# 多数据源字段映射

| 目标字段 | Sorftime | 卖家精灵 API | SIF MCP | 西柚洞察 MCP / API | 其他软件 |
|---|---|---|---|---|---|
| 流量占比 | product_traffic_terms | traffic/keyword · trafficPercentage | 自动识别流量/反查工具 | MCP get_asin_keywords；API asins/research/list/period | MCP动态匹配 / 通用字段 |
| ABA热度 | keyword_detail | aba/research · searchRank | 自动识别关键词详情工具 | MCP get_keyword_info；API searchTerms/info | MCP动态匹配 / 通用字段 |
| 搜索量 | keyword_detail | aba/research · searches | 自动识别关键词详情工具 | MCP get_keyword_info；API searchTerms/info | MCP动态匹配 / 通用字段 |
| 自然位 | keyword_search_results | traffic/keyword · rankPosition | 自动识别排名工具 | MCP ASIN关键词/排名工具；API ranks.position=or | MCP动态匹配 / 通用字段 |
| 广告位 | keyword_search_results | traffic/keyword · adPosition | 自动识别流量/排名工具 | MCP ASIN关键词工具；API ranks.position=sp | MCP动态匹配 / 通用字段 |
| 价格 | product_detail | asin detail · price | 自动识别产品详情工具 | MCP get_asin_info；API asins/info | MCP动态匹配 / 通用字段 |
| 月销量 | product_detail/product_trend | competitor-lookup · units | 自动识别销量工具 | MCP get_asin_order_trends；API asins/orders | MCP动态匹配 / 通用字段 |
| 大类排名 | product_detail/product_trend | asin detail · bsrRank | 自动识别排名/产品工具 | MCP get_asin_bsr_trends；API bsrInfo/trends/daily | MCP动态匹配 / 通用字段 |
| 评分 | product_detail | asin detail · rating | 自动识别产品详情工具 | MCP get_asin_info；API asins/info | MCP动态匹配 / 通用字段 |
| 评价数 | product_detail | asin detail · ratings | 自动识别产品详情工具 | MCP get_asin_info；API asins/info | MCP动态匹配 / 通用字段 |

优惠券、秒杀价和 Prime 价属于平台条件字段，仅当所选软件实际返回对应值时写入，不生成虚假数据。
