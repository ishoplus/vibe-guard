---
name: safe-start
description: >
  为新手的新项目（或还没有 git 的旧项目）做安全开局：初始化 git 存档、写好 .gitignore 防止密钥外泄、
  放一份给 AI 看的项目规则 AGENTS.md（Codex 直接读，Claude Code 通过 CLAUDE.md 引用）、建立 .env / .env.example 密钥存放方式，并提醒设置云服务预算上限。
  当用户说「开始一个新项目」「新建项目」「从零开始」「start a new project」「初始化」，
  或 vibe-guard 提示「这个文件夹还不是 git 项目」「没有 AGENTS.md / CLAUDE.md」「.env 没被忽略」时使用。
  不用于已完成开局的项目的日常开发（走 small-steps）。
metadata:
  version: 0.1.0
---

# 安全开局

目的：在写第一行业务代码之前，把「改坏了能回去」和「密钥不会外泄」这两件事变成默认值。整个过程对用户来说应该只有一两次确认。

## 执行流程

1. **说明要做什么**：告诉用户接下来会做 4 件事（存档系统、防泄露清单、AI 规则文件、密钥存放处）。每件用一行四段说明（要做什么 / 为什么 / 做了之后 / 不做的话），前两件的标准讲法见 `../explain-plain/references/why-library.md` 的「用 git 存档」「把 .env 加进 .gitignore」。讲完问一次「可以吗」。
2. **跑脚本**：`python3 scripts/setup.py <项目根目录>`。它是幂等的（重复跑不会弄坏东西），会：
   - 没有 git 就 `git init`；没有 git 身份就提示
   - 把 `templates/gitignore` 里缺的规则补进 `.gitignore`（不覆盖原有内容）
   - 没有 AGENTS.md 就从 `templates/AGENTS.md` 生成；没有 CLAUDE.md 就生成一行 `@AGENTS.md`（Claude Code 会把它展开成 AGENTS.md 的内容），两个工具读到同一份规则
   - 检查 `.env*` 是否已被提交过
   脚本输出里有 🔴 的项目，逐条用白话告诉用户并处理。
3. **已有代码的项目：先分析代码库**（全新的空项目跳过这步）
   - **Claude Code**：调用 `init` 技能分析代码库。它会把结果写进 CLAUDE.md —— 写完后把其中「怎么跑起来」「项目结构」的内容搬进 AGENTS.md 对应的段落，再把 CLAUDE.md 改回一行 `@AGENTS.md`
   - **Codex**：`/init` 只能由用户输入，而且生成的是通用模板。直接由你读代码库，填 AGENTS.md 的「怎么跑起来」「项目结构」两节
4. **填 AGENTS.md**：把生成的 AGENTS.md 里 `{…}` 的地方填上。有 SPEC.md 就从 SPEC 里取；没有就问用户一句「这个项目是做什么的」。技术栈还没定就先留「待定」。
5. **密钥存放**：项目需要任何 API key 时，建 `.env`（真实值，已被忽略）和 `.env.example`（同样的变量名，假值，会被提交）。告诉用户：「真密钥只放 .env，这个文件永远不会被上传」。
6. **第一个存档**：`git add -A && git commit -m "开局：项目初始化"`。
7. **预算提醒**：项目会用到任何云服务或 AI API 时，先用四段说明讲清楚为什么要设（见 why-library「设预算上限」），再读 `references/budget-alerts.md`，带用户把预算上限设好。这一步用户必须自己在网页上点，你给出具体步骤。
8. **收尾**：告诉用户现在有了什么保护，以及怎么回退：Claude Code 按两次 Esc（或输入 /rewind）；Codex 直接说「回到上一个存档」。

## 资深模式
session 显示「资深模式」时：校验、检查、确认步骤一律照做，只省略教学性说明（白话类比、四段说明、术语解释）。本技能具体差异：
- 跳过第 1 步的逐项说明，直接跑 `scripts/setup.py`，按输出处理 🔴
- 第 3 步分析代码库、第 7 步预算上限照做，只报告结果和需要用户在后台操作的项目
- 硬性纪律全部照做（已提交的 .env 必须作废重发）

## 深度参考

| 文件 | 何时去读 |
|---|---|
| `templates/AGENTS.md` | 第 4 步填写时，了解每一节的用途 |
| `templates/gitignore` | 用户问「为什么要忽略这些」时 |
| `references/budget-alerts.md` | 第 7 步，按用户用到的服务查设置方法 |

## 硬性纪律
- `.env` 已经被提交过（脚本报 🔴）时：光加 .gitignore 不够，必须告诉用户**这些密钥要去原服务后台作废并重新生成**，并协助从 git 追踪中移除（`git rm --cached .env`）
- 不覆盖用户已有的 .gitignore、AGENTS.md、CLAUDE.md，只补缺
- 脚本报「只有 CLAUDE.md」时：征得用户同意后，把 CLAUDE.md 的内容搬进 AGENTS.md，CLAUDE.md 改成一行 `@AGENTS.md` —— 否则 Codex 读不到这些规则
