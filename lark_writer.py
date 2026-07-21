from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any


def append_records_to_lark(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    field_columns: list[tuple[str, str]],
) -> dict[str, Any]:
    app_id = (config.get("feishu_app_id") or os.getenv("FEISHU_APP_ID", "")).strip()
    app_secret = (config.get("feishu_app_secret") or os.getenv("FEISHU_APP_SECRET", "")).strip()
    base_url = (config.get("base_url") or config.get("bitable_url") or "").strip()
    app_token = (config.get("app_token") or config.get("base_token") or "").strip()
    table_id = (config.get("table_id") or "").strip()

    parsed_token, parsed_table = parse_bitable_url(base_url)
    app_token = app_token or parsed_token
    table_id = table_id or parsed_table

    if not all((app_id, app_secret, app_token, table_id)):
        return {
            "ok": False,
            "message": "飞书配置不完整：需要 App ID、App Secret、Base 链接/Token 和 table_id。",
            "written": 0,
        }

    try:
        tenant_token = get_tenant_token(app_id, app_secret)
        written = 0
        for start in range(0, len(records), 500):
            batch = records[start : start + 500]
            payload = {
                "records": [
                    {
                        "fields": {
                            label: normalize_cell(record.get(key, ""))
                            for key, label in field_columns
                        }
                    }
                    for record in batch
                ]
            }
            url = (
                "https://open.feishu.cn/open-apis/bitable/v1/apps/"
                f"{urllib.parse.quote(app_token)}/tables/{urllib.parse.quote(table_id)}/records/batch_create"
            )
            response = request_json(
                url,
                payload,
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            if response.get("code") not in (0, None):
                raise RuntimeError(response.get("msg") or str(response))
            written += len(batch)
        return {"ok": True, "message": f"已写入飞书 {written} 条。", "written": written}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "written": 0}


def parse_bitable_url(url: str) -> tuple[str, str]:
    if not url:
        return "", ""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    table_id = (query.get("table") or query.get("table_id") or [""])[0]
    match = re.search(r"/(?:base|wiki)/([A-Za-z0-9_-]+)", parsed.path)
    app_token = match.group(1) if match else ""
    return app_token, table_id


def get_tenant_token(app_id: str, app_secret: str) -> str:
    response = request_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = response.get("tenant_access_token")
    if not token:
        raise RuntimeError(response.get("msg") or "获取飞书 tenant_access_token 失败")
    return token


def request_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    all_headers = {"Content-Type": "application/json; charset=utf-8"}
    all_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=all_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def normalize_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)
