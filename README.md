# Amazon 关键词监控工具 by kong · V6.1 西柚洞察 MCP 版

部署在 Zeabur 的 Amazon 关键词监控工具。用户先选择数据源，再输入自己的 MCP / CLI / API 凭证、ASIN 和关键词，结果可下载 Excel、写入飞书，或同时输出。

## 支持的数据源

| 页面选项 | 连接方式 | 页面需要填写 |
|---|---|---|
| Sorftime | Sorftime CLI / Sorftime MCP | Account-SK，或 MCP URL + Token |
| 卖家精灵 | API | API Key；API Base URL 默认已填写 |
| SIF | MCP | MCP URL + MCP Key |
| 西柚洞察 | MCP（默认）/ OpenAPI V2 | MCP URL + Token，或 API Key |
| 其他软件 | 自定义 MCP / API | MCP URL + Token，或 API Endpoint + Key/Header |

选择不同软件时，页面只显示该软件的连接输入框。原来的“CLI / MCP”已明确改名为 **Sorftime CLI / Sorftime MCP**。

## 使用步骤

1. 在 STEP 1 选择数据源。
2. 填写该数据源的 MCP、CLI 或 API 凭证并测试连接。
3. 输入 ASIN 和关键词；关键词示例仅使用 `关键词1`、`关键词2`、`关键词3`。
4. 选择 Amazon 站点。
5. 选择下载 Excel、写入飞书，或两者同时执行。
6. 保持“每日 09:00 自动抓取（北京时间）”勾选，可保存当前数据源和任务配置。
7. 点击“开始抓取”。

## 各数据源字段组合

### Sorftime

保留现有严格指标映射：

- 流量占比：`product_traffic_terms`
- ABA热度、搜索量：`keyword_detail`
- 自然位、广告位：`keyword_search_results`，自然位再用关键词排名趋势兜底
- 价格、优惠券、秒杀价、Prime价、月销量、大类排名、评分、评价数：`product_detail`，月销量/排名按 `product_trend` 兜底

### 卖家精灵 API

- 反查流量词：`/v1/traffic/keyword`
- ABA与搜索量：`/v1/aba/research`
- 产品详情：`/v1/asin/{marketplace}/{asin}`
- 月销量兜底：`/v1/product/competitor-lookup`

### SIF MCP

程序调用 `tools/list`，按工具名称、描述和实时 `inputSchema` 自动识别：流量词、关键词详情、产品详情、排名和销量工具。SIF 后续修改命名空间时，无需在页面重新填写接口名。

### 西柚洞察 MCP / OpenAPI V2

MCP 为页面默认方式：

- MCP URL：`https://mcp.xydc.com/mcp`
- 鉴权：`Authorization: Bearer <MCP Token>`
- 程序通过 `initialize → tools/list → tools/call` 连接，并优先识别西柚的 ASIN 关键词、关键词详情、ASIN详情、关键词排名、订单趋势和 BSR 趋势工具。
- 工具名称变化时，继续使用实时 `tools/list` 和 `inputSchema` 动态匹配。

OpenAPI V2 仍可在页面切换使用：

- 反查关键词与流量占比：`/v1/asins/research/list/period`
- ABA与搜索量：`/v1/searchTerms/info`
- 产品详情：`/v1/asins/info`
- 30日订单/月销量：`/v1/asins/orders`
- BSR趋势：`/v1/asins/bsrInfo/trends/daily`

### 其他软件

- 自定义 MCP：读取 `tools/list` 并动态匹配 Amazon ASIN/关键词工具。
- 自定义 API：对 Endpoint 发送 JSON POST：

```json
{
  "asin": "B0XXXXXXXX",
  "keyword": "关键词1",
  "marketplace": "US"
}
```

返回字段可使用常见英文或中文名称，例如 `trafficShare`、`searchFrequencyRank`、`searchVolume`、`organicPosition`、`price`、`monthlySales`、`bsrRank`、`rating`、`reviewCount`。

## 飞书与 Excel

- 飞书输入：App ID、App Secret、Base 链接。
- 支持读取目标字段类型并转换，避免 `TextFieldConvFail`。
- 支持 Excel、飞书、Excel + 飞书三种输出方式。
- Excel“任务汇总”页显示数据接口总调用次数、各接口次数和耗时。

## 每日 09:00 自动抓取

- 固定北京时间 `Asia/Shanghai` 09:00。
- 会保存当前 ASIN、关键词、站点、数据源、输出方式与飞书配置。
- MCP/API/CLI 与飞书凭证会加密保存，不写入普通任务 JSON。
- Zeabur 必须挂载持久化卷：

```text
/app/data
```

## Zeabur 部署

将项目文件直接覆盖 GitHub 仓库根目录，确认至少存在：

```text
Dockerfile
app.py
provider_adapter.py
sorftime_adapter.py
lark_writer.py
requirements.txt
static/
```

Zeabur 不需要手动创建 `PORT`、`HOST`、`APP_MODE` 或 `python app.py` 变量。部署后检查：

```text
https://你的域名/api/health
```

## 测试

```bash
python -m unittest discover -s tests -v
node --check static/app.js
python -m py_compile app.py provider_adapter.py sorftime_adapter.py lark_writer.py
```

V6.1 使用模拟响应测试不同软件的字段解析、请求参数、客户端分发、凭证脱敏，以及西柚洞察 MCP 工具优先匹配；未把任何真实 Token 写入项目文件。
