from __future__ import annotations

import cgi
import json
import mimetypes
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from lark_writer import append_records_to_lark
from sorftime_adapter import build_sorftime_client, capture_batch


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "exports"
JOB_DIR = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "keyword_tracker.db"
DAILY_JOB_PATH = DATA_DIR / "daily_job.json"
APP_HOST = os.environ.get("HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("PORT") or os.environ.get("KEYWORD_TRACKER_PORT", "8766"))
EXCEL_FONT_NAME = "Microsoft YaHei"
EXCEL_FONT_SIZE = 11

FIELD_COLUMNS = [
    ("date", "日期"),
    ("captured_at", "抓取时间"),
    ("marketplace", "站点"),
    ("asin", "ASIN"),
    ("keyword", "关键词"),
    ("organic_position", "最近自然位置"),
    ("organic_time", "自然曝光时间"),
    ("ad_position", "最近广告位置"),
    ("ad_time", "广告曝光时间"),
    ("keyword_rank", "最新曝光位置"),
    ("price", "当前价格"),
    ("estimated_sales", "月销量"),
    ("product_rank", "大类排名"),
    ("rating", "链接评分"),
    ("review_count", "评价数量"),
    ("product_url", "产品链接"),
    ("source", "数据源"),
    ("status", "状态"),
    ("message", "备注"),
]

DB_CAPTURE_COLUMNS = {
    "owner_id": "TEXT",
    "organic_position": "TEXT",
    "organic_time": "TEXT",
    "ad_position": "TEXT",
    "ad_time": "TEXT",
    "rating": "TEXT",
    "review_count": "TEXT",
    "product_url": "TEXT",
}


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)
    JOB_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id TEXT,
                date TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                marketplace TEXT NOT NULL,
                asin TEXT NOT NULL,
                keyword TEXT NOT NULL,
                keyword_rank TEXT,
                organic_position TEXT,
                organic_time TEXT,
                ad_position TEXT,
                ad_time TEXT,
                price TEXT,
                estimated_sales TEXT,
                product_rank TEXT,
                rating TEXT,
                review_count TEXT,
                product_url TEXT,
                source TEXT,
                status TEXT,
                message TEXT,
                raw_json TEXT
            )
            """
        )
        existing_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(captures)").fetchall()
        }
        for column, column_type in DB_CAPTURE_COLUMNS.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE captures ADD COLUMN {column} {column_type}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_captures_date ON captures(date, asin, keyword)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_captures_owner ON captures(owner_id, id)"
        )


def parse_text_items(value: str, uppercase: bool = False) -> list[str]:
    pieces: list[str] = []
    for raw_line in (value or "").replace(",", "\n").replace(";", "\n").splitlines():
        item = raw_line.strip()
        if not item:
            continue
        pieces.append(item.upper() if uppercase else item)
    return dedupe(pieces)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def read_items_from_upload(field: cgi.FieldStorage | None, uppercase: bool = False) -> list[str]:
    if field is None or not getattr(field, "filename", ""):
        return []
    data = field.file.read()
    filename = field.filename.lower()
    values: list[str] = []

    if filename.endswith(".xlsx"):
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
        sheet = workbook.active
        for row_index, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            value = "" if row[0] is None else str(row[0]).strip()
            if not value:
                continue
            if row_index == 1 and value.casefold() in {"asin", "keyword", "关键词"}:
                continue
            values.append(value.upper() if uppercase else value)
    else:
        text = decode_text_file(data)
        values.extend(parse_text_items(text, uppercase=uppercase))

    return dedupe(values)


def decode_text_file(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def make_workbook(records: list[dict[str, Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "keyword_rank"
    headers = [label for _, label in FIELD_COLUMNS]
    sheet.append(headers)

    for record in records:
        sheet.append([record.get(key, "") for key, _ in FIELD_COLUMNS])

    widths = [12, 20, 10, 16, 28, 18, 20, 18, 20, 16, 12, 12, 14, 12, 12, 42, 14, 12, 32]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
    apply_excel_style(sheet, "1F6F78")

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def make_template(kind: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    if kind == "keywords":
        sheet.title = "keywords"
        sheet.append(["关键词"])
    else:
        sheet.title = "asins"
        sheet.append(["ASIN"])

    sheet.column_dimensions["A"].width = 28
    apply_excel_style(sheet, "334E68")

    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def apply_excel_style(sheet: Any, header_color: str) -> None:
    default_font = Font(name=EXCEL_FONT_NAME, size=EXCEL_FONT_SIZE)
    header_font = Font(name=EXCEL_FONT_NAME, size=EXCEL_FONT_SIZE, bold=True, color="FFFFFF")
    default_alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    header_fill = PatternFill("solid", fgColor=header_color)

    for row in sheet.iter_rows():
        for cell in row:
            cell.font = default_font
            cell.alignment = default_alignment

    for cell in sheet[1]:
        cell.font = header_font
        cell.fill = header_fill


def save_records(records: list[dict[str, Any]]) -> None:
    if not records:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO captures (
                owner_id, date, captured_at, marketplace, asin, keyword, keyword_rank,
                organic_position, organic_time, ad_position, ad_time, price,
                estimated_sales, product_rank, rating, review_count, product_url,
                source, status, message, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.get("owner_id", ""),
                    record.get("date", ""),
                    record.get("captured_at", ""),
                    record.get("marketplace", ""),
                    record.get("asin", ""),
                    record.get("keyword", ""),
                    str(record.get("keyword_rank", "")),
                    str(record.get("organic_position", "")),
                    str(record.get("organic_time", "")),
                    str(record.get("ad_position", "")),
                    str(record.get("ad_time", "")),
                    str(record.get("price", "")),
                    str(record.get("estimated_sales", "")),
                    str(record.get("product_rank", "")),
                    str(record.get("rating", "")),
                    str(record.get("review_count", "")),
                    str(record.get("product_url", "")),
                    record.get("source", ""),
                    record.get("status", ""),
                    record.get("message", ""),
                    json.dumps(record.get("raw", {}), ensure_ascii=False),
                )
                for record in records
            ],
        )


def latest_history(owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
    owner_id = sanitize_owner_id(owner_id)
    if not owner_id:
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT date, captured_at, marketplace, asin, keyword, keyword_rank, price,
                   organic_position, organic_time, ad_position, ad_time,
                   estimated_sales, product_rank, rating, review_count, product_url,
                   source, status, message
            FROM captures
            WHERE owner_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (owner_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def sanitize_owner_id(value: str) -> str:
    value = (value or "").strip()
    return value if re.fullmatch(r"[A-Za-z0-9_-]{16,80}", value) else ""


def parse_capture_form(form: cgi.FieldStorage) -> dict[str, Any]:
    asins = parse_text_items(
        form.getfirst("asins_text", "") or form.getfirst("asinText", ""),
        uppercase=True,
    )
    keywords = parse_text_items(
        form.getfirst("keywords_text", "") or form.getfirst("keywordText", "")
    )

    asins.extend(
        read_items_from_upload(
            first_form_field(form, "asins_file", "asinFile"),
            True,
        )
    )
    keywords.extend(
        read_items_from_upload(
            first_form_field(form, "keywords_file", "keywordFile"),
        )
    )
    delivery = (
        form.getfirst("delivery", "")
        or form.getfirst("outputMode", "")
        or "excel"
    )
    if delivery == "feishu":
        delivery = "lark"

    return {
        "asins": dedupe(asins),
        "keywords": dedupe(keywords),
        "marketplace": (
            form.getfirst("marketplace", "")
            or form.getfirst("marketplaceCode", "")
            or "US"
        ).strip() or "US",
        "owner_id": sanitize_owner_id(form.getfirst("owner_id", "")),
        "delivery": delivery,
        "lark": {
            "spreadsheet_token": form.getfirst("spreadsheet_token", "").strip(),
            "spreadsheet_url": form.getfirst("spreadsheet_url", "").strip(),
            "sheet_id": form.getfirst("sheet_id", "").strip(),
            "append_range": form.getfirst("append_range", "").strip(),
            "include_header": form.getfirst("include_header", "") == "on",
        },
    }


def first_form_field(form: cgi.FieldStorage, *names: str) -> cgi.FieldStorage | None:
    for name in names:
        if name in form:
            field = form[name]
            if isinstance(field, list):
                return field[0] if field else None
            return field
    return None


def form_from_request(handler: BaseHTTPRequestHandler) -> cgi.FieldStorage:
    return cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": handler.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": handler.headers.get("Content-Length", "0"),
        },
        keep_blank_values=True,
    )


def run_capture(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not payload["asins"]:
        raise ValueError("请至少输入或上传 1 个 ASIN")
    if not payload["keywords"]:
        raise ValueError("请至少输入或上传 1 个关键词")

    client = build_sorftime_client()
    records = capture_batch(
        client=client,
        asins=payload["asins"],
        keywords=payload["keywords"],
        marketplace=payload["marketplace"],
    )
    for record in records:
        record["owner_id"] = payload.get("owner_id", "")
    save_records(records)
    return records



def job_path(job_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", job_id or "")
    return JOB_DIR / f"{safe_id}.json"


def write_job(job: dict[str, Any]) -> None:
    JOB_DIR.mkdir(exist_ok=True)
    tmp_path = job_path(job["id"]).with_suffix(".tmp")
    tmp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(job_path(job["id"]))


def read_job(job_id: str) -> dict[str, Any] | None:
    path = job_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def append_job_log(job: dict[str, Any], line: str) -> None:
    logs = job.setdefault("logs", [])
    logs.append(f"{datetime.now().strftime('%H:%M:%S')} {line}")
    del logs[:-120]


def public_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = dict(job)
    payload.pop("payload", None)
    payload.pop("records", None)
    return payload


def run_capture_with_progress(job_id: str, payload: dict[str, Any]) -> None:
    job = read_job(job_id) or {"id": job_id}
    try:
        asins = payload.get("asins", [])
        keywords = payload.get("keywords", [])
        if not asins:
            raise ValueError("请至少输入或上传 1 个 ASIN")
        if not keywords:
            raise ValueError("请至少输入或上传 1 个关键词")

        total = max(1, len(asins) * len(keywords))
        records: list[dict[str, Any]] = []
        client = build_sorftime_client()
        capture_date = datetime.now().date().isoformat()
        captured_at = datetime.now().isoformat(timespec="seconds")
        marketplace = payload.get("marketplace", "US")
        owner_id = payload.get("owner_id", "")

        job.update({"status": "running", "percent": 3, "done": 0, "total": total})
        append_job_log(job, f"任务启动：{len(asins)} 个 ASIN × {len(keywords)} 个关键词，共 {total} 条。")
        write_job(job)

        done = 0
        for asin in asins:
            for keyword in keywords:
                done += 1
                job.update({"status": "running", "done": done, "total": total, "percent": int(5 + (done - 1) / total * 80)})
                append_job_log(job, f"抓取中 {done}/{total}：{asin} | {keyword}")
                write_job(job)
                try:
                    result = client.capture_keyword(asin, keyword, marketplace)
                except Exception as exc:
                    result = {
                        "keyword_rank": "",
                        "organic_position": "",
                        "organic_time": "",
                        "ad_position": "",
                        "ad_time": "",
                        "price": "",
                        "estimated_sales": "",
                        "product_rank": "",
                        "rating": "",
                        "review_count": "",
                        "product_url": "",
                        "status": "failed",
                        "message": str(exc),
                        "raw": {},
                    }
                records.append(
                    {
                        "owner_id": owner_id,
                        "date": capture_date,
                        "captured_at": captured_at,
                        "marketplace": marketplace,
                        "asin": asin,
                        "keyword": keyword,
                        "keyword_rank": result.get("keyword_rank", ""),
                        "organic_position": result.get("organic_position", ""),
                        "organic_time": result.get("organic_time", ""),
                        "ad_position": result.get("ad_position", ""),
                        "ad_time": result.get("ad_time", ""),
                        "price": result.get("price", ""),
                        "estimated_sales": result.get("estimated_sales", ""),
                        "product_rank": result.get("product_rank", ""),
                        "rating": result.get("rating", ""),
                        "review_count": result.get("review_count", ""),
                        "product_url": result.get("product_url", ""),
                        "source": client.source_name,
                        "status": result.get("status", "ok"),
                        "message": result.get("message", ""),
                        "raw": result.get("raw", result),
                    }
                )
                job.update({"percent": int(5 + done / total * 80), "done": done})
                write_job(job)

        job.update({"status": "saving", "percent": 88})
        append_job_log(job, "正在保存历史记录并生成输出文件。")
        write_job(job)
        save_records(records)

        output_name = ""
        lark_result: dict[str, Any] | None = None
        delivery = payload.get("delivery", "excel")
        if delivery in {"excel", "both"}:
            output_name = f"keyword-rank-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
            (EXPORT_DIR / output_name).write_bytes(make_workbook(records))
        if delivery in {"lark", "both"}:
            lark_result = append_records_to_lark(records, payload.get("lark", {}), FIELD_COLUMNS)

        job.update(
            {
                "status": "completed" if not lark_result or lark_result.get("ok") else "failed",
                "percent": 100,
                "done": total,
                "records_count": len(records),
                "excel": f"/exports/{output_name}" if output_name else "",
                "lark": lark_result,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        append_job_log(job, f"任务完成：{len(records)} 条记录。")
        if lark_result and not lark_result.get("ok"):
            append_job_log(job, f"飞书写入失败：{lark_result.get('message', '')}")
        write_job(job)
    except Exception as exc:
        job.update({"status": "failed", "percent": job.get("percent", 0), "error": str(exc), "finished_at": datetime.now().isoformat(timespec="seconds")})
        append_job_log(job, f"任务失败：{exc}")
        write_job(job)


def create_capture_job(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    total = max(1, len(payload.get("asins", [])) * len(payload.get("keywords", [])))
    job = {
        "id": job_id,
        "status": "queued",
        "percent": 1,
        "done": 0,
        "total": total,
        "records_count": 0,
        "logs": [f"{datetime.now().strftime('%H:%M:%S')} 任务已创建，等待启动。"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
    }
    write_job(job)
    thread = threading.Thread(target=run_capture_with_progress, args=(job_id, payload), daemon=True)
    thread.start()
    return public_job_payload(job)


def save_daily_job(payload: dict[str, Any], enabled: bool, run_time: str) -> None:
    job = {
        "enabled": enabled,
        "run_time": run_time or "09:00",
        "payload": payload,
        "last_run_date": None,
    }
    DAILY_JOB_PATH.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def load_daily_job() -> dict[str, Any] | None:
    if not DAILY_JOB_PATH.exists():
        return None
    try:
        return json.loads(DAILY_JOB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def scheduler_loop() -> None:
    while True:
        try:
            job = load_daily_job()
            if job and job.get("enabled"):
                now = datetime.now()
                run_time = job.get("run_time", "09:00")
                due_time = datetime.strptime(run_time, "%H:%M").time()
                if now.time() >= due_time and job.get("last_run_date") != now.date().isoformat():
                    records = run_capture(job["payload"])
                    if job["payload"].get("delivery") == "lark":
                        append_records_to_lark(records, job["payload"].get("lark", {}), FIELD_COLUMNS)
                    else:
                        output = EXPORT_DIR / f"daily-keyword-rank-{now.date().isoformat()}.xlsx"
                        output.write_bytes(make_workbook(records))
                    job["last_run_date"] = now.date().isoformat()
                    DAILY_JOB_PATH.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            error_path = DATA_DIR / "scheduler-error.log"
            error_path.write_text(f"{datetime.now().isoformat()} {exc}\n", encoding="utf-8")
        time.sleep(60)


class KeywordTrackerHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.serve_file(STATIC_DIR / "index.html")
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "service": "amazon-keyword-tracker", "time": datetime.now().isoformat(timespec="seconds")})
        if parsed.path.startswith("/static/"):
            return self.serve_file(STATIC_DIR / parsed.path.removeprefix("/static/"))
        if parsed.path == "/api/history":
            owner_id = parse_qs(parsed.query).get("owner_id", [""])[0]
            return self.send_json({"records": latest_history(owner_id)})
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = read_job(job_id)
            if not job:
                return self.send_json({"ok": False, "error": "任务不存在或服务已重启"}, status=404)
            return self.send_json({"ok": True, "job": public_job_payload(job)})
        if parsed.path == "/api/daily":
            return self.send_json({"job": load_daily_job()})
        if parsed.path == "/api/template":
            kind = parse_qs(parsed.query).get("kind", ["asins"])[0]
            body = make_template(kind)
            filename = "keywords-template.xlsx" if kind == "keywords" else "asins-template.xlsx"
            return self.send_bytes(
                body,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                {"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        if parsed.path.startswith("/exports/"):
            return self.serve_file(EXPORT_DIR / parsed.path.removeprefix("/exports/"))
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/jobs":
                payload = parse_capture_form(form_from_request(self))
                job = create_capture_job(payload)
                return self.send_json({"ok": True, "job": job})

            if self.path == "/api/capture":
                payload = parse_capture_form(form_from_request(self))
                records = run_capture(payload)
                if payload["delivery"] == "lark":
                    result = append_records_to_lark(records, payload["lark"], FIELD_COLUMNS)
                    return self.send_json({"ok": result["ok"], "records": len(records), "lark": result})
                body = make_workbook(records)
                if payload["delivery"] == "both":
                    output_name = f"keyword-rank-results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
                    (EXPORT_DIR / output_name).write_bytes(body)
                    result = append_records_to_lark(records, payload["lark"], FIELD_COLUMNS)
                    return self.send_json(
                        {
                            "ok": result["ok"],
                            "records": len(records),
                            "lark": result,
                            "excel": f"/exports/{output_name}",
                        }
                    )
                return self.send_bytes(
                    body,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    {"Content-Disposition": 'attachment; filename="keyword-rank-results.xlsx"'},
                )

            if self.path == "/api/test-excel":
                records = [
                    {
                        "date": datetime.now().date().isoformat(),
                        "captured_at": datetime.now().isoformat(timespec="seconds"),
                        "marketplace": "US",
                        "asin": "",
                        "keyword": "",
                        "organic_position": "测试自然位置",
                        "organic_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "ad_position": "测试广告位置",
                        "ad_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "keyword_rank": "测试曝光位置",
                        "price": "99.99",
                        "estimated_sales": "120",
                        "product_rank": "12345",
                        "rating": "4.6",
                        "review_count": "88",
                        "product_url": "",
                        "source": "self_test",
                        "status": "ok",
                        "message": "测试行，不是真实抓取。",
                    }
                ]
                body = make_workbook(records)
                return self.send_bytes(
                    body,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    {"Content-Disposition": 'attachment; filename="keyword-rank-test.xlsx"'},
                )

            if self.path == "/api/daily":
                form = form_from_request(self)
                payload = parse_capture_form(form)
                enabled = form.getfirst("daily_enabled", "") == "on"
                run_time = form.getfirst("run_time", "09:00")
                save_daily_job(payload, enabled, run_time)
                return self.send_json({"ok": True, "job": load_daily_job()})
        except ValueError as exc:
            return self.send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            return self.send_json({"ok": False, "error": str(exc)}, status=500)
        self.send_error(404)

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(path.read_bytes(), content_type)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json", status=status)

    def send_bytes(
        self,
        body: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=60")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    ensure_storage()
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()

    server = ThreadingHTTPServer((APP_HOST, APP_PORT), KeywordTrackerHandler)
    print(f"Keyword tracker running at http://{APP_HOST}:{APP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
