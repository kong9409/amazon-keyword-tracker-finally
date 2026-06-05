# Zeabur 部署说明

## 必填环境变量

```text
SORFTIME_ACCOUNT_SK=你的 Sorftime Account-SK
SORFTIME_CLI_PROFILE=codex
SF_CLI_PATH=sorftime
HOST=0.0.0.0
PORT=8766
```

如果你已经有可用的 Sorftime MCP 地址，也可以补充：

```text
SORFTIME_MCP_URL=你的 Sorftime MCP 地址
```

## 部署方式

1. 在 Zeabur 创建服务，选择从代码或压缩包部署。
2. 上传本目录文件或上传打包好的 zip。
3. 在 Zeabur 服务环境变量里填上上面的变量。
4. 构建时 Dockerfile 会自动安装 Python 依赖和 `sorftime-cli`。

部署包不会包含 `.env`、历史数据库、导出结果、本地解压的 CLI 文件。
