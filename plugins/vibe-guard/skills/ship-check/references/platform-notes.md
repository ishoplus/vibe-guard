# 平台专项注意事项

> 各平台界面会改版。以下是**要查什么**；具体菜单位置以平台当下为准，找不到就请用户截图。

## Supabase
- **每张表都要开 RLS**，并且写了规则。只开 RLS 不写规则 = 谁都读不到（功能坏）；不开 = 谁都读得到（数据外泄）
- `anon` key 可以放前端（它本来就是公开的，靠 RLS 保护）；**`service_role` key 绝对不能出现在前端**，它会绕过所有权限
- Storage 的 bucket 也有权限规则，public bucket 里的文件任何人拿到网址都能看
- 检查方式：用未登录状态、另一个账号，各试一次读写

## Firebase
- Firestore / Storage 的「测试模式」规则到期前**所有人可读写**，上线前必须改成正式规则
- 最低要求：`allow read, write: if request.auth != null && request.auth.uid == userId` 这类「只能动自己的」规则
- Firebase 前端配置里的 `apiKey` 是公开的，不是泄露；保护靠的是规则
- 升级到付费 Blaze 方案前先设预算告警（它**不会自动停**）

## Vercel / Netlify
- 本地 `.env` 里的变量要在平台后台的 Environment Variables 里**另外设一次**
- 预览部署（Preview）的网址也是公开的，别在预览环境接正式数据库
- 带 `NEXT_PUBLIC_` / `VITE_` 前缀的变量会进浏览器，只能放公开值
- 知道「回滚到上一次部署」的按钮在哪里

## Stripe（收款）
- 开发用 `sk_test_` / `pk_test_`；正式才换 `sk_live_`，且 `sk_live_` 只能在后端
- **订单是否付款成功，以 webhook 通知为准**，不要以前端「跳转回成功页」为准（可以被伪造）
- 验证 webhook 签名

## AI API（OpenAI / Anthropic / 其他）
- 密钥只在后端；前端调用自己的后端，后端再调 AI
- 后端加：每个用户每日次数上限、单次最大长度（max_tokens）、整体每日上限
- 服务后台设月度消费上限
- 用户输入会直接进 prompt 的，要预期有人会试图让它说出系统提示或做别的事 —— 不要在 prompt 里放任何秘密

## GitHub
- 推到**公开**仓库之前，先确认 git 历史里没有密钥（precheck 会查）
- 开启 Secret Scanning 与 Dependabot 提醒（仓库 Settings → Code security）
- 已经推上去的密钥：**先作废重发**，再考虑清理历史
