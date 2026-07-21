# V3 修复说明：Sorftime 站点参数与飞书 403

## 1. Sorftime 全字段空白的真实原因

从实际导出的 `amazon-keyword-tracker-20260721-151458.xlsx` 备注中可以看到，Sorftime MCP 已经明确返回：

```text
Please specify the site to query.
See the amz_site parameter description in the method signature.
```

关键词接口返回：

```text
Please specify the site to query.
See the keyword_support_site parameter description in the method signature.
```

这说明不是 ASIN 或关键词没有数据，而是程序没有把站点参数传给实时 MCP schema。

Sorftime 表格文档使用 camelCase：

```text
amzSite
keywordSupportSite
```

实际 MCP `tools/list` 返回的 schema 使用 snake_case：

```text
amz_site
keyword_support_site
```

V2 的别名适配没有包含这两个名称，导致站点被静默丢弃。V3 已同时兼容：

```text
amzSite / amz_site
keywordSupportSite / keyword_support_site
marketplace / site / amazon_site
```

同时，Sorftime 以普通字符串返回的参数错误现在会直接被识别为错误，不再错误显示为“未返回匹配数据”。

## 2. SSL EOF

实际导出中有一行出现：

```text
SSL: UNEXPECTED_EOF_WHILE_READING
```

V3 对 MCP 的临时网络错误、429、500、502、503、504 增加最多 3 次自动重试。

## 3. 飞书字段接口 403

当前错误路径是：

```text
/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields
```

这说明 App ID/Secret、app_token、table_id 已经解析成功，失败发生在应用访问该数据表字段时。

V3 增加自动降级：

1. 首先尝试读取并创建缺失字段。
2. 字段接口返回 403 时，跳过字段管理。
3. 直接按现有字段名调用 `records/batch_create`。
4. 如果已有同名字段且应用有记录写入权限，仍可成功写入。
5. 如果记录写入也返回 403，则必须在飞书 Base 中给应用添加文档/高级权限，代码无法绕过。

目标飞书表建议预先建立以下字段：

```text
日期、ASIN、关键词、流量占比、ABA热度、搜索量、自然位、广告位、价格、优惠券、秒杀价、Prime价、月销量、大类排名、评分、评价数、链接、抓取时间、站点、自然曝光时间、广告曝光时间、优惠券类型、是否秒杀、数据源、状态、备注
```
