# 本次优化实施报告

## 1. 页面排版

- 增加全局 `[hidden] { display: none !important; }`，解决 MCP 模式下 CLI Account-SK 区域仍然显示的问题。
- CLI/MCP 连接区域改为统一卡片高度、边框、内边距和辅助文字布局。
- 站点、输出方式、自动下载改为三列等高卡片；飞书配置单独显示为三列区域。
- 移动端自动切换为单列。

## 2. 名称

页面标题、浏览器标题和文档统一为：

```text
Amazon 关键词监控工具 by kong
```

## 3. Excel 与飞书输出

新增三种选择：

```text
下载 Excel
写入飞书
下载 Excel + 写入飞书
```

飞书页面字段：

```text
App ID
App Secret
Base 链接
```

飞书写入逻辑支持：

- Base 链接解析
- Wiki 链接解析为 Base app_token
- 链接无 table_id 时选择第一张表
- 自动检查并创建缺失字段
- 每批 500 条写入
- 返回写入条数与错误信息

## 4. Amazon / TikTok 错误路由修复

原工具用 `normalized.endswith(required)` 识别 MCP 工具。因此：

```text
product_detail
```

可能错误匹配到：

```text
tiktok_product_detail
```

新版使用评分匹配，并完全排除 TikTok、Temu、Shopee、Walmart、eBay 等非 Amazon 平台命名。核心 Amazon 工具缺失时，连接测试直接给出明确错误，不再继续抓取空数据。

## 5. MCP / CLI 字段对应

项目内新增：

```text
MCP_CLI_FIELD_MAPPING.md
Amazon关键词监控_MCP_CLI字段对应表_by_kong.xlsx
```

本工具默认推荐 MCP；大量批量查询时可选 CLI。

## 测试结果

```text
Python 语法检查：通过
JavaScript 语法检查：通过
单元测试：11 项全部通过
Zeabur 端口/健康检查：通过，监听 0.0.0.0:$PORT
```

无法在交付环境中使用你的真实 Sorftime Token 和飞书 Secret 做线上写入测试；MCP 平台路由、CLI 固定命令、飞书 API 调用顺序均通过模拟测试。
