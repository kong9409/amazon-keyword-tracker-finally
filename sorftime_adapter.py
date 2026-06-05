from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


BASE_DIR = Path(__file__).resolve().parent
_CLI_PROFILE_READY = False


class SorftimeClient(Protocol):
    source_name: str

    def capture_keyword(self, asin: str, keyword: str, marketplace: str) -> dict[str, Any]:
        ...


class DemoSorftimeClient:
    source_name = "demo"

    def capture_keyword(self, asin: str, keyword: str, marketplace: str) -> dict[str, Any]:
        seed = hashlib.sha256(f"{datetime.now().date()}|{marketplace}|{asin}|{keyword}".encode()).hexdigest()
        number = int(seed[:8], 16)
        rank = (number % 120) + 1
        return {
            "keyword_rank": rank if rank <= 100 else ">100",
            "traffic_share": f"{(number % 280) / 10:.1f}%",
            "aba_rank": 1000 + (number % 90000),
            "search_volume": 500 + (number % 40000),
            "price": round(11 + (number % 9000) / 100, 2),
            "coupon_type": "",
            "coupon_value": "",
            "deal_status": "否",
            "deal_price": "",
            "prime_discount_price": "",
            "estimated_sales": 20 + (number % 480),
            "product_rank": 500 + (number % 19000),
            "status": "demo",
            "message": "Sorftime MCP is not configured, so demo data was used.",
            "raw": {"seed": seed},
        }


class ExternalSorftimeClient:
    source_name = "sorftime"

    def __init__(self, command: str) -> None:
        self.command = command

    def capture_keyword(self, asin: str, keyword: str, marketplace: str) -> dict[str, Any]:
        payload = {
            "asin": asin,
            "keyword": keyword,
            "marketplace": marketplace,
            "date": datetime.now().date().isoformat(),
        }
        args = shlex.split(self.command, posix=False)
        completed = subprocess.run(
            args,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            return {
                "status": "failed",
                "message": completed.stderr.strip() or completed.stdout.strip() or "Sorftime command failed.",
                "raw": payload,
            }
        data = json.loads(completed.stdout)
        return normalize_external_result(data)


class SorftimeMcpClient:
    source_name = "sorftime_mcp"

    def __init__(self, url: str) -> None:
        self.url = url
        self._initialized = False
        self._keyword_result_cache: dict[tuple[str, str, int], Any] = {}
        self._traffic_terms_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._product_detail_cache: dict[tuple[str, str], Any] = {}
        self._product_trend_cache: dict[tuple[str, str, str], Any] = {}

    def capture_keyword(self, asin: str, keyword: str, marketplace: str) -> dict[str, Any]:
        self._ensure_initialized()
        site = normalize_marketplace(marketplace)

        traffic_match = self.find_in_traffic_terms(asin, keyword, site)
        ranking = {}
        if not traffic_match:
            ranking = self.call_tool(
                "product_ranking_trend_by_keyword",
                {"asin": asin, "keyword": keyword, "page": 1, "amzSite": site},
            )
        detail = self.product_detail(asin, site)
        detail_metrics = parse_product_detail(detail)

        sales = self.product_trend(asin, "SalesVolume", site)
        price = self.product_trend(asin, "Price", site)
        product_rank = self.product_trend(asin, "Rank", site)

        raw = {
            "traffic_term_match": traffic_match,
            "ranking": ranking,
            "detail": detail,
            "sales_trend": sales,
            "price_trend": price,
            "rank_trend": product_rank,
        }
        organic_position = traffic_match.get("最近自然曝光位置", "")
        ad_position = traffic_match.get("最近广告曝光位置", "")
        fallback_rank = extract_keyword_rank(ranking)
        keyword_rank = first_non_empty(organic_position, ad_position, fallback_rank)
        # Keyword traffic metrics must come from the ASIN's own traffic-term row.
        # Do not fall back to generic keyword/search-result data here, otherwise
        # the ABA/search-volume/traffic-share values may no longer correspond to
        # this specific ASIN + keyword pair.
        traffic_share = find_value(traffic_match, TRAFFIC_SHARE_KEYS)
        aba_rank = find_value(traffic_match, ABA_RANK_KEYS)
        search_volume = find_value(traffic_match, SEARCH_VOLUME_KEYS)
        price_value = first_non_empty(detail_metrics.get("price"), extract_latest_number(price), find_value(detail, PRICE_KEYS))
        coupon_value = first_non_empty(detail_metrics.get("coupon_value"), find_value(detail, COUPON_KEYS), find_value(price, COUPON_KEYS))
        coupon_type = first_non_empty(detail_metrics.get("coupon_type"), classify_coupon(coupon_value))
        deal_price = first_non_empty(detail_metrics.get("deal_price"), find_value(detail, DEAL_PRICE_KEYS), find_value(price, DEAL_PRICE_KEYS))
        deal_status = first_non_empty(detail_metrics.get("deal_status"), find_value(detail, DEAL_STATUS_KEYS), "是" if deal_price else "否")
        prime_discount_price = first_non_empty(detail_metrics.get("prime_discount_price"), find_value(detail, PRIME_PRICE_KEYS), find_value(price, PRIME_PRICE_KEYS))
        sales_value = first_non_empty(detail_metrics.get("estimated_sales"), extract_latest_number(sales), find_value(detail, SALES_KEYS))
        rank_value = first_non_empty(detail_metrics.get("product_rank"), extract_latest_number(product_rank), find_value(detail, RANK_KEYS))
        rating = first_non_empty(detail_metrics.get("rating"), find_value(detail, RATING_KEYS))
        review_count = first_non_empty(detail_metrics.get("review_count"), find_value(detail, REVIEW_KEYS))

        if needs_cli_fallback(
            organic_position,
            ad_position,
            price_value,
            sales_value,
            rank_value,
            rating,
            review_count,
        ):
            cli_keyword = cli_asin_keyword_match(asin, keyword, site)
            cli_detail = cli_product_detail(asin, site)
            raw["cli_traffic_term_match"] = cli_keyword
            raw["cli_detail"] = cli_detail

            organic_position = first_non_empty(organic_position, cli_keyword.get("SearchPosition", ""))
            organic_time = first_non_empty(
                traffic_match.get("最近自然曝光时间", ""),
                cli_keyword.get("searchPositionDate", ""),
            )
            ad_position = first_non_empty(ad_position, cli_keyword.get("AdPosition", ""))
            ad_time = first_non_empty(
                traffic_match.get("最近广告曝光时间", ""),
                cli_keyword.get("AdPositionDate", ""),
            )
            keyword_rank = first_non_empty(organic_position, ad_position, fallback_rank)
            price_value = first_non_empty(price_value, find_value(cli_detail, PRICE_KEYS))
            sales_value = first_non_empty(sales_value, find_value(cli_detail, SALES_KEYS))
            rank_value = first_non_empty(rank_value, find_value(cli_detail, RANK_KEYS))
            traffic_share = first_non_empty(traffic_share, find_value(cli_keyword, TRAFFIC_SHARE_KEYS))
            aba_rank = first_non_empty(aba_rank, find_value(cli_keyword, ABA_RANK_KEYS))
            search_volume = first_non_empty(search_volume, find_value(cli_keyword, SEARCH_VOLUME_KEYS))
            coupon_value = first_non_empty(coupon_value, find_value(cli_detail, COUPON_KEYS))
            coupon_type = first_non_empty(coupon_type, classify_coupon(coupon_value))
            deal_price = first_non_empty(deal_price, find_value(cli_detail, DEAL_PRICE_KEYS))
            deal_status = first_non_empty(deal_status, find_value(cli_detail, DEAL_STATUS_KEYS), "是" if deal_price else "否")
            prime_discount_price = first_non_empty(prime_discount_price, find_value(cli_detail, PRIME_PRICE_KEYS))
            rating = first_non_empty(rating, find_value(cli_detail, RATING_KEYS))
            review_count = first_non_empty(review_count, find_value(cli_detail, REVIEW_KEYS))
        else:
            organic_time = traffic_match.get("最近自然曝光时间", "")
            ad_time = traffic_match.get("最近广告曝光时间", "")

        found_any = any(
            value not in (None, "", [], {})
            for value in (keyword_rank, organic_position, ad_position, traffic_share, aba_rank, search_volume, price_value, coupon_value, deal_price, prime_discount_price, sales_value, rank_value, rating, review_count)
        )

        return {
            "keyword_rank": keyword_rank,
            "organic_position": organic_position,
            "organic_time": organic_time,
            "ad_position": ad_position,
            "ad_time": ad_time,
            "traffic_share": traffic_share,
            "aba_rank": aba_rank,
            "search_volume": search_volume,
            "price": price_value,
            "coupon_type": coupon_type,
            "coupon_value": coupon_value,
            "deal_status": deal_status,
            "deal_price": deal_price,
            "prime_discount_price": prime_discount_price,
            "estimated_sales": sales_value,
            "product_rank": rank_value,
            "rating": rating,
            "review_count": review_count,
            "product_url": amazon_product_url(asin, site),
            "status": "ok" if found_any else "not_found",
            "message": "" if found_any else summarize_sorftime_failure(raw),
            "raw": raw,
        }

    def find_in_traffic_terms(self, asin: str, keyword: str, site: str) -> dict[str, Any]:
        target = keyword.strip().casefold()
        for row in self.product_traffic_terms(asin, site):
            row_keyword = str(row.get("关键词", "")).strip().casefold()
            if row_keyword == target:
                return dict(row)
        return {}

    def product_traffic_terms(self, asin: str, site: str) -> list[dict[str, Any]]:
        cache_key = (asin.upper(), site)
        if cache_key in self._traffic_terms_cache:
            return self._traffic_terms_cache[cache_key]
        rows: list[dict[str, Any]] = []
        for page in range(1, 21):
            response = self.call_tool("product_traffic_terms", {"asin": asin, "page": page, "amzSite": site})
            page_rows = [row for row in collect_dict_rows(response) if isinstance(row, dict) and row.get("关键词")]
            if not page_rows:
                break
            rows.extend(page_rows)
            if len(page_rows) < 20:
                break
        self._traffic_terms_cache[cache_key] = rows
        return rows

    def product_detail(self, asin: str, site: str) -> Any:
        cache_key = (asin.upper(), site)
        if cache_key not in self._product_detail_cache:
            self._product_detail_cache[cache_key] = self.call_tool("product_detail", {"asin": asin, "amzSite": site})
        return self._product_detail_cache[cache_key]

    def product_trend(self, asin: str, trend_type: str, site: str) -> Any:
        cache_key = (asin.upper(), trend_type, site)
        if cache_key not in self._product_trend_cache:
            self._product_trend_cache[cache_key] = self.call_tool(
                "product_trend",
                {"asin": asin, "productTrendType": trend_type, "amzSite": site},
            )
        return self._product_trend_cache[cache_key]

    def find_in_keyword_results(self, asin: str, keyword: str, site: str) -> dict[str, Any]:
        target = asin.upper()
        for page in range(1, 6):
            rows = self.keyword_search_results(keyword, site, page)
            for index, row in enumerate(collect_dict_rows(rows), start=1):
                row_asin = str(find_value(row, {"ASIN", "asin"})).upper()
                if row_asin == target:
                    match = dict(row)
                    match.setdefault("rank", (page - 1) * 20 + index)
                    return match
        return {}

    def keyword_search_results(self, keyword: str, site: str, page: int) -> Any:
        cache_key = (keyword, site, page)
        if cache_key not in self._keyword_result_cache:
            self._keyword_result_cache[cache_key] = self.call_tool(
                "keyword_search_results",
                {"keyword": keyword, "page": page, "keywordSupportSite": site},
            )
        return self._keyword_result_cache[cache_key]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": int(datetime.now().timestamp() * 1000),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in response:
            raise RuntimeError(response["error"].get("message", f"Sorftime tool failed: {name}"))
        content = response.get("result", {}).get("content", [])
        return parse_tool_content(content)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "keyword-tracker", "version": "0.1"},
                },
            }
        )
        if "error" in response:
            raise RuntimeError(response["error"].get("message", "Sorftime MCP initialize failed."))
        self._initialized = True

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8", errors="replace")
        return parse_mcp_response(body)


def parse_mcp_response(body: str) -> dict[str, Any]:
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return json.loads(body)


def parse_tool_content(content: list[dict[str, Any]]) -> Any:
    if not content:
        return {}
    parsed_items: list[Any] = []
    for item in content:
        if item.get("type") == "text":
            text = item.get("text", "")
            try:
                parsed_items.append(json.loads(text))
            except json.JSONDecodeError:
                parsed_items.append(text)
        elif "data" in item:
            parsed_items.append(item["data"])
    if len(parsed_items) == 1:
        return parsed_items[0]
    return parsed_items


def normalize_external_result(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "keyword_rank": first_value(data, "keyword_rank", "rank", "organic_rank", "keywordRank"),
        "organic_position": first_value(data, "organic_position", "natural_position", "organicRank", "naturalRank"),
        "organic_time": first_value(data, "organic_time", "natural_time"),
        "ad_position": first_value(data, "ad_position", "ads_position", "adRank"),
        "ad_time": first_value(data, "ad_time", "ads_time"),
        "traffic_share": first_value(data, "traffic_share", "flow_share", "trafficShare", "click_share"),
        "aba_rank": first_value(data, "aba_rank", "abaRank", "aba_search_frequency_rank", "search_frequency_rank"),
        "search_volume": first_value(data, "search_volume", "searchVolume", "monthly_search_volume"),
        "price": first_value(data, "price", "current_price", "buybox_price"),
        "coupon_type": first_value(data, "coupon_type", "couponType"),
        "coupon_value": first_value(data, "coupon_value", "coupon", "couponValue"),
        "deal_status": first_value(data, "deal_status", "is_deal", "dealStatus"),
        "deal_price": first_value(data, "deal_price", "lightning_deal_price", "dealPrice"),
        "prime_discount_price": first_value(data, "prime_discount_price", "prime_price", "primePrice"),
        "estimated_sales": first_value(data, "estimated_sales", "sales", "monthly_sales", "daily_sales"),
        "product_rank": first_value(data, "product_rank", "bsr", "best_seller_rank", "category_rank"),
        "rating": first_value(data, "rating", "link_rating", "review_rating"),
        "review_count": first_value(data, "review_count", "reviews", "rating_count", "ratings"),
        "product_url": first_value(data, "product_url", "url", "link"),
        "status": data.get("status", "ok"),
        "message": data.get("message", ""),
        "raw": data,
    }


def first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return ""


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}) and not is_error_text(value):
            return value
    return ""


def load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_sorftime_client() -> SorftimeClient:
    load_dotenv()
    mcp_url = os.environ.get("SORFTIME_MCP_URL", "").strip()
    if mcp_url:
        return SorftimeMcpClient(mcp_url)

    command = os.environ.get("SORFTIME_CAPTURE_COMMAND", "").strip()
    if command:
        return ExternalSorftimeClient(command)
    return DemoSorftimeClient()


def capture_batch(
    client: SorftimeClient,
    asins: list[str],
    keywords: list[str],
    marketplace: str,
) -> list[dict[str, Any]]:
    captured_at = datetime.now().isoformat(timespec="seconds")
    capture_date = datetime.now().date().isoformat()
    records: list[dict[str, Any]] = []

    for asin in asins:
        for keyword in keywords:
            try:
                result = client.capture_keyword(asin, keyword, marketplace)
            except Exception as exc:
                result = {
                    "keyword_rank": "",
                    "price": "",
                    "traffic_share": "",
                    "aba_rank": "",
                    "search_volume": "",
                    "coupon_type": "",
                    "coupon_value": "",
                    "deal_status": "",
                    "deal_price": "",
                    "prime_discount_price": "",
                    "estimated_sales": "",
                    "product_rank": "",
                    "status": "failed",
                    "message": str(exc),
                    "raw": {},
                }
            records.append(
                {
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
                    "traffic_share": result.get("traffic_share", ""),
                    "aba_rank": result.get("aba_rank", ""),
                    "search_volume": result.get("search_volume", ""),
                    "price": result.get("price", ""),
                    "coupon_type": result.get("coupon_type", ""),
                    "coupon_value": result.get("coupon_value", ""),
                    "deal_status": result.get("deal_status", ""),
                    "deal_price": result.get("deal_price", ""),
                    "prime_discount_price": result.get("prime_discount_price", ""),
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
    return records


def normalize_marketplace(marketplace: str) -> str:
    value = (marketplace or "US").upper()
    if value == "UK":
        return "GB"
    return value


TRAFFIC_SHARE_KEYS = {
    "关键词流量占比", "流量占比", "流量占比%", "点击份额", "点击占比", "流量份额",
    "自然流量占比", "广告流量占比", "流量比例", "流量贡献", "traffic_share",
    "trafficShare", "flowShare", "flow_share", "clickShare", "click_share", "share", "占比",
    "TrafficShare", "ClickShare", "FlowShare",
}
ABA_RANK_KEYS = {
    "ABA热度排名", "ABA排名", "ABA", "ABA Rank", "ABA Rank 排名", "aba_rank", "abaRank",
    "searchFrequencyRank", "search_frequency_rank", "SearchFrequencyRank", "关键词热度排名",
    "搜索频率排名", "Search Frequency Rank", "SFR",
}
SEARCH_VOLUME_KEYS = {
    "搜索量", "月搜索量", "关键词搜索量", "search_volume", "searchVolume",
    "monthly_search_volume", "MonthlySearchVolume", "SearchVolume", "月搜索量预估",
    "searches", "Searches", "keywordSearchVolume",
}
COUPON_KEYS = {
    "优惠券", "coupon", "Coupon", "couponValue", "coupon_value", "couponAmount",
    "CouponAmount", "couponDiscount", "优惠券金额", "优惠券折扣", "couponPercent",
    "couponPercentage", "CouponPercent", "couponSavings", "coupon_savings",
}
DEAL_STATUS_KEYS = {"是否秒杀", "秒杀", "deal", "isDeal", "is_deal", "dealStatus", "DealStatus", "促销状态", "lightningDeal", "LightningDeal"}
DEAL_PRICE_KEYS = {
    "秒杀价格", "秒杀价", "lightningDealPrice", "lightning_deal_price",
    "dealPrice", "DealPrice", "flashDealPrice", "促销价", "LDPrice", "LightningDealPrice",
}
PRIME_PRICE_KEYS = {
    "Prime专享价", "Prime价格", "Prime折扣价", "primePrice", "prime_price",
    "prime_discount_price", "PrimeDiscountPrice", "primeExclusivePrice",
    "primeExclusiveDiscountPrice", "PrimeExclusiveDiscountPrice",
}

PRICE_KEYS = {
    "price",
    "currentPrice",
    "current_price",
    "buyBoxPrice",
    "buybox_price",
    "salePrice",
    "SalesPrice",
    "ListingSalesPrice",
}
SALES_KEYS = {
    "本产品月销量",
    "sales",
    "monthSales",
    "monthlySales",
    "month_sales_volume",
    "monthly_sales",
    "salesVolume",
    "ListingSalesVolumeOfMonth",
    "MonthSaleVolume",
    "SalesVolume",
}
RANK_KEYS = {
    "产品排名",
    "大类排名",
    "rank",
    "bsr",
    "productRank",
    "categoryRank",
    "subcategorySalesVolumeRank",
    "bestSellerRank",
    "CategoryRank",
    "SubcategorySalesVolumeRank",
    "SalesRank",
}
RATING_KEYS = {
    "星级",
    "rating",
    "ratings",
    "reviewRating",
    "linkRating",
    "Rating",
    "Star",
}
REVIEW_KEYS = {
    "评论数",
    "评价数量",
    "review_count",
    "reviews",
    "ratingCount",
    "reviewCount",
    "Ratings",
    "ReviewCount",
}
KEYWORD_RANK_KEYS = {
    "关键词排名",
    "自然排名",
    "rank",
    "position",
    "keywordRank",
    "organicRank",
    "naturalRank",
    "ranking",
}
VALUE_KEYS = {"value", "val", "dataValue", "trendValue", "rank", "price", "sales"}
PRICE_KEYS.add("价格")
VALUE_KEYS.add("价格")
VALUE_KEYS.add("销量")
VALUE_KEYS.add("月销量")
DATE_KEYS = {"date", "time", "recordDate", "captureDate", "exposureTime", "statDate"}


def parse_product_detail(detail: Any) -> dict[str, Any]:
    text = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
    coupon_value = first_non_empty(
        regex_first_text(text, r"优惠券[:：]\s*([^,，;；\n]+)"),
        regex_first_text(text, r"coupon[:：]\s*([^,，;；\n]+)"),
    )
    return {
        "price": regex_first(text, r"价格：([0-9]+(?:\.[0-9]+)?)"),
        "coupon_value": coupon_value,
        "coupon_type": classify_coupon(coupon_value),
        "deal_status": first_non_empty(regex_first_text(text, r"是否秒杀[:：]\s*([^,，;；\n]+)"), "是" if regex_first(text, r"秒杀(?:价格|价)?[:：]\s*([0-9]+(?:\.[0-9]+)?)") else ""),
        "deal_price": regex_first(text, r"秒杀(?:价格|价)?[:：]\s*([0-9]+(?:\.[0-9]+)?)"),
        "prime_discount_price": regex_first(text, r"Prime(?:专享价|价格|折扣价)[:：]\s*([0-9]+(?:\.[0-9]+)?)"),
        "rating": regex_first(text, r"星级：([0-9]+(?:\.[0-9]+)?)"),
        "review_count": regex_first(text, r"评论数：([0-9,]+)"),
        "estimated_sales": regex_first(text, r"月销量：(?:月销量：)?([0-9,]+)"),
        "product_rank": regex_first(text, r"所属大类：.*?排名:([0-9,]+)"),
    }


def regex_first(text: str, pattern: str) -> str:
    match = __import__("re").search(pattern, text)
    if not match:
        return ""
    return match.group(1).replace(",", "")


def regex_first_text(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def classify_coupon(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value)
    if "%" in text or "percent" in text.lower() or "折" in text:
        return "百分比"
    if re.search(r"[$€£￥¥]|\bUSD\b|\bEUR\b|\bGBP\b|\d+(?:\.\d+)?\s*(?:off|减|元)", text, re.I):
        return "金额"
    return "其他"


def amazon_product_url(asin: str, site: str) -> str:
    domains = {
        "US": "amazon.com",
        "GB": "amazon.co.uk",
        "DE": "amazon.de",
        "FR": "amazon.fr",
        "IT": "amazon.it",
        "ES": "amazon.es",
        "CA": "amazon.ca",
        "JP": "amazon.co.jp",
        "MX": "amazon.com.mx",
        "AU": "amazon.com.au",
        "BR": "amazon.com.br",
        "AE": "amazon.ae",
        "SA": "amazon.sa",
        "IN": "amazon.in",
    }
    return f"https://www.{domains.get(site, 'amazon.com')}/dp/{asin}"


def extract_keyword_rank(data: Any) -> Any:
    if isinstance(data, dict):
        direct = find_value(data, KEYWORD_RANK_KEYS)
        if direct not in (None, ""):
            return direct
    latest = latest_record(data)
    if isinstance(latest, dict):
        value = find_value(latest, KEYWORD_RANK_KEYS)
        if value not in (None, ""):
            return value
    return ""


def extract_latest_number(data: Any) -> Any:
    series_value = parse_latest_series_value(data)
    if series_value not in (None, ""):
        return series_value
    latest = latest_record(data)
    if isinstance(latest, dict):
        value = find_value(latest, VALUE_KEYS)
        if value not in (None, ""):
            return parse_latest_series_value(value) or value
    if isinstance(latest, (int, float, str)):
        return parse_latest_series_value(latest) or latest
    return ""


def latest_record(data: Any) -> Any:
    rows = collect_dict_rows(data)
    if not rows:
        return data
    rows.sort(key=lambda item: str(find_value(item, DATE_KEYS) or ""), reverse=True)
    return rows[0]


def collect_dict_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows: list[dict[str, Any]] = []
        for item in data:
            rows.extend(collect_dict_rows(item))
        return rows
    if isinstance(data, dict):
        child_rows: list[dict[str, Any]] = []
        for value in data.values():
            if isinstance(value, list):
                child_rows.extend(collect_dict_rows(value))
        if child_rows:
            return child_rows
        return [data]
    return []


def find_value(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and value not in (None, "") and not is_error_text(value):
                return value
        for value in data.values():
            found = find_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_value(item, keys)
            if found not in (None, ""):
                return found
    return ""


def is_error_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(
        marker in lowered
        for marker in (
            "未查询到",
            "not found",
            "no data",
            "no result",
            "error",
            "failed",
            "authentication required",
            "unauthorized",
            "请求数量不足",
            "requestleft",
            "code\": 694",
        )
    )


def parse_latest_series_value(data: Any) -> Any:
    if isinstance(data, dict):
        for value in data.values():
            parsed = parse_latest_series_value(value)
            if parsed not in (None, ""):
                return parsed
        return ""
    if isinstance(data, list):
        for item in data:
            parsed = parse_latest_series_value(item)
            if parsed not in (None, ""):
                return parsed
        return ""
    if not isinstance(data, str) or "=" not in data:
        return ""

    points: list[tuple[str, str]] = []
    for raw_part in data.replace("，", ",").split(","):
        if "=" not in raw_part:
            continue
        label, value = raw_part.split("=", 1)
        label = label.strip()
        value = value.strip()
        if label and value:
            points.append((label, value))
    if not points:
        return ""
    points.sort(key=lambda pair: pair[0])
    return points[-1][1]


def needs_cli_fallback(*values: Any) -> bool:
    return any(is_error_text(value) for value in values) or all(
        value in (None, "", [], {}) or is_error_text(value) for value in values
    )


def cli_product_detail(asin: str, site: str) -> dict[str, Any]:
    return cli_api("ProductRequest", {"asin": asin}, site)


def cli_asin_keyword_match(asin: str, keyword: str, site: str) -> dict[str, Any]:
    result = cli_api("ASINRequestKeywordv2", {"asin": asin, "pageIndex": 1, "pageSize": 100}, site)
    target = keyword.strip().casefold()
    for row in collect_dict_rows(result):
        row_keyword = find_value(row, {"keyword", "Keyword", "关键词"})
        if str(row_keyword).strip().casefold() == target:
            return row
    return {}


def cli_api(endpoint: str, params: dict[str, Any], site: str) -> dict[str, Any]:
    cli_path = os.environ.get("SF_CLI_PATH") or shutil.which("sorftime.cmd") or shutil.which("sorftime")
    if not cli_path:
        return {"_sf_error": "sorftime CLI not found"}
    profile = ensure_cli_profile(cli_path)
    cmd = [
        cli_path,
        "api",
        endpoint,
        json.dumps(params, ensure_ascii=False, separators=(",", ":")),
        "--domain",
        str(domain_for_site(site)),
    ]
    if profile:
        cmd.extend(["--profile", profile])
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return {"_sf_error": str(exc)}
    stdout = decode_process_bytes(completed.stdout)
    stderr = decode_process_bytes(completed.stderr)
    if completed.returncode != 0 and not stdout:
        return {"_sf_error": stderr or f"sorftime CLI failed: {completed.returncode}"}
    data = parse_cli_json(stdout)
    if isinstance(data, dict) and data.get("Code") not in (None, 0):
        return {"_sf_error": data.get("Message") or f"Code {data.get('Code')}", "_sf_response": data}
    if isinstance(data, dict) and "Data" in data:
        return data.get("Data") or {}
    return data if isinstance(data, dict) else {"_sf_response": data}


def ensure_cli_profile(cli_path: str) -> str:
    global _CLI_PROFILE_READY
    profile = os.environ.get("SORFTIME_CLI_PROFILE", "").strip() or "codex"
    account_sk = os.environ.get("SORFTIME_ACCOUNT_SK", "").strip()
    if _CLI_PROFILE_READY or not account_sk:
        return profile

    try:
        subprocess.run(
            [cli_path, "add", profile, account_sk],
            capture_output=True,
            timeout=60,
            check=False,
        )
        subprocess.run(
            [cli_path, "use", profile],
            capture_output=True,
            timeout=60,
            check=False,
        )
    finally:
        _CLI_PROFILE_READY = True
    return profile


def decode_process_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_cli_json(stdout: str) -> Any:
    clean = re.sub(r"\x1b\[[0-9;]*m", "", stdout)
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", clean)
    if not match:
        return {"_sf_error": clean.strip()}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {"_sf_error": clean.strip()}


def domain_for_site(site: str) -> int:
    return {
        "US": 1,
        "GB": 2,
        "UK": 2,
        "DE": 3,
        "FR": 4,
        "IN": 5,
        "CA": 6,
        "JP": 7,
        "ES": 8,
        "IT": 9,
        "MX": 10,
        "AE": 11,
        "AU": 12,
        "BR": 13,
        "SA": 14,
    }.get(site.upper(), 1)


def summarize_sorftime_failure(raw: dict[str, Any]) -> str:
    messages: list[str] = []
    for value in raw.values():
        collect_error_messages(value, messages)
    return "; ".join(messages) or "Sorftime did not return matching ranking or product metrics."


def collect_error_messages(value: Any, messages: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"_sf_error", "Message", "message", "msg", "error"} and item not in (None, ""):
                text = str(item)
                if text not in messages:
                    messages.append(text)
            else:
                collect_error_messages(item, messages)
    elif isinstance(value, list):
        for item in value:
            collect_error_messages(item, messages)
    elif isinstance(value, str) and is_error_text(value):
        if value not in messages:
            messages.append(value)
