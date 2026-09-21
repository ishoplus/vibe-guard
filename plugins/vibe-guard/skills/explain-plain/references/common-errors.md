# 常见报错白话对照

按「报错里出现的关键字」查。每条：白话意思 → 最常见原因 → 通常怎么处理。

## 环境与安装

| 关键字 | 白话意思 | 常见原因 | 通常处理 |
|---|---|---|---|
| `command not found` / `不是内部或外部命令` | 电脑找不到这个工具 | 没安装；装了但终端不知道在哪（PATH） | 安装它；装完重开终端 |
| `EADDRINUSE` / `address already in use` / `port … is already in use` | 这个端口（门牌号）已经被别的程序占用 | 上次启动的还没关 | 关掉旧的，或换一个端口 |
| `EACCES` / `Permission denied` | 没有权限动这个文件 | 文件属于系统或别的用户 | 不要急着加 sudo，先确认路径对不对 |
| `ERESOLVE` / `peer dependency` | 装的依赖包之间版本互相冲突 | 某个包要求另一个包的特定版本 | 看报错提到的两个包，统一版本 |
| `Cannot find module` / `ModuleNotFoundError` / `No module named` | 程序要用的零件找不到 | 没安装依赖（npm install / pip install）；路径或名字拼错 | 先重新安装依赖 |
| `node: bad option` / `SyntaxError: Unexpected token` 在启动时 | 语言版本太旧，看不懂新写法 | Node / Python 版本不对 | 查项目要求的版本 |

## 程序运行

| 关键字 | 白话意思 | 常见原因 | 通常处理 |
|---|---|---|---|
| `undefined` / `null` / `NoneType` / `Cannot read properties of undefined` | 想用一个东西，但它是空的 | 数据还没从网上拿回来就先用了；名字拼错；数据里根本没有这个栏位 | 打日志看那个值实际是什么 |
| `is not a function` | 把不是功能的东西当功能来叫 | 名字拼错；导入方式不对 | 检查名字和 import |
| `Maximum call stack` / `RecursionError` | 程序在自己绕圈，停不下来 | 函数自己调用自己没有出口；画面更新触发自己再更新 | 找出循环的那两段 |
| `Too many re-renders` | React 画面在无限重画 | 在画面渲染时直接改了状态 | 把改状态的动作放进事件或 useEffect |
| `Hydration failed` / `hydration mismatch` | 服务器画出来的和浏览器画出来的不一样 | 用了时间、随机数、浏览器专属的东西 | 把这些放到页面载入之后再做 |
| `SyntaxError` / `Unexpected token` | 代码写法有错，看不懂 | 少了括号、引号、逗号 | 看报错指的那一行和上一行 |
| `TypeError` | 类型不对，例如把文字当数字算 | 表单输入永远是文字 | 转换类型 |

## 网络与后端

| 关键字 | 白话意思 | 常见原因 | 通常处理 |
|---|---|---|---|
| `CORS` / `blocked by CORS policy` | 浏览器为了安全，不让这个网页去拿另一个网站的数据 | 前端直接呼叫外部 API；后端没允许前端的网址 | 让后端允许前端网址；或改成经过自己的后端去拿 |
| `401 Unauthorized` | 没带身份证明，或证明无效 | 没登录；API key 没读到或错了 | 查环境变量有没有读到 |
| `403 Forbidden` | 知道你是谁，但你没权限 | 权限规则（例如 Supabase RLS）挡住了 | 查权限规则，**不要直接关掉权限** |
| `404 Not Found` | 找不到这个网址 / 资源 | 网址打错；路由没设定；部署后路径不同 | 对照实际网址 |
| `429 Too Many Requests` | 请求太频繁，被限速了 | 循环呼叫；额度用完 | 查是否在重复呼叫；看额度 |
| `500 Internal Server Error` | 后端自己出错了 | 真正原因在后端的日志里 | 去看后端 / 服务器日志，不是看浏览器 |
| `ECONNREFUSED` / `Failed to fetch` / `Network Error` | 连不上对方 | 后端没启动；网址或端口错；断网 | 确认后端在跑、网址对 |
| `timeout` | 等太久没回应 | 对方太慢；查询太大；网络问题 | 看是哪一个请求慢 |

## 数据库

| 关键字 | 白话意思 | 常见原因 | 通常处理 |
|---|---|---|---|
| `relation … does not exist` / `no such table` | 数据表不存在 | 还没建表；连错数据库 | 查建表步骤（migration）有没有执行 |
| `duplicate key` / `unique constraint` | 这个值规定不能重复，但重复了 | 重复提交；测试数据没清 | 查是不是按钮连点 |
| `violates row-level security` | 数据库权限规则挡住了这次读写 | RLS 规则没设对 | 修规则，**不要关掉 RLS** |
| `password authentication failed` | 数据库密码错了 | 环境变量没读到或值错了 | 查 .env |

## Git

| 关键字 | 白话意思 | 常见原因 | 通常处理 |
|---|---|---|---|
| `merge conflict` / `CONFLICT` | 两个版本改了同一个地方，git 不知道留哪个 | 两边都改了同一行 | 逐处决定留哪个，问用户 |
| `rejected … fetch first` / `non-fast-forward` | 远端有你本地没有的新改动 | 别处推过新版本 | 先拉下来（pull）再推，**不要加 --force** |
| `detached HEAD` | 你现在站在一个旧存档上，不在任何分支 | 切到了某个历史存档 | 回到分支：`git switch main` |
