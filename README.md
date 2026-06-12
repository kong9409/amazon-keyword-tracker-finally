# ASIN 关键词位置抓取工具

这是一个轻量网页版工具，用于批量输入或上传 ASIN 与关键词，通过 Sorftime MCP 抓取：

- 关键词最近自然位置、自然曝光时间
- 关键词最近广告位置、广告曝光时间
- ABA 热度排名、搜索量、关键词流量占比
- 当前价格、优惠券类型/优惠金额、秒杀价、Prime 专享/折扣价
- 月销量、大类排名、链接评分、评价数量、Amazon 产品链接

结果可下载为 Excel，也可以追加写入飞书表格。

## 本地启动

双击：

```text
start-keyword-tracker.cmd
```

打开：

```text
http://127.0.0.1:8766
```

停止工具：

```text
stop-keyword-tracker.cmd
```

也可以手动启动：

```powershell
& "C:\Users\EDY\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\app.py
```

## 输入方式

- ASIN：手动每行一个、逗号分隔，或上传 `.xlsx` / `.csv` / `.txt`
- 关键词：手动每行一个、多行粘贴，或上传 `.xlsx` / `.csv` / `.txt`
- 页面里的“模板”链接可以下载对应 Excel 模板

工具会对 ASIN 和关键词做笛卡尔组合，例如 2 个 ASIN × 5 个关键词 = 10 条抓取任务。

## Sorftime 配置

本地 `.env` 需要配置：

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的key
```

没有配置时，工具会退回演示数据，便于测试页面流程。

## Zeabur 部署

项目已包含：

- `Dockerfile`
- `requirements.txt`
- `zeabur.json`
- `.dockerignore`

部署到 Zeabur 后，在服务环境变量里配置：

```text
SORFTIME_MCP_URL=https://mcp.sorftime.com?key=你的key
HOST=0.0.0.0
PORT=8766
```

如果 Zeabur 自动分配 `PORT`，保留 Zeabur 提供的值即可；代码会优先读取 `PORT`。

## 输出字段

Excel 和历史记录包含：

```text
日期、抓取时间、站点、ASIN、关键词、关键词流量占比、ABA热度排名、搜索量、
最近自然位置、自然曝光时间、最近广告位置、广告曝光时间、最新曝光位置、
当前价格、优惠券类型、优惠券优惠、是否秒杀、秒杀价格、Prime专享价/折扣价、
月销量、大类排名、链接评分、评价数量、产品链接、数据源、状态、备注
```

自然/广告位置来自 Sorftime `product_traffic_terms`；产品价格、销量、排名、评分和评价数量来自 Sorftime 产品详情与趋势接口。


## 本次优化说明

- Excel 输出统一靠左，使用 Microsoft YaHei / PingFang SC 优先字体，不再自动换行。
- Excel 结果会按“关键词流量占比”降序排列，便于优先查看高流量关键词。
- 新增字段：ABA热度排名、搜索量、关键词流量占比、优惠券类型、优惠券优惠、是否秒杀、秒杀价格、Prime专享价/折扣价。
- 以上新增字段会优先从 Sorftime MCP 的产品流量词、产品详情、价格趋势等返回内容中自动识别；若 Sorftime 暂无对应字段，则该列为空。


## 飞书多维表写入

Zeabur 环境变量需要添加：

```text
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

页面里只需要填写飞书多维表 base 链接，工具会自动解析 app_token 和 table_id。
