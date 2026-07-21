# 本次修复：飞书 403 与 MCP 全字段空白

## 1. 飞书 HTTP 403

App ID 与 App Secret 只能证明应用身份，不能自动获得目标多维表格的访问权。

需要同时满足：

1. 飞书开放平台为应用开通 `bitable:app` 多维表格读写权限。
2. 发布应用版本，并完成管理员审批。
3. 在目标 Base 的协作者或“添加应用”中，把该 App ID 对应应用加入并授予可编辑权限。
4. Base 开启高级权限时，需要把应用加入能读写目标表、字段和记录的角色或群。
5. 建议使用 `/base/...?...table=tbl...` 的直接链接，避免 Wiki 快捷链接额外需要 Wiki 权限。

新版会根据 403 发生在读取表格、字段创建还是记录写入阶段，返回更明确的处理提示。

## 2. MCP 已连接但所有字段空白

旧版只读取 MCP `tools/call` 返回结果中的 `content`。现代 MCP 工具可以把结构化 JSON 只放在 `structuredContent` 中；如果 Sorftime 使用这种返回方式，连接和工具调用都会成功，但程序会把真实数据忽略，最终全部显示为空。

新版已经增加：

- 支持 `structuredContent`。
- 支持 TextContent 中的 JSON、Markdown 代码块 JSON 和嵌套 JSON 字符串。
- 自动解包 `Code/Data`、`code/data`、`result`、`payload` 等常见响应结构。
- 根据 `tools/list` 返回的实时 `inputSchema` 自动适配 `amzSite`、`keywordSupportSite`、`marketplace`、分页和趋势参数。
- 字段名改为大小写、下划线和符号不敏感匹配，并补充 Sorftime 常见价格、销量、排名、评分和评价数字段别名。
- Sorftime 返回业务错误、套餐权限不足或 `RequestLeft=0` 时，直接显示实际原因。
- 如果仍未识别到字段，备注会显示各接口返回的数据类型和顶层字段，不再只显示“未返回匹配数据”。

## 3. 仍然空白时需要查看什么

重新运行后查看结果“备注”列。新版会区分：

- Sorftime 套餐或调用次数不足。
- MCP 工具参数与当前 inputSchema 不匹配。
- Sorftime 返回了数据，但字段名结构仍未覆盖。
- ASIN 在该关键词前三页没有自然位或广告位。

其中价格、月销量、排名、评分和评价数来自 `product_detail`，与关键词是否匹配无关。因此这些字段也全部空白时，优先检查 MCP 返回解析或账户权限，而不是更换关键词。
