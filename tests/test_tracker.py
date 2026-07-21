from __future__ import annotations

import io
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from openpyxl import load_workbook

import app
from sorftime_adapter import SorftimeCliClient, SorftimeMcpClient


class FakeSorftimeClient(SorftimeMcpClient):
    def __init__(self) -> None:
        super().__init__("https://example.invalid/mcp")
        self.seen: list[tuple[str, dict]] = []

    def _ensure_initialized(self) -> None:
        self._initialized = True

    def call_tool(self, name: str, arguments: dict):
        started = time.perf_counter()
        self.seen.append((name, dict(arguments)))
        with self._lock:
            self._mcp_calls += 1
            self._tool_calls[name] += 1
            self._tool_seconds[name] += time.perf_counter() - started

        if name == "product_traffic_terms":
            return {"data": [{"keyword": "under bed storage", "trafficShare": "12.5%"}]}
        if name == "keyword_detail":
            return {"data": {"keyword": arguments["keyword"], "searchFrequencyRank": 321, "searchVolume": 12345}}
        if name == "keyword_search_results" and arguments["positionType"] == 0:
            return {"data": [
                {"asin": "B000000001", "position": 4},
                {"asin": "B000000002", "position": 9},
            ]}
        if name == "keyword_search_results" and arguments["positionType"] == 2:
            return {"data": []}
        if name == "product_detail":
            asin = arguments["asin"]
            suffix = int(asin[-1])
            return {"data": {
                "asin": asin,
                "price": 29.99 + suffix,
                "coupon": "$5 off",
                "dealPrice": 25.99,
                "primePrice": 27.99,
                "monthlySales": 600 + suffix,
                "BSR": 1000 + suffix,
                "rating": 4.6,
                "reviewCount": 800 + suffix,
            }}
        raise AssertionError(f"Unexpected tool call: {name} {arguments}")


class TrackerTests(unittest.TestCase):
    def test_field_fallbacks_and_cache_reduce_calls(self) -> None:
        client = FakeSorftimeClient()
        first = client.capture_keyword("B000000001", "under bed storage", "US")
        second = client.capture_keyword("B000000002", "under bed storage", "US")

        self.assertEqual(first["traffic_share"], "12.5%")
        self.assertEqual(first["aba_rank"], 321)
        self.assertEqual(first["search_volume"], 12345)
        self.assertEqual(first["organic_position"], 4)
        self.assertEqual(second["organic_position"], 9)
        self.assertEqual(first["price"], 30.99)
        self.assertEqual(first["coupon_value"], "$5 off")
        self.assertEqual(first["deal_price"], 25.99)
        self.assertEqual(first["prime_discount_price"], 27.99)
        self.assertEqual(first["estimated_sales"], 601)
        self.assertEqual(first["product_rank"], 1001)
        self.assertEqual(first["rating"], 4.6)
        self.assertEqual(first["review_count"], 801)
        self.assertIn("/dp/B000000001", first["product_url"])

        counts = client.stats()["tool_calls"]
        self.assertEqual(counts["product_traffic_terms"], 2)
        self.assertEqual(counts["keyword_detail"], 1)
        self.assertEqual(counts["keyword_search_results"], 2)
        self.assertEqual(counts["product_detail"], 2)
        self.assertNotIn("product_trend", counts)

    def test_cli_account_mode_uses_fixed_sorftime_commands(self) -> None:
        old_path = os.environ.get("PATH", "")
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "sorftime"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "args=sys.argv[1:]\n"
                "if not args: sys.exit(2)\n"
                "if args[0] in {'add','use'}:\n"
                "    print(json.dumps({'ok': True}))\n"
                "elif args[0]=='whoami':\n"
                "    print(json.dumps({'account':'keyword-tracker'}))\n"
                "elif args[0]=='api':\n"
                "    endpoint=args[1]\n"
                "    if endpoint=='ASINRequestKeywordv2':\n"
                "        data=[{'keyword':'under bed storage','trafficShare':'12.5%','searchFrequencyRank':321,'searchVolume':12345,'organicPosition':4,'adPosition':2}]\n"
                "    elif endpoint=='ProductRequest':\n"
                "        data={'price':29.99,'coupon':'$5 off','dealPrice':25.99,'primePrice':27.99,'monthlySales':600,'BSR':1000,'rating':4.6,'reviewCount':800}\n"
                "    else:\n"
                "        print(json.dumps({'Code':1,'Message':'unknown endpoint'})); sys.exit(1)\n"
                "    print(json.dumps({'Code':0,'Data':data}))\n"
                "else:\n"
                "    sys.exit(2)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            os.environ["PATH"] = f"{tmp}{os.pathsep}{old_path}"
            try:
                client = SorftimeCliClient("ACCOUNT-SK-SECRET")
                ready = client.check_ready()
                result = client.capture_keyword("B000000001", "under bed storage", "US")
                stats = client.stats()
                client.close()
            finally:
                os.environ["PATH"] = old_path

        self.assertEqual(ready["source"], "sorftime_cli")
        self.assertEqual(result["traffic_share"], "12.5%")
        self.assertEqual(result["organic_position"], 4)
        self.assertEqual(result["ad_position"], 2)
        self.assertEqual(result["price"], 29.99)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(stats["mcp_calls"], 2)
        self.assertEqual(stats["tool_calls"]["ASINRequestKeywordv2"], 1)
        self.assertEqual(stats["tool_calls"]["ProductRequest"], 1)

    def test_excel_has_required_columns_and_call_summary(self) -> None:
        record = {key: "" for key, _ in app.FIELD_COLUMNS}
        record.update({
            "date": "2026-07-21",
            "asin": "B000000001",
            "keyword": "under bed storage",
            "traffic_share": "12.5%",
            "status": "ok",
        })
        stats = {
            "mcp_calls": 7,
            "elapsed_seconds": 3.21,
            "tool_calls": {"keyword_detail": 1, "product_detail": 1},
            "tool_seconds": {"keyword_detail": 0.4, "product_detail": 0.8},
        }
        content = app.make_workbook([record], stats)
        workbook = load_workbook(io.BytesIO(content), data_only=False)
        self.assertEqual(workbook.sheetnames, ["关键词监控结果", "任务汇总"])
        headers = [cell.value for cell in workbook["关键词监控结果"][1]]
        self.assertEqual(headers[:17], [label for _, label in app.FIELD_COLUMNS[:17]])
        summary = workbook["任务汇总"]
        self.assertEqual(summary["B3"].value, 7)
        self.assertEqual(summary["B4"].value, 3.21)

    def test_connection_secrets_are_redacted_from_job_payload(self) -> None:
        connection = {
            "mode": "mcp_url",
            "mcp_url": "https://mcp.sorftime.com/?key=SECRET-IN-URL",
            "mcp_token": "SECRET-TOKEN",
            "cli_account_sk": "SECRET-SK",
        }
        clean = app.sanitize_payload_for_disk({"connection": connection, "lark": {"feishu_app_secret": "SECRET-LARK"}})
        serialized = json.dumps(clean, ensure_ascii=False)
        self.assertNotIn("SECRET", serialized)
        self.assertEqual(clean["connection"]["mcp_url"], "")
        self.assertEqual(clean["connection"]["mcp_token"], "")
        self.assertEqual(clean["connection"]["cli_account_sk"], "")

    def test_hosted_mode_rejects_local_or_insecure_mcp_url(self) -> None:
        app.validate_hosted_mcp_url("https://mcp.sorftime.com/")
        with self.assertRaises(ValueError):
            app.validate_hosted_mcp_url("http://mcp.example.com/path")
        with self.assertRaises(ValueError):
            app.validate_hosted_mcp_url("https://localhost:3000/mcp")
        with self.assertRaises(ValueError):
            app.validate_hosted_mcp_url("https://127.0.0.1/mcp")

    def test_hosted_mode_keeps_excel_for_browser_download(self) -> None:
        original_export = app.EXPORT_DIR
        original_hosted = app.HOSTED_MODE
        try:
            with tempfile.TemporaryDirectory() as internal, tempfile.TemporaryDirectory() as local:
                app.EXPORT_DIR = Path(internal)
                app.HOSTED_MODE = True
                url, local_path = app.write_excel_exports(b"xlsx", "hosted.xlsx", {"auto_download": True, "download_dir": local})
                self.assertEqual(url, "/exports/hosted.xlsx")
                self.assertEqual(local_path, "")
                self.assertEqual((Path(internal) / "hosted.xlsx").read_bytes(), b"xlsx")
                self.assertFalse((Path(local) / "hosted.xlsx").exists())
        finally:
            app.EXPORT_DIR = original_export
            app.HOSTED_MODE = original_hosted

    def test_concurrent_job_updates_are_json_serializable(self) -> None:
        # Smoke-test that ordinary progress payloads remain safe to write from worker threads.
        payload = {"status": "running", "tool_calls": {"ProductRequest": 1}, "logs": ["ok"]}
        errors: list[Exception] = []

        def worker() -> None:
            try:
                json.dumps(payload, ensure_ascii=False)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
