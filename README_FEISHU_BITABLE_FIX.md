# 飞书多维表写入修复说明

本版本修复 Zeabur 中 `[Errno 2] No such file or directory: 'cmd'` 的问题。

原因：旧版使用 `cmd /c lark-cli` 写入飞书，只能在 Windows 本地运行；Zeabur 是 Linux 容器，没有 `cmd`。

新版改为直接调用飞书开放平台 Bitable API：

- 从飞书多维表链接自动解析 `app_token` 和 `table_id`
- 优先使用页面填写的 `飞书 App ID`、`飞书 App Secret` 获取 `tenant_access_token`
- 如果页面没填，再回退到 Zeabur 环境变量 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`
- 自动读取多维表字段，只写入表里已经存在的字段
- 如果字段缺失，不会整单失败，会在返回结果里提示 ignored_missing_fields

## Zeabur 环境变量

对外通用版只建议固定 Sorftime，不固定飞书凭证：

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的key
HOST=0.0.0.0
```

飞书 App ID / App Secret 由使用者在网页填写。内部专用部署时，也可以继续把 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 放在 Zeabur 环境变量里作为兜底。

## 页面填写方式

输出方式选择：`Excel + 飞书` 或 `只写入飞书`。

飞书多维表链接填写完整链接，例如：

```text
https://xxx.feishu.cn/base/UJqibn3pladdKes9UwbcQHi6n6g?table=tblIxKeDmJ429Adc&view=vewjenqwDH
```

`table_id` 可以留空，工具会自动从链接里的 `table=tbl...` 识别。

## 飞书权限要求

请确认：

1. 飞书开放平台自建应用已启用多维表相关权限。
2. 该应用已添加到目标多维表，或目标文档已授权给该应用。
3. 多维表内的字段名和工具导出的中文字段名一致，例如：日期、抓取时间、站点、ASIN、关键词、关键词流量占比、ABA热度排名、搜索量。
