from __future__ import annotations

import json
import subprocess
from typing import Any


def append_records_to_lark(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    columns: list[tuple[str, str]],
) -> dict[str, Any]:
    if not records:
        return {"ok": True, "message": "没有需要写入的记录"}

    spreadsheet_url = (config.get("spreadsheet_url") or "").strip()
    spreadsheet_token = (config.get("spreadsheet_token") or "").strip()
    sheet_id = (config.get("sheet_id") or "").strip()
    append_range = (config.get("append_range") or "").strip()

    if not spreadsheet_url and not spreadsheet_token:
        return {"ok": False, "message": "请填写飞书表格 URL 或 spreadsheet token"}
    if not sheet_id and not append_range:
        return {"ok": False, "message": "请填写 sheet_id 或追加范围"}

    values: list[list[Any]] = []
    if config.get("include_header"):
        values.append([label for _, label in columns])
    values.extend([[record.get(key, "") for key, _ in columns] for record in records])

    args = ["cmd", "/c", "lark-cli", "sheets", "+append", "--values", json.dumps(values, ensure_ascii=False)]
    if spreadsheet_url:
        args.extend(["--url", spreadsheet_url])
    else:
        args.extend(["--spreadsheet-token", spreadsheet_token])
    if sheet_id:
        args.extend(["--sheet-id", sheet_id])
    if append_range:
        args.extend(["--range", append_range])

    completed = subprocess.run(args, text=True, capture_output=True, timeout=120, check=False)
    return {
        "ok": completed.returncode == 0,
        "message": completed.stdout.strip() if completed.returncode == 0 else completed.stderr.strip(),
        "command": "lark-cli sheets +append",
    }
