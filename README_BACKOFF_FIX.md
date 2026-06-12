# Zeabur BackOff 修复说明

本版本修复容器启动阶段 BackOff 的常见原因：

1. 移除 Python `cgi` 标准库依赖，兼容 Python 3.13 和 Python 3.11。
2. 保留 Dockerfile 部署，默认使用 Python 3.11 slim。
3. 后端增加 `/api/health`，部署后可直接访问健康检查。
4. 前端使用异步任务接口 `/api/jobs`，避免长请求导致网关超时。

Zeabur 环境变量建议：

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的新key
HOST=0.0.0.0
```

不要手动设置 `PORT`，优先让 Zeabur 自动注入。
