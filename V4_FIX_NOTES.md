# V4 修复说明

## 1. 飞书 `TextFieldConvFail`

问题原因：飞书目标列是多行文本字段，但旧版直接提交了数字、布尔值或对象，例如月销量 `1234`、评分 `4.7`。飞书批量新增记录接口会返回 `TextFieldConvFail`。

V4 调整：

- 读取目标 Base 的真实字段类型。
- 文本字段全部转换为字符串。
- 数字字段转换为数值；空值不再提交。
- 日期字段转换为毫秒时间戳。
- 复选框字段转换为布尔值。
- 超链接字段转换为链接对象。
- 无字段读取权限时，采用全字符串安全写入。
- 自动创建的缺失字段仍统一创建为文本字段。

## 2. Sorftime 四项指标固定接口

V4 不再混用 `product_report` 获取下列指标：

| 指标 | 固定数据源 | 备用数据源 |
|---|---|---|
| 流量占比 | `product_traffic_terms` | 无 |
| ABA热度 | `keyword_detail` | 无 |
| 搜索量 | `keyword_detail` | 无 |
| 月销量 | `product_detail` | `product_trend(SalesVolume)` |
| 大类排名 | `product_detail` | `product_trend(Rank/Ranking)` |

同时增加：

- `productTrendType` 根据实时 MCP `inputSchema.enum` 自动映射 `Rank` / `Ranking`。
- 趋势接口枚举名不一致时自动尝试等价名称。
- 扩展 Sorftime 月销量、大类排名、ABA、流量占比字段别名。
- 产品排名为对象或列表时优先提取 root/main/大类排名。
- 关键词字段支持 `KeywordName`、`SearchKeyword` 等返回名。
- 备注明确写出每个空白指标对应的接口来源。

## 3. 仍可能为空的情况

- `product_traffic_terms` 没有返回该 ASIN 对应关键词，或返回结果本身没有流量占比字段。
- `keyword_detail` 当前账户套餐没有 ABA 排名字段。
- ASIN 新上架、无销量历史或 Sorftime 尚未收录。
- Sorftime Account-SK 请求次数不足或站点数据权限受限。

V4 不会伪造数据；接口真实未返回时仍保留空白，并在备注标记具体来源。
