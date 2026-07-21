# Amazon 关键词监控工具 by kong｜MCP 与 CLI 字段对应

## 结论

这套 17 字段关键词监控，**默认推荐 MCP**。原因是自然位与广告位可以分别通过 `keyword_search_results(positionType=0/2)` 扫描当前结果页，并且可以使用 `product_report`、`product_trend` 等接口兜底。

当一次需要批量查询大量 ASIN × 关键词，主要目标是快速导出基础字段时，可选择 **CLI**。当前 CLI 组合为：

- `ASINRequestKeywordv2`：流量词、流量占比、自然位/广告位（接口返回时）
- `KeywordRequest`：ABA 热度、搜索量兜底
- `ProductRequest`：价格、活动价、销量、BSR、评分和评价数

> 优惠券、秒杀价、Prime 价以及 CLI 广告位属于“条件字段”，只有 Sorftime 当前站点和接口响应实际返回时才能写入，工具不会编造数据。

## 17 个字段一一对应

|字段|MCP 主接口|MCP 兜底|CLI 主命令|建议|
|---|---|---|---|---|
|日期|本地生成|—|本地生成|两者相同|
|ASIN|用户输入|—|用户输入|两者相同|
|关键词|用户输入/接口匹配|—|用户输入/接口匹配|两者相同|
|流量占比|`product_traffic_terms`|`product_report`|`ASINRequestKeywordv2`|都可|
|ABA热度|`keyword_detail`|流量词/报告关键词行|`KeywordRequest`|MCP 更稳|
|搜索量|`keyword_detail`|流量词/报告关键词行|`KeywordRequest`|都可|
|自然位|`keyword_search_results(positionType=0)`|`product_traffic_terms`、`product_ranking_trend_by_keyword`|`ASINRequestKeywordv2`|MCP 更适合监控|
|广告位|`keyword_search_results(positionType=2)`|`product_traffic_terms`|`ASINRequestKeywordv2` 返回 `adPosition` 时|MCP 明显更优|
|价格|`product_detail`|`product_report`、`product_trend(Price)`|`ProductRequest`|都可|
|优惠券|`product_detail`|`product_report`|`ProductRequest`|条件覆盖|
|秒杀价|`product_detail`|`product_report`|`ProductRequest`|条件覆盖|
|Prime价|`product_detail`|`product_report`|`ProductRequest`|条件覆盖|
|月销量|`product_detail`|`product_report`、`product_trend(SalesVolume)`|`ProductRequest`|都可|
|大类排名|`product_detail`|`product_report`、`product_trend(Rank)`|`ProductRequest`|都可|
|评分|`product_detail`|`product_report`|`ProductRequest`|都可|
|评价数|`product_detail`|`product_report`|`ProductRequest`|都可|
|链接|本地按站点和 ASIN 生成|—|本地生成|两者相同|

## 本次错误原因

旧版把 MCP 工具名按 `endswith("product_detail")` 匹配。当 Sorftime 的 `tools/list` 同时返回 Amazon、TikTok、Temu 工具时，列表中靠前的 `tiktok_product_detail` 会被误认为 Amazon 的 `product_detail`。

新版按以下顺序解析：

1. 精确的 `product_detail`
2. `amazon_product_detail` / `amazon.product_detail`
3. `sorftime_product_detail`
4. 其他无平台冲突的命名空间

任何包含 `tiktok`、`temu`、`shopee`、`walmart` 等非 Amazon 平台标识的工具都会被排除。
