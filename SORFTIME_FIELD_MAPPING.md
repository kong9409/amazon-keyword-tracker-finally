# Sorftime 字段映射

| 页面字段 | CLI 主来源 | MCP 主来源 / 兜底 |
|---|---|---|
| 流量占比 | `ASINRequestKeywordv2` | `product_traffic_terms` → `product_report` |
| ABA 热度 | `ASINRequestKeywordv2` | 流量词字段 → `keyword_detail` |
| 搜索量 | `ASINRequestKeywordv2` | 流量词字段 → `keyword_detail` |
| 自然位 | `ASINRequestKeywordv2` | `product_traffic_terms` → `keyword_search_results(positionType=0)` → `product_ranking_trend_by_keyword` |
| 广告位 | `ASINRequestKeywordv2` | `product_traffic_terms` → `keyword_search_results(positionType=2)` |
| 价格 | `ProductRequest` | `product_detail` → `product_report` |
| 优惠券 | `ProductRequest` | `product_detail` → `product_report` |
| 秒杀价 | `ProductRequest` | `product_detail` → `product_report` / `product_trend` |
| Prime 价 | `ProductRequest` | `product_detail` → `product_report` / `product_trend` |
| 月销量 | `ProductRequest` | `product_detail` → `product_report` / `product_trend` |
| 大类排名 | `ProductRequest` | `product_detail` → `product_report` / `product_trend` |
| 评分 | `ProductRequest` | `product_detail` → `product_report` |
| 评价数 | `ProductRequest` | `product_detail` → `product_report` |
| 链接 | ASIN + 站点生成 | ASIN + 站点生成 |

Sorftime 某接口未返回某字段时，单元格保留为空并在“状态/备注”中说明；不会填充模拟数据。

## V4 固定来源覆盖规则

| 字段 | 主接口 | 备用接口 |
|---|---|---|
| 流量占比 | `product_traffic_terms` | 无 |
| ABA热度 | `keyword_detail` | 无 |
| 搜索量 | `keyword_detail` | 无 |
| 月销量 | `product_detail` | `product_trend`，类型 `SalesVolume` |
| 大类排名 | `product_detail` | `product_trend`，类型 `Rank` 或 `Ranking` |

V4 已移除 `product_report` 对以上字段的填充，避免跨接口取错值。
