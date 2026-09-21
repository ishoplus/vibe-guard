# 作废与更换密钥

> 各服务后台菜单会改版，以下是查找方向；找不到时请用户截图。

## 通用步骤（每个服务都一样）
1. 在服务后台**生成一把新密钥**
2. 把新密钥填进：本机 `.env`、托管平台的环境变量（Production / Preview 都要检查）、CI 的 Secrets（如果有）
3. **重新部署**，确认网站用新密钥正常工作
4. **作废（删除 / revoke）旧密钥**
5. 看旧密钥最近的使用记录，确认作废后没有新的调用

情况紧急（正在被盗刷）时，第 4 步提前到第 1 步：先作废，网站暂时坏掉也比继续被刷好。

## 各服务的查找方向

| 服务 | 去哪里 |
|---|---|
| OpenAI | 后台 API keys 页面：新建、删除 |
| Anthropic（Claude） | Console → API Keys：新建、停用 / 删除 |
| AWS | IAM → 对应用户 → Security credentials → Access keys：新建、停用、删除 |
| GitHub token | Settings → Developer settings → Personal access tokens |
| Stripe | Dashboard → Developers → API keys：Roll key（可设旧密钥延迟失效） |
| Supabase | Project Settings → API：service_role / anon key；更换方式依 Supabase 当下的 API key 机制而定，照后台指引操作 |
| Firebase / Google Cloud | Google Cloud Console → APIs & Services → Credentials；服务账号密钥在 IAM → Service Accounts |
| 数据库密码 | 数据库平台的 Database 设置里重设密码，并更新所有连接字符串 |

## 做完后
- 在 INCIDENTS.md 记下：哪把密钥、何时作废、新密钥放在哪些地方
- 跑一次 ship-check，确认代码和 git 历史里没有其他密钥
