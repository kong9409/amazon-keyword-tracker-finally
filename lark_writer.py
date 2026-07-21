from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

FEISHU_API = "https://open.feishu.cn/open-apis"


def append_records_to_lark(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    field_columns: list[tuple[str, str]],
) -> dict[str, Any]:
    """Append keyword tracker records to a Feishu Base table.

    Users only need to provide App ID, App Secret and a Base table link. A wiki
    link is resolved to the underlying Base app token. When the link does not
    include a table id, the first table in the Base is used. Missing tracker
    fields are created as text fields before records are written.
    """
    app_id = (config.get("feishu_app_id") or os.getenv("FEISHU_APP_ID", "")).strip()
    app_secret = (config.get("feishu_app_secret") or os.getenv("FEISHU_APP_SECRET", "")).strip()
    base_url = (
        config.get("base_url")
        or config.get("feishu_base_url")
        or config.get("bitable_url")
        or ""
    ).strip()
    app_token = (config.get("app_token") or config.get("base_token") or "").strip()
    table_id = (config.get("table_id") or "").strip()

    parsed = parse_bitable_url(base_url)
    app_token = app_token or parsed["app_token"]
    table_id = table_id or parsed["table_id"]
    wiki_token = parsed["wiki_token"]

    if not app_id or not app_secret:
        return {
            "ok": False,
            "message": "飞书配置不完整：请填写 App ID 和 App Secret。",
            "written": 0,
        }
    if not (base_url or app_token):
        return {
            "ok": False,
            "message": "飞书配置不完整：请粘贴 Base 数据表链接。",
            "written": 0,
        }

    try:
        tenant_token = get_tenant_token(app_id, app_secret)
        auth = {"Authorization": f"Bearer {tenant_token}"}

        if not app_token and wiki_token:
            app_token = resolve_wiki_app_token(wiki_token, auth)
        if not app_token:
            raise RuntimeError("无法从 Base 链接识别 app_token，请复制浏览器中的完整 Base 链接。")

        if not table_id:
            table_id = first_table_id(app_token, auth)
        if not table_id:
            raise RuntimeError("该 Base 中没有可写入的数据表，请先在飞书 Base 中新建一张表。")

        created_fields = ensure_fields(app_token, table_id, auth, field_columns)
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
                f"{FEISHU_API}/bitable/v1/apps/{quote(app_token)}"
                f"/tables/{quote(table_id)}/records/batch_create"
            )
            response = request_json(url, payload, headers=auth)
            assert_feishu_ok(response, "批量写入飞书记录失败")
            written += len(batch)

        detail = f"已写入飞书 {written} 条"
        if created_fields:
            detail += f"，并自动创建 {len(created_fields)} 个缺失字段"
        return {
            "ok": True,
            "message": detail + "。",
            "written": written,
            "app_token": app_token,
            "table_id": table_id,
            "created_fields": created_fields,
        }
    except Exception as exc:
        return {"ok": False, "message": explain_feishu_error(exc), "written": 0}


def parse_bitable_url(url: str) -> dict[str, str]:
    result = {"app_token": "", "wiki_token": "", "table_id": ""}
    if not url:
        return result
    parsed = urllib.parse.urlparse(url.strip())
    query = urllib.parse.parse_qs(parsed.query)
    result["table_id"] = (query.get("table") or query.get("table_id") or [""])[0]
    base_match = re.search(r"/base/([A-Za-z0-9_-]+)", parsed.path)
    wiki_match = re.search(r"/wiki/([A-Za-z0-9_-]+)", parsed.path)
    if base_match:
        result["app_token"] = base_match.group(1)
    elif wiki_match:
        result["wiki_token"] = wiki_match.group(1)
    return result


def get_tenant_token(app_id: str, app_secret: str) -> str:
    response = request_json(
        f"{FEISHU_API}/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = response.get("tenant_access_token")
    if not token:
        raise RuntimeError(response.get("msg") or "获取飞书 tenant_access_token 失败")
    return str(token)


def resolve_wiki_app_token(wiki_token: str, headers: dict[str, str]) -> str:
    query = urllib.parse.urlencode({"token": wiki_token})
    response = request_json(
        f"{FEISHU_API}/wiki/v2/spaces/get_node?{query}",
        method="GET",
        headers=headers,
    )
    assert_feishu_ok(response, "解析飞书 Wiki/Base 链接失败")
    node = (response.get("data") or {}).get("node") or {}
    obj_type = str(node.get("obj_type") or "").lower()
    app_token = str(node.get("obj_token") or "")
    if not app_token:
        raise RuntimeError("Wiki 链接已识别，但飞书未返回对应的 Base app_token。")
    if obj_type and obj_type not in {"bitable", "base"}:
        raise RuntimeError(f"该 Wiki 链接指向 {obj_type}，不是飞书多维表格 Base。")
    return app_token


def first_table_id(app_token: str, headers: dict[str, str]) -> str:
    response = request_json(
        f"{FEISHU_API}/bitable/v1/apps/{quote(app_token)}/tables?page_size=100",
        method="GET",
        headers=headers,
    )
    assert_feishu_ok(response, "读取飞书 Base 数据表列表失败")
    items = (response.get("data") or {}).get("items") or []
    for item in items:
        if isinstance(item, dict) and item.get("table_id"):
            return str(item["table_id"])
    return ""


def list_field_names(app_token: str, table_id: str, headers: dict[str, str]) -> set[str]:
    response = request_json(
        f"{FEISHU_API}/bitable/v1/apps/{quote(app_token)}/tables/{quote(table_id)}/fields?page_size=100",
        method="GET",
        headers=headers,
    )
    assert_feishu_ok(response, "读取飞书字段失败")
    items = (response.get("data") or {}).get("items") or []
    return {
        str(item.get("field_name"))
        for item in items
        if isinstance(item, dict) and item.get("field_name")
    }


def ensure_fields(
    app_token: str,
    table_id: str,
    headers: dict[str, str],
    field_columns: list[tuple[str, str]],
) -> list[str]:
    existing = list_field_names(app_token, table_id, headers)
    created: list[str] = []
    for _, label in field_columns:
        if label in existing:
            continue
        response = request_json(
            f"{FEISHU_API}/bitable/v1/apps/{quote(app_token)}/tables/{quote(table_id)}/fields",
            {"field_name": label, "type": 1},  # 1 = 文本
            headers=headers,
        )
        assert_feishu_ok(response, f"创建飞书字段“{label}”失败")
        existing.add(label)
        created.append(label)
    return created


def assert_feishu_ok(response: dict[str, Any], action: str) -> None:
    if response.get("code") not in (0, None):
        message = response.get("msg") or response.get("message") or str(response)
        raise RuntimeError(f"{action}：{message}")


def request_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "POST",
) -> dict[str, Any]:
    all_headers = {"Content-Type": "application/json; charset=utf-8"}
    all_headers.update(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
            message = detail.get("msg") or detail.get("message") or body
        except json.JSONDecodeError:
            message = body or str(exc)
        request_id = exc.headers.get("X-Tt-Logid", "") or exc.headers.get("X-Request-Id", "")
        path = urllib.parse.urlparse(url).path
        suffix = f"；request_id={request_id}" if request_id else ""
        raise RuntimeError(f"飞书接口 HTTP {exc.code}（{path}）：{message}{suffix}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接飞书开放平台：{exc.reason}") from exc


def explain_feishu_error(exc: Exception) -> str:
    text = str(exc)
    lower = text.lower()
    if "http 403" in lower or "1254302" in lower or "1254304" in lower or "forbidden" in lower:
        stage = "访问飞书 Base"
        if "/wiki/" in lower:
            stage = "解析 Wiki/Base 链接"
        elif "/fields" in lower:
            stage = "读取或创建飞书字段"
        elif "/records/batch_create" in lower:
            stage = "写入飞书记录"
        elif "/tables" in lower:
            stage = "读取飞书数据表"
        return (
            f"{stage}失败：飞书返回 403，无文档或角色权限。"
            "请完成三项设置：① 飞书开放平台给应用开通多维表格读写权限 bitable:app，"
            "发布版本并完成管理员审批；② 在目标 Base 右上角的协作者/添加应用中，"
            "把该 App ID 对应的应用加入并授予可编辑权限；③ 如果 Base 开启高级权限，"
            "把应用加入具有该数据表、字段和记录读写权限的角色或群。"
            "建议粘贴 /base/ 开头的直接 Base 链接，不要使用仅个人可见的 /wiki/ 快捷链接。"
            f" 原始错误：{text}"
        )
    if "http 401" in lower or "unauthorized" in lower:
        return "飞书鉴权失败：请检查 App ID、App Secret 是否属于同一个已启用的自建应用。原始错误：" + text
    if "wrongbasetoken" in lower or "basetokennotfound" in lower or "1254003" in lower or "1254040" in lower:
        return "飞书 Base 链接无法识别或已失效：请复制浏览器地址栏中的完整 /base/... 链接，并确认链接内 table 参数对应目标数据表。原始错误：" + text
    return text


def quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def normalize_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False)
