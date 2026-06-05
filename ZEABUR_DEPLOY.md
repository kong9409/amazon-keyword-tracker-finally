# Zeabur 部署说明

## 必填环境变量

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的key
HOST=0.0.0.0
```

Zeabur 通常会自动注入 PORT，不建议手动固定 PORT。

## 部署方式

1. 在 Zeabur 创建服务，选择从代码或压缩包部署。
2. 上传本目录文件或上传打包好的 zip。
3. 在 Zeabur 服务环境变量里填上上面的变量。
4. 构建时 Dockerfile 只安装 Python 依赖；Sorftime 通过 MCP URL 调用，不再依赖浏览器或 sorftime-cli。

部署包不会包含 `.env`、历史数据库、导出结果、本地解压的 CLI 文件。
