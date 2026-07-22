# V6.1 多数据源改造说明

## 页面改动

- STEP 1 改为“连接数据源”。
- 新增数据源选择：Sorftime、卖家精灵、SIF、西柚洞察、其他软件。
- 原 CLI / MCP 明确改名为 Sorftime CLI / Sorftime MCP。
- 选择数据源后，仅显示对应凭证输入框。
- “Sorftime 接口调用次数”改为“数据接口调用次数”。
- 定时任务状态增加数据源名称。

## 后端改动

新增 `provider_adapter.py`，统一所有数据源的四个能力：

```text
check_ready
capture_keyword
stats
close
```

原有 Sorftime 采集逻辑保持不变，新增：

- 卖家精灵 API 适配器
- 西柚洞察 OpenAPI V2 适配器
- SIF 动态 MCP 适配器
- 其他软件动态 MCP 适配器
- 其他软件通用 POST API 适配器

## 安全与定时任务

- 普通任务 JSON 仅保留数据源名称与连接方式，不写入 API Key、MCP Token、Account-SK。
- 每日任务凭证继续整体加密后存入 `/app/data`。
- Zeabur 模式仍拒绝 HTTP、localhost 和内网 MCP/API 地址。

## 测试

- 原 24 项测试全部保留。
- 新增 5 项多数据源测试：卖家精灵字段映射、西柚字段映射、客户端分发、凭证脱敏、页面数据源与关键词脱敏。
- 共 30 项自动化测试。

## V6.1 稳定性补充

- 西柚 `asins/info` 已按 V2 结构把 `country` 放入每个 `entity`。
- 西柚 BSR 趋势优先取最新日期的根类目排名，避免误取子类目排名。
- SIF/其他 MCP 会同时发送常见的 `Authorization`、`X-API-Key`、`MCP-Key` 头，提高 Key 鉴权兼容性。
- 其他 API 支持自定义 Endpoint、API Key 和 Header 名称。
