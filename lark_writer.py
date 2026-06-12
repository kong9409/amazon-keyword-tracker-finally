from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

FEISHU_OPEN_BASE = os.environ.get("FEISHU_OPEN_BASE", "https://open.feishu.cn").rstrip("/")


def append_records_to_lark(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    columns: list[tuple[str, str]],
) -> dict[str, Any]:
    """Append records to a Feishu/Lark Bitable table.

    This Zeabur/Linux implementation does NOT call lark-cli. It uses the
    official Feishu OpenAPI directly, so it works inside containers.
    """
    if not records:
        return {"ok": True, "message": "没有需要写入的记录"}

    # Page-entered credentials take priority. Environment variables are only a
    # fallback for private/internal deployments. Do not log or return the secret.
    app_id = (config.get("feishu_app_id") or os.environ.get("FEISHU_APP_ID", "")).strip()
    app_secret = (config.get("feishu_app_secret") or os.environ.get("FEISHU_APP_SECRET", "")).strip()
    if not app_id or not app_secret:
        return {
            "ok": False,
            "message": "请在页面填写飞书 App ID 和 App Secret，或在部署环境变量中配置 FEISHU_APP_ID / FEISHU_APP_SECRET。",
        }

    parsed = parse_bitable_config(config)
    app_token = parsed.get("app_token", "")
    table_id = parsed.get("table_id", "")
    if not app_token or not table_id:
        return {
            "ok": False,
            "message": "请填写飞书多维表链接，或分别填写 app_token 与 table_id。链接格式应包含 /base/<app_token>?table=<table_id>。",
        }

    try:
        token = get_tenant_access_token(app_id, app_secret)
        existing_fields = list_bitable_fields(token, app_token, table_id)
        if not existing_fields:
            return {
                "ok": False,
                "message": "未读取到飞书多维表字段。请确认应用已被添加到该多维表，且拥有 bitable 读写权限。",
            }

        field_names = {field.get("field_name", "") for field in existing_fields}
        usable_columns = [(key, label) for key, label in columns if label in field_names]
        missing_labels = [label for _, label in columns if label not in field_names]
        if not usable_columns:
            return {
                "ok": False,
                "message": "飞书表中没有找到可写入字段。请至少创建这些字段：日期、抓取时间、站点、ASIN、关键词。",
                "available_fields": sorted(field_names),
            }

        total = 0
        for batch in chunked(records, 500):
            payload = {
                "records": [
                    {
                        "fields": {
                            label: stringify_for_bitable(record.get(key, ""))
                            for key, label in usable_columns
                            if stringify_for_bitable(record.get(key, "")) != ""
                        }
                    }
                    for record in batch
                ]
            }
            # Drop fully empty rows defensively.
            payload["records"] = [row for row in payload["records"] if row["fields"]]
            if not payload["records"]:
                continue
            response = feishu_request(
                "POST",
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                token=token,
                body=payload,
            )
            if response.get("code") != 0:
                return {
                    "ok": False,
                    "message": response.get("msg") or "飞书多维表写入失败",
                    "response": response,
                }
            total += len(payload["records"])

        return {
            "ok": True,
            "message": f"已写入飞书多维表 {total} 行。",
            "records": total,
            "app_token": mask_token(app_token),
            "table_id": table_id,
            "ignored_missing_fields": missing_labels,
        }
    except Exception as exc:
        return {"ok": False, "message": f"飞书写入异常：{exc}"}


def parse_bitable_config(config: dict[str, Any]) -> dict[str, str]:
    url = (
        config.get("base_url")
        or config.get("bitable_url")
        or config.get("spreadsheet_url")
        or ""
    ).strip()
    app_token = (
        config.get("app_token")
        or config.get("spreadsheet_token")
        or config.get("base_token")
        or ""
    ).strip()
    table_id = (
        config.get("table_id")
        or config.get("sheet_id")
        or ""
    ).strip()

    if url:
        parsed = urllib.parse.urlparse(url)
        # /base/<app_token> or /wiki/<node_token> (this tool supports base token directly)
        match = re.search(r"/(?:base|bitable)/([^/?#]+)", parsed.path)
        if match:
            app_token = match.group(1)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("table"):
            table_id = query["table"][0]

    # Users sometimes type the visible Chinese table name into sheet_id; ignore it.
    if table_id and not table_id.startswith("tbl"):
        table_id = ""

    return {"app_token": app_token, "table_id": table_id}


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    response = feishu_request(
        "POST",
        "/open-apis/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
        token=None,
    )
    if response.get("code") != 0:
        raise RuntimeError(response.get("msg") or "获取 tenant_access_token 失败")
    token = response.get("tenant_access_token")
    if not token:
        raise RuntimeError("飞书没有返回 tenant_access_token")
    return token


def list_bitable_fields(token: str, app_token: str, table_id: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    page_token = ""
    while True:
        query = "page_size=100"
        if page_token:
            query += "&page_token=" + urllib.parse.quote(page_token)
        response = feishu_request(
            "GET",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields?{query}",
            token=token,
        )
        if response.get("code") != 0:
            raise RuntimeError(response.get("msg") or "读取飞书字段失败")
        data = response.get("data", {})
        fields.extend(data.get("items", []) or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
        if not page_token:
            break
    return fields


def feishu_request(method: str, path: str, token: str | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = FEISHU_OPEN_BASE + path
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(f"Feishu HTTP {exc.code}: {text[:500]}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Feishu 返回非 JSON：{text[:500]}") from exc


def stringify_for_bitable(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def mask_token(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "***" + value[-4:]
