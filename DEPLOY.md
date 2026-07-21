# Zeabur 重新部署步骤

1. 下载并解压本项目。
2. 将解压后的所有文件覆盖到 GitHub 仓库根目录。
3. 在 Zeabur 的 **Variable** 页面删除手动创建的：
   - `APP_MODE`
   - `HOST`
   - `PORT`
   - `python app.py`
4. 不要添加公共 Sorftime Key。
5. 回到 Zeabur 服务页面，点击重新部署。
6. 部署完成后先打开 `/api/health` 检查服务。
7. 打开主页，选择 CLI 或 MCP，输入自己的连接信息后抓取。

Dockerfile 会自动：

- 安装 Python 依赖。
- 安装官方 `sorftime-cli`。
- 运行 `python app.py --no-browser`。
- 监听 Zeabur 自动注入的 `PORT`。
