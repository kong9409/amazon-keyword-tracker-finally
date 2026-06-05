# Failed to fetch 修复说明

本版把原来的同步 `/api/capture` 改为异步任务：

1. 前端提交到 `/api/jobs`，马上返回任务 ID。
2. 后端在线程里调用 Sorftime MCP。
3. 前端每 1.5 秒轮询 `/api/jobs/{job_id}` 显示进度。
4. 任务完成后提供 Excel 下载链接。

这样可以避免 Zeabur 网关因为长连接、502 或后端重启导致前端直接显示 `TypeError: Failed to fetch`。

部署后先访问：

```text
/api/health
```

看到 `ok: true` 后再测试 1 个 ASIN + 1 个关键词。
