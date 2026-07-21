# V5：每日 09:00 自动抓取

## 新增功能

- 页面默认勾选“每日 09:00 自动抓取（北京时间）”。
- 点击“开始抓取”时，同时保存当前：
  - ASIN
  - 关键词
  - Amazon 站点
  - CLI Account-SK 或 MCP URL/Token
  - Excel / 飞书输出方式
  - 飞书 App ID、App Secret、Base 链接
- 后台调度器按 `Asia/Shanghai` 每天 09:00 检查并执行。
- 同一任务同一天最多自动执行一次，接口失败也不会每分钟重复消耗次数。
- 页面显示定时任务开关、最近运行时间、错误信息和最近一次定时 Excel 下载链接。

## 凭证保存

为了让 Zeabur 在浏览器关闭后仍可执行，定时任务必须保存 Sorftime 和飞书凭证。V5 不以明文保存：

- 整个定时任务 payload 使用 Fernet 加密。
- 密钥保存在 `/app/data/.scheduler.key`，文件权限尽量设置为 `600`。
- 普通任务 JSON、历史记录接口和前端状态接口均不返回凭证或密文。

## Zeabur 必须设置持久化卷

在 Zeabur 服务的 **Volumes** 页面新增 Volume，挂载路径：

```text
/app/data
```

否则服务重新部署或重启后，定时配置、加密密钥、历史结果和定时 Excel 可能丢失。
