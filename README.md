# Amazon Keyword Tracker · Zeabur 简化版

这是一个单一的 Zeabur 网页工具。使用者打开网页后：

1. 选择 **CLI** 或 **MCP**。
2. CLI 模式输入自己的 Sorftime `Account-SK`；MCP 模式输入 MCP URL 和 Bearer Token。
3. 输入 ASIN、关键词和 Amazon 站点。
4. 点击“开始抓取并导出”。
5. 页面显示进度、接口调用次数和运行时间，完成后自动下载 Excel。

## CLI 和 MCP 的含义

### CLI 模式

网页只要求输入 Sorftime `Account-SK`。Docker 容器内已经安装 `sorftime-cli`，后端只会执行固定命令：

```text
sorftime add keyword-tracker <Account-SK>
sorftime use keyword-tracker
sorftime api ASINRequestKeywordv2 ...
sorftime api ProductRequest ...
```

网页不会接受或执行用户填写的 Shell 命令。

### MCP 模式

默认 MCP 地址：

```text
https://mcp.sorftime.com/
```

用户填写自己的 Bearer Token / Account-SK。后端按照标准 MCP 流程初始化并调用 Sorftime 工具。

## Zeabur 部署

把项目文件直接放在 GitHub 仓库根目录，确保根目录存在：

```text
Dockerfile
app.py
sorftime_adapter.py
requirements.txt
static/
```

然后在 Zeabur 重新部署即可。

### Zeabur 变量

这个版本不需要手动新增以下变量：

```text
APP_MODE
HOST
PORT
python app.py
SORFTIME_MCP_URL
SORFTIME_API_KEY
```

特别注意：`python app.py` 是启动命令，不是环境变量。Dockerfile 已经包含启动命令；Zeabur 会自动提供 `PORT`，程序会监听 `0.0.0.0:$PORT`。

部署后访问：

```text
https://你的域名/api/health
```

正常返回应包含：

```json
{
  "ok": true,
  "mode": "hosted",
  "hosted": true,
  "supports_cli": true
}
```

## 输出字段

Excel 和网页固定显示：

```text
日期、ASIN、关键词、流量占比、ABA热度、搜索量、自然位、广告位、价格、优惠券、秒杀价、Prime价、月销量、大类排名、评分、评价数、链接
```

Excel 另有“任务汇总”工作表，包含接口调用总次数、运行时间、各接口调用次数与累计耗时。

## 数据接口

CLI 模式主要使用：

- `ASINRequestKeywordv2`：ASIN 关键词、流量占比、排名、搜索热度等。
- `ProductRequest`：价格、促销、销量、排名、评分和评价数等。

MCP 模式根据可用工具使用：

- `product_traffic_terms`
- `keyword_detail`
- `keyword_search_results`
- `product_ranking_trend_by_keyword`
- `product_detail`
- `product_report`
- `product_trend`

同一批任务会缓存关键词、搜索结果和产品数据，避免重复调用。

## 安全说明

- Account-SK、Token 和 MCP URL 不写入 GitHub。
- Zeabur 网页模式不把连接凭证保存到任务 JSON 或数据库。
- CLI 模式使用临时配置目录，任务结束后删除。
- 不支持用户输入任意 CLI/Shell 命令，避免远程命令执行风险。

## 测试

```bash
python -m unittest discover -s tests -v
node --check static/app.js
python -m py_compile app.py sorftime_adapter.py
```
