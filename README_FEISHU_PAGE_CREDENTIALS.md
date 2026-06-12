# 飞书页面自填凭证版说明

本版本适合把工具发给不同公司/团队使用。飞书凭证不需要提前写进 Zeabur 环境变量，也不会硬编码到 GitHub 仓库里。

## 页面填写

当输出方式选择 `只写入飞书` 或 `Excel + 飞书` 时，页面会展开“飞书连接配置”，用户自行填写：

- 飞书 App ID
- 飞书 App Secret
- 飞书多维表链接
- table_id（可选，通常会自动从链接里的 `table=tbl...` 识别）

## 凭证优先级

1. 页面填写的 `飞书 App ID / App Secret` 优先。
2. 如果页面没填，才会回退到 Zeabur 环境变量 `FEISHU_APP_ID / FEISHU_APP_SECRET`。

## 安全处理

- App Secret 不写入 GitHub。
- App Secret 不写入 Excel。
- App Secret 不写入任务日志。
- App Secret 不返回给前端。
- App Secret 不持久化到后端任务 JSON 文件。
- 如果用户勾选“仅在当前浏览器记住”，凭证只保存在该用户当前浏览器的 localStorage 中。

## 对外部署建议

Zeabur 环境变量只需要配置：

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的SorftimeKey
HOST=0.0.0.0
```

飞书 App ID / Secret 由使用者在页面自行填写。
