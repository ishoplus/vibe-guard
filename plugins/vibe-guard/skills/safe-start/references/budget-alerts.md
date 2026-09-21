# 预算上限与费用告警

新手最贵的一课通常不是技术问题，而是一张账单：密钥被盗刷、代码死循环调用 API、忘记关掉的服务器。
**原则：能设「硬上限」（超过就停）的设硬上限；只能设「告警」的，把告警金额设低。**

> 各家后台界面会改版。以下是查找方向，给用户步骤时以对方后台当下的实际菜单为准；找不到就让用户截图给你看。

| 服务 | 能做什么 | 去哪里找 |
|---|---|---|
| OpenAI API | 月度预算上限 + 告警邮件 | 后台 Settings → Limits / Billing |
| Anthropic API（Claude） | 工作区消费上限 | Console → Settings → Limits / Billing |
| Google Cloud / Firebase | 预算告警（**不会自动停**） | Billing → Budgets & alerts；Firebase 建议保持免费 Spark 方案直到确定需要升级 |
| AWS | 预算告警（**不会自动停**） | Billing → Budgets |
| Vercel | 用量上限（Spend Management） | Team Settings → Billing |
| Supabase | 免费方案本身有额度上限；付费方案有 Spend Cap 开关 | Organization → Billing |
| Railway | 用量上限 | Workspace → Usage / Billing |

## 其他防护
- **AI API 调用一律经过后端**，并在后端加「每个用户每天最多 N 次」的限制
- 调用外部 API 的地方，确认**不会在循环或页面每次刷新时重复调用**
- 不用的服务器、数据库、测试部署，当天删掉
- 如果能选，**优先用有免费额度且超额会停止、而不是自动扣款的方案**
