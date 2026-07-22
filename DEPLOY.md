# Zeabur 部署步骤 · V6.1

1. 解压项目，把内部文件直接覆盖到 GitHub 仓库根目录。
2. 确认存在 `Dockerfile`、`app.py`、`provider_adapter.py`、`sorftime_adapter.py`、`lark_writer.py` 和 `static/`。
3. Zeabur Variable 中不要手工创建 `PORT`、`HOST`、`APP_MODE`、`python app.py` 或任何公共数据源 Key。
4. 在 Volumes 中挂载持久化卷到 `/app/data`，用于每日 09:00 任务和加密凭证。
5. 点击 Redeploy。
6. 打开 `/api/health`，确认 `ok: true`、`supports_daily: true`。
7. 回到首页，由每位用户选择 Sorftime、卖家精灵、SIF、西柚洞察或其他软件并输入自己的凭证。

## 连接要求

- Sorftime CLI：容器已安装 `sorftime-cli`，用户只输入 Account-SK。
- Sorftime/SIF/其他 MCP：必须是 Zeabur 可访问的公网 HTTPS URL。
- 卖家精灵/西柚/其他 API：必须是公网 HTTPS API 地址。
- 数据源凭证不应配置成全站公共 Zeabur 环境变量。
