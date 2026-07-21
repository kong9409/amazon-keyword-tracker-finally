# Amazon 关键词监控工具 by kong V4 实施报告

## 已修复

1. 飞书 `TextFieldConvFail`
   - 读取飞书真实字段类型。
   - 文本字段强制转字符串。
   - 数字、日期、复选框、超链接按字段类型转换。
   - 空白数字和日期不提交，避免转换失败。

2. Sorftime 指标来源固定
   - 流量占比：`product_traffic_terms`
   - ABA热度、搜索量：`keyword_detail`
   - 月销量：`product_detail` → `product_trend(SalesVolume)`
   - 大类排名：`product_detail` → `product_trend(Rank/Ranking)`
   - 移除 `product_report` 对上述指标的填充。

3. Sorftime 兼容性
   - 根据 MCP 实时 schema 自动适配 `Rank` / `Ranking`。
   - 扩展关键词、流量占比、ABA、销量和排名字段别名。
   - 支持排名对象、排名列表及趋势时间序列。
   - 空白指标的备注会显示固定接口来源。

## 验证

- Python 编译通过。
- JavaScript 语法检查通过。
- 21 项自动化测试通过。
- Zeabur 托管模式 `/api/health` 启动检查通过。
- 飞书文本字段数值转字符串测试通过。
- `product_detail` 缺失销量/排名后，`product_trend` 回退测试通过。
