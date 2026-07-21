# Amazon 关键词监控工具 by kong

一个部署在 Zeabur 的 Amazon 关键词监控网页工具。每位使用者在页面自行选择 Sorftime **CLI** 或 **MCP**，输入 ASIN 和关键词后抓取数据，并选择：

- 下载 Excel
- 写入飞书 Base
- 下载 Excel + 写入飞书

## 本版修复

- 修复 MCP `product_detail` 被错误路由到 `tiktok_product_detail` 的问题。
- MCP 工具匹配会优先选择精确 Amazon 工具，并排除 TikTok、Temu、Shopee、Walmart 等平台前缀。
- 修复 CLI/MCP 切换后隐藏字段仍显示、输入框高度和边框不一致的问题。
- 工具名称统一为 **Amazon 关键词监控工具 by kong**。
- 增加 Excel、飞书、Excel + 飞书三种输出方式。
- 飞书只需输入 App ID、App Secret、Base 链接；工具可解析 Wiki/Base 链接、自动选择数据表并创建缺失字段。
- 保留 Sorftime 接口次数、运行时间、进度、结果预览和 Excel 任务汇总。

## 使用步骤

1. 选择 `CLI（Account-SK）` 或 `MCP（URL + Token）`。
2. 点击“测试连接”。
3. 输入一个或多个 ASIN、关键词。
4. 选择 Amazon 站点。
5. 选择输出方式。
6. 需要飞书时，填写 App ID、App Secret 和 Base 数据表链接。
7. 点击“开始抓取”。

## MCP 与 CLI 怎么选

当前 17 字段监控默认推荐 MCP：

```text
product_traffic_terms
keyword_detail
keyword_search_results（自然 positionType=0 / 广告 positionType=2）
product_ranking_trend_by_keyword
product_detail
product_report
product_trend
```

CLI 更适合大量批量采集，当前使用：

```text
ASINRequestKeywordv2
KeywordRequest
ProductRequest
```

完整字段对应见：

```text
MCP_CLI_FIELD_MAPPING.md
Amazon关键词监控_MCP_CLI字段对应表_by_kong.xlsx
```

## 飞书配置

企业自建应用至少需要开通多维表格读取/写入相关权限，并把应用添加为目标 Base 的协作者。页面填写：

```text
App ID
App Secret
Base 链接（建议复制到具体数据表，链接中包含 table=tbl...）
```

工具会：

1. 获取 tenant_access_token。
2. 如果粘贴的是 Wiki 链接，解析为 Base app_token。
3. 如果链接不含 table_id，选择 Base 中第一张表。
4. 检查字段并创建缺失字段。
5. 每批最多 500 条写入。

App Secret 不会写入任务 JSON。

## Zeabur 部署

把项目文件放到 GitHub 仓库根目录，确保存在：

```text
Dockerfile
app.py
sorftime_adapter.py
lark_writer.py
requirements.txt
static/
```

Zeabur 不需要手动设置 `APP_MODE`、`HOST`、`PORT` 或 `python app.py` 变量。Dockerfile 会启动应用，Zeabur 自动注入 `PORT`。

健康检查：

```text
https://你的域名/api/health
```

## 输出字段

```text
日期、ASIN、关键词、流量占比、ABA热度、搜索量、自然位、广告位、价格、优惠券、秒杀价、Prime价、月销量、大类排名、评分、评价数、链接
```

活动相关字段只有在 Sorftime 实际返回时才会写入；没有数据时保持空白并在备注中说明，不生成虚假值。

## 测试

```bash
python -m unittest discover -s tests -v
node --check static/app.js
python -m py_compile app.py sorftime_adapter.py lark_writer.py
```
