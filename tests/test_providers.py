from __future__ import annotations

import unittest
from pathlib import Path

import app
from provider_adapter import GenericApiClient, GenericMcpClient, SellerSpriteApiClient, XiyouApiClient, XiyouMcpClient, build_data_client


class FakeSellerSprite(SellerSpriteApiClient):
    def _request(self, method, path, payload=None, *, tool_name=""):
        with self._lock:
            self._calls += 1
            self._tool_calls[tool_name] += 1
        if path == "/v1/traffic/keyword":
            return {"data": [{"keywords": "关键词1", "trafficPercentage": 0.135, "searches": 9000, "rankPosition": {"position": 7}, "adPosition": {"position": 2}}]}
        if path == "/v1/aba/research":
            return {"data": [{"keyword": "关键词1", "searchRank": 321, "searches": 10000}]}
        if path.startswith("/v1/asin/"):
            return {"data": {"price": 29.99, "bsrRank": 456, "rating": 4.6, "ratings": 789}}
        if path == "/v1/product/competitor-lookup":
            return {"data": [{"asin": "B000000001", "units": 654}]}
        raise AssertionError(path)


class FakeXiyou(XiyouApiClient):
    def __init__(self, base_url, api_key):
        super().__init__(base_url, api_key)
        self.requests = []

    def _request(self, method, path, payload=None, *, tool_name=""):
        self.requests.append((method, path, payload))
        with self._lock:
            self._calls += 1
            self._tool_calls[tool_name] += 1
        if path == "/v1/asins/research/list/period":
            return {"data": [{
                "searchTerm": "关键词1",
                "trafficSummary": {"trafficAcquisitionRate": {"total": "8.2%"}},
                "ranks": [{"position": "or", "totalRank": 5}, {"position": "sp", "totalRank": 1}],
            }]}
        if path == "/v1/searchTerms/info":
            return {"data": [{"searchTerm": "关键词1", "weeklySearchVolume": 12000, "abaReport": {"searchFrequencyRank": 222}}]}
        if path == "/v1/asins/info":
            return {"data": [{"asin": "B000000001", "price": 39.5, "stars": 4.7, "ratings": 888, "amazonUrl": "https://example.com/p"}]}
        if path == "/v1/asins/orders":
            return {"data": [{"asin": "B000000001", "orders": 777}]}
        if path == "/v1/asins/bsrInfo/trends/daily":
            return {"data": [{
                "categoryTree": [
                    {"categoryId": "root-1", "root": True},
                    {"categoryId": "leaf-1", "root": False},
                ],
                "trends": [
                    {"date": "2026-07-20", "values": [{"categoryId": "root-1", "rank": 1200}]},
                    {"date": "2026-07-21", "values": [
                        {"categoryId": "leaf-1", "rank": 12},
                        {"categoryId": "root-1", "rank": 999},
                    ]},
                ],
            }]}
        raise AssertionError(path)


class ProviderTests(unittest.TestCase):
    def test_sellersprite_maps_required_fields(self):
        client = FakeSellerSprite("https://api.sellersprite.com", "secret")
        result = client.capture_keyword("B000000001", "关键词1", "US")
        self.assertEqual(result["traffic_share"], "13.5%")
        self.assertEqual(result["aba_rank"], 321)
        self.assertEqual(result["organic_position"], 7)
        self.assertEqual(result["ad_position"], 2)
        self.assertEqual(result["estimated_sales"], 654)
        self.assertEqual(result["product_rank"], 456)
        self.assertEqual(result["rating"], 4.6)
        self.assertEqual(result["review_count"], 789)

    def test_xiyou_maps_required_fields(self):
        client = FakeXiyou("https://openapi.xydc.com", "secret")
        result = client.capture_keyword("B000000001", "关键词1", "US")
        self.assertEqual(result["traffic_share"], "8.2%")
        self.assertEqual(result["aba_rank"], 222)
        self.assertEqual(result["search_volume"], 12000)
        self.assertEqual(result["organic_position"], 5)
        self.assertEqual(result["ad_position"], 1)
        self.assertEqual(result["estimated_sales"], 777)
        self.assertEqual(result["product_rank"], 999)
        self.assertEqual(result["product_url"], "https://example.com/p")
        info_payloads = [payload for _, path, payload in client.requests if path == "/v1/asins/info"]
        self.assertEqual(info_payloads, [{"entities": [{"country": "US", "asin": "B000000001"}]}])

    def test_connection_normalization_and_redaction(self):
        connection = app.normalize_connection({
            "provider": "sellersprite", "mode": "api",
            "api_key": "top-secret", "api_url": "https://api.sellersprite.com",
        })
        self.assertTrue(app.connection_has_value(connection))
        clean = app.sanitize_payload_for_disk({"connection": connection, "lark": {"feishu_app_secret": "secret"}})
        self.assertEqual(clean["connection"]["provider"], "sellersprite")
        self.assertEqual(clean["connection"]["api_key"], "")
        self.assertEqual(clean["lark"]["feishu_app_secret"], "")

    def test_build_provider_clients(self):
        self.assertEqual(build_data_client({"provider": "sellersprite", "mode": "api", "api_key": "x"}).source_name, "sellersprite_api")
        self.assertEqual(build_data_client({"provider": "xiyou", "mode": "api", "api_key": "x"}).source_name, "xiyou_api")
        self.assertEqual(build_data_client({"provider": "xiyou", "mode": "mcp_url", "mcp_url": "https://mcp.xydc.com/mcp", "mcp_token": "x"}).source_name, "xiyou_mcp")
        self.assertEqual(build_data_client({"provider": "sif", "mode": "mcp_url", "mcp_url": "https://mcp.sif.com/mcp", "mcp_token": "x"}).source_name, "sif_mcp")
        self.assertIsInstance(build_data_client({"provider": "custom", "mode": "api", "api_url": "https://example.com/data"}), GenericApiClient)
        self.assertIsInstance(build_data_client({"provider": "custom", "mode": "mcp_url", "mcp_url": "https://example.com/mcp"}), GenericMcpClient)


    def test_xiyou_mcp_prefers_official_tool_names(self):
        client = XiyouMcpClient("https://mcp.xydc.com/mcp", "token")
        client._generic_tools = [
            {"name": "get_asin_keywords", "description": "ASIN关键词"},
            {"name": "get_keyword_info", "description": "关键词详情"},
            {"name": "get_asin_info", "description": "ASIN详情"},
            {"name": "get_asin_keyword_rank_hourly", "description": "关键词排名"},
            {"name": "get_asin_order_trends", "description": "订单趋势"},
            {"name": "get_asin_bsr_trends", "description": "BSR趋势"},
        ]
        self.assertEqual(client._select_tool("traffic")["name"], "get_asin_keywords")
        self.assertEqual(client._select_tool("keyword")["name"], "get_keyword_info")
        self.assertEqual(client._select_tool("product")["name"], "get_asin_info")
        self.assertEqual(client._select_tool("ranking")["name"], "get_asin_keyword_rank_hourly")
        self.assertEqual(client._select_tool("sales")["name"], "get_asin_order_trends")
        self.assertEqual(client._select_tool("bsr")["name"], "get_asin_bsr_trends")
        self.assertEqual(client._auth_headers(), {"Authorization": "Bearer token"})

    def test_xiyou_defaults_to_mcp_and_token_is_redacted(self):
        connection = app.normalize_connection({"provider": "xiyou", "mcp_token": "private-token"})
        self.assertEqual(connection["mode"], "mcp_url")
        self.assertEqual(connection["mcp_url"], "https://mcp.xydc.com/mcp")
        self.assertTrue(app.connection_has_value(connection))
        clean = app.sanitize_payload_for_disk({"connection": connection, "lark": {"feishu_app_secret": ""}})
        self.assertEqual(clean["connection"]["mcp_token"], "")

    def test_generic_mcp_sends_common_key_headers(self):
        client = GenericMcpClient("https://example.com/mcp", "key-123")
        headers = client._auth_headers()
        self.assertEqual(headers["Authorization"], "Bearer key-123")
        self.assertEqual(headers["X-API-Key"], "key-123")
        self.assertEqual(headers["MCP-Key"], "key-123")

    def test_ui_contains_all_provider_options_and_no_sensitive_keyword_examples(self):
        html = Path(app.STATIC_DIR / "index.html").read_text(encoding="utf-8")
        for value in ("sorftime", "sellersprite", "sif", "xiyou", "custom"):
            self.assertIn(f'value="{value}"', html)
        self.assertIn("Sorftime CLI", html)
        self.assertIn("Sorftime MCP", html)
        self.assertIn("西柚洞察 MCP", html)
        self.assertIn("https://mcp.xydc.com/mcp", html)
        self.assertIn("关键词1", html)
        self.assertNotIn("真实业务关键词", html)


if __name__ == "__main__":
    unittest.main()
