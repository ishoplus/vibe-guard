# 更新记录

## 0.6.2 — 2026-09-21
- 公开发布到 https://github.com/ishoplus/vibe-guard ，安装来源改为 `ishoplus/vibe-guard`
- 清单补上 homepage、repository；作者改为 ishoplus，不再公开邮箱
- 修复 ship-check 误报：Python 后端、文档里提到 `VITE_…` 变量名或 `dangerouslyAllowBrowser` 时，被当成浏览器端暴露（用 ship-check 检查 vibe-guard 自己的仓库时发现）
- 修复 ship-check 漏报：被 .gitignore 忽略的 `.env` 没被检查，里面 `NEXT_PUBLIC_` / `VITE_` 开头的敏感变量查不出来

## 0.6.1 — 2026-09-21
- 新增 `docs/开发与发布.md`：本地开发、测试、发版、使用者升级（重载与升级行为在 CC 与 Codex 上实测）
- 新增 `scripts/bump_version.py`：三个清单的版本号一起改
- 新增 `tests/e2e/cc_step.py`、`tests/e2e/codex_sandbox.sh`：端到端试跑工具
- 新手使用说明补「我的项目怎么在自己电脑上跑起来」
- 修复：用户贴报错原文时 explain-plain 不触发；需求访谈推荐存本机文件时没先讲代价

## 0.6.0 — 2026-09-21
- 新手模式 / 资深模式：校验与护栏完全相同，资深模式只省略教学说明
- 模式可用环境变量、项目设置、个人设置指定，也可以在对话里说「我是工程师」由 AI 切换

## 0.5.0 — 2026-09-21
- 四段说明（要做什么 / 为什么 / 做了之后 / 不做的话）写进工作规则
- 新增 17 条常见建议的标准说明库（`explain-plain/references/why-library.md`）
- 危险命令确认附「为什么要先确认」与「更稳妥的做法」

## 0.4.0 — 2026-09-21
- 新增 `deploy-guide`（第一次部署）与 `incident-rescue`（出事急救）
- `ship-check --online`：依赖漏洞扫描、依赖包真实性检查、Supabase RLS 规则内容检查
- 部署闸门：部署命令与推到自动部署分支时，检查上线前检查是否通过、是否已过期
- 修复：国内 npm 镜像不支持漏洞查询时，结果被误判为「没有漏洞」

## 0.3.0 — 2026-09-21
- 按平台调用内置工具（CC：rewind / security-review / simplify / init；Codex：review-agent）
- 自动存档：CC 默认关闭（停下时仍扫描密钥），Codex 默认开启

## 0.2.0 — 2026-09-21
- 同时支持 Claude Code 与 Codex（一份 hooks.json；Codex 不支持 ask，改为拦下后由用户在对话中确认）
- 项目说明书以 AGENTS.md 为正本，CLAUDE.md 引用它

## 0.1.0 — 2026-09-21
- 7 个技能：idea-to-spec、safe-start、small-steps、debug-rescue、explain-plain、health-check、ship-check
- 4 个 hook：新手模式注入、密钥拦截、危险命令确认、自动存档
