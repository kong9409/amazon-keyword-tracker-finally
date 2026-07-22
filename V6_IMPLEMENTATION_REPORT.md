# V6.1 多数据源实施报告

## 已完成

1. 页面新增统一“数据源软件”选择器。
2. 原有连接名称改为 `Sorftime CLI` 和 `Sorftime MCP`。
3. 新增卖家精灵 API、西柚洞察 OpenAPI V2、SIF MCP。
4. 新增“其他软件”，支持自定义 MCP 与自定义 API。
5. 选择数据源后，只显示对应凭证输入框。
6. ASIN、关键词、站点、Excel、飞书、每日 09:00 共用原流程。
7. 普通任务文件不保存 API Key、MCP Token、Account-SK；每日任务继续加密保存到 `/app/data`。

## 后端架构

新增 `provider_adapter.py`，把不同数据源统一为：

```text
check_ready()
capture_keyword(asin, keyword, marketplace)
stats()
close()
```

`app.py` 不再直接绑定 Sorftime，而是通过 `build_data_client()` 分发到所选数据源。

## 接口适配

### Sorftime

保留现有 Sorftime MCP / CLI 严格字段映射和趋势兜底。

### 卖家精灵

- API Key 使用 `secret-key` 请求头。
- 反查流量词、ABA、产品详情和销量接口分别缓存，避免同一 ASIN/关键词重复消耗。
- 支持嵌套自然位/广告位对象以及 0~1 流量占比转换。

### SIF

- 使用 MCP `initialize`、`tools/list`、`tools/call`。
- 根据工具名称、描述和实时 `inputSchema` 动态识别 Amazon 流量、关键词、产品、排名和销量工具。
- Key 同时兼容常见 Bearer、X-API-Key 和 MCP-Key 请求头。

### 西柚洞察

- 使用 OpenAPI V2 请求头。
- 产品详情请求把 `country` 放在每个 `entity` 中。
- BSR 趋势按最新日期优先取根类目排名。

### 其他软件

- MCP：自动发现工具和参数。
- API：向用户填写的 Endpoint 发送 `asin`、`keyword`、`marketplace`，并按通用字段别名解析。

## 测试结果

```text
Python 编译检查：通过
JavaScript 语法检查：通过
自动化测试：30 项全部通过
Hosted 健康接口：通过
HTML 数据源选项与关键词脱敏检查：通过
```

测试使用模拟响应，没有调用用户的真实付费账户，因此真实账号的套餐权限、接口额度和字段覆盖仍以各软件实际响应为准。
