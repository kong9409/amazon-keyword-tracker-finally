# Zeabur 部署步骤

1. 解压项目，将内部文件直接覆盖到 GitHub 仓库根目录。
2. 确认根目录存在 `Dockerfile`、`app.py`、`sorftime_adapter.py`、`lark_writer.py`、`static/`。
3. Zeabur Variable 中删除手工创建的：

```text
APP_MODE
HOST
PORT
python app.py
SORFTIME_MCP_URL
SORFTIME_API_KEY
```

`python app.py` 是启动命令，不是变量名。新版 Dockerfile 已包含启动命令。

4. 在 Zeabur 点击 Redeploy。
5. 打开 `/api/health`，确认返回 `ok: true` 和 `supports_cli: true`。
6. 回到首页，由每个使用者自行输入 CLI Account-SK 或 MCP URL/Token。

## 飞书写入前准备

- 创建飞书企业自建应用。
- 开通多维表格读取、字段管理和记录写入权限。
- 发布应用版本。
- 把应用添加为目标 Base 的协作者。
- 在工具页面粘贴 App ID、App Secret、完整 Base 数据表链接。

## 数据仍为空时的排查顺序

1. 点击“测试连接”，确认 MCP 识别到 Amazon 工具。
2. 任务日志中不应再出现 `tiktok_product_detail`。
3. 先用 1 个 ASIN + 1 个关键词测试。
4. 检查 Amazon 站点是否正确。
5. 查看结果“备注”列，确认是接口无字段、关键词未匹配还是账户权限/额度问题。
