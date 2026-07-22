# V6.1 修复说明：西柚洞察 MCP

- 西柚洞察由“仅 OpenAPI”升级为“MCP / OpenAPI”。
- 页面默认选择西柚 MCP，并预填 `https://mcp.xydc.com/mcp`。
- 新增西柚 MCP Token 输入框，按 Bearer 方式鉴权。
- 新增西柚专用 MCP 客户端，优先匹配 ASIN关键词、关键词详情、ASIN详情、关键词排名、订单趋势和 BSR 趋势工具。
- 保留 `tools/list` + `inputSchema` 动态适配，兼容工具命名和参数变化。
- 增强中文工具名、中文参数名、站点枚举、分页、日期范围及必填 enum 参数识别。
- 西柚 MCP Token 不写入源码、普通任务文件或导出文件；每日任务沿用加密存储。
- 西柚 OpenAPI 仍可切换使用，不影响原有 API 用户。

## 验证

- Python 编译通过。
- JavaScript 语法检查通过。
- 32 项自动化测试通过。
- 未将用户真实 Token 写入生成包。
