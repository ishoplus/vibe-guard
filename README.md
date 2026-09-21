# vibe-guard

给**没有 CS 背景、没有工程经验**的人用的 vibe coding 护栏。**同一份代码同时是 Claude Code plugin 和 Codex plugin。**

核心判断：AI 已经解决了「写出代码」，但「判断代码好不好」的门槛没有降低。vibe-guard 把工程师的判断力拆成两种形态：

- **Hook（不经过模型、一定会发生）**：拦密钥外泄、不可逆操作要确认、停下时存档或检查密钥
- **Skill（模型按需调用的流程）**：把需求访谈、小步开发、调试、体检、上线检查写成固定流程
- **说明（不只引导，还讲清楚为什么）**：要用户决定或动手的事，一律用四段说明 —— 📌 要做什么 ｜ ❓ 为什么 ｜ ✅ 做了之后 ｜ ⚠️ 不做的话（风险多常见、多严重）

## 新手模式 / 资深模式

**两种模式的校验和护栏完全一样**（密钥拦截、危险命令确认、部署闸门、ship-check、如实报告、调试熔断），只有「怎么说」不同。

| | 新手模式（默认） | 资深模式 |
|---|---|---|
| 说明方式 | 白话、类比、四段说明、「💡 记住这个」 | 技术结论 + 一句话风险 + 更稳妥的做法 |
| 方案先行 | 超过小改动都先讲方案 | 只在较大改动时给一句话方案 |
| 危险命令确认 | 📌 会做什么 ｜ ❓ 为什么要确认 ｜ ✅ 更稳妥的做法 | 一行：会做什么 + 建议（确认流程不变） |
| 收尾报告 | 含「请你试一下」「下一步建议」 | 改了什么 / 已验证 / 未验证 |
| 各 skill | 完整流程与说明 | 每个 SKILL.md 的「资深模式」一节写明省略哪些说明、哪些校验照做 |

**设置方式**（优先级由高到低）：

| 方式 | 范围 |
|---|---|
| 环境变量 `VIBE_GUARD_MODE=expert` | 当前终端 |
| `python3 plugins/vibe-guard/lib/mode.py set expert --project <项目路径>` | 单个项目（写在 `.vibe-guard/config.json`） |
| `python3 plugins/vibe-guard/lib/mode.py set expert --user` | 这台电脑上的所有项目（写在 `~/.vibe-guard.json`） |
| 在对话里说「我是工程师，以后不用解释这么多」/「我看不懂，讲详细一点」 | AI 确认后自己执行上面的命令（默认只改本项目） |

切换后 hook 立即按新模式说话；每次对话开始注入的规则在下一次对话生效，当前对话由 AI 按新模式回答。

## 四段说明

新手不只需要知道「下一步做什么」，还要知道「为什么要做、不做会怎样」，否则会觉得 AI 在找麻烦，找机会跳过保护措施。

| 在哪里 | 怎么做 |
|---|---|
| 每次对话开始注入的规则 | 定义四段格式和使用分寸：要用户动手、会花钱 / 删数据 / 上线、可能被跳过的保护措施用完整四段；小改动一句话；风险如实分级（很常见 / 偶尔 / 少见但严重），不吓人，可以跳过就说可以跳过 |
| `explain-plain/references/why-library.md` | 17 条常见建议的标准四段说明（git 存档、.gitignore、预算上限、分环境、备份、RLS、回滚演练、CI、只加不删……）。每次讲法一致，不靠 AI 临场发挥 |
| 各 skill | 需要用户拍板或动手的步骤都引用这套格式：`safe-start` 开局、`small-steps` 方案、`idea-to-spec` 选项（加上「选错了会怎样」）、`ship-check` 修 🔴、`health-check` 报告、`deploy-guide` 每一步、`incident-rescue` 止血动作的副作用、`debug-rescue` 回退提议 |
| hook 的拦截提示 | 危险命令的确认框写明：📌 这条命令会做什么 ｜ ❓ 为什么要先确认 ｜ ✅ 更稳妥的做法。每条规则都有对应的替代做法（例如 `git reset --hard` → 先 `git stash`） |

## 文档

| 文件 | 给谁看 |
|---|---|
| [docs/新手使用说明.md](docs/新手使用说明.md) | 新手本人：装好之后怎么用、改坏了怎么办、确认框怎么看 |
| [docs/试点带领人指引.md](docs/试点带领人指引.md) | 帮新手装、陪着用的人：安装、装好后的 5 分钟检查、要记录什么、反馈格式 |
| [docs/试跑记录-2026-09-21.md](docs/试跑记录-2026-09-21.md) | 维护者：用示例项目完整走一遍的结果，作为试点前的基线 |
| [docs/开发与发布.md](docs/开发与发布.md) | 维护者：本地开发怎么让改动生效、三层测试、常见改动清单、版本号规则、发版清单、使用者升级 |
| [CHANGELOG.md](CHANGELOG.md) | 更新记录 |

**目前状态：内部试点**。只在 macOS 验证过；需要有人陪同安装与第一次使用。

## 问题 → 对应组件

| 新手遇到的问题 | 组件 | 类型 |
|---|---|---|
| 需求说不清，AI 默默替你决定一堆事 | `idea-to-spec` | skill |
| 环境与开局：没有 git、密钥乱放 | `safe-start` | skill |
| 「能跑」≠「做好了」，AI 报喜不报忧 | `small-steps` + 新手模式纪律 | skill + SessionStart hook |
| 调试死循环、改坏了回不去 | `debug-rescue` + 平台回退（CC 的 rewind／Codex 的自动存档） | skill + Stop hook |
| 看不懂报错和术语 | `explain-plain` | skill |
| 项目变大后越来越乱 | `health-check`（定期自动提醒） | skill + SessionStart hook |
| 上线前没发现的安全、成本问题（含 AI 编造的依赖包） | `ship-check` | skill |
| 不会部署、环境没分开、改数据库丢数据、不知道怎么回滚 | `deploy-guide` | skill |
| 上线后出事（网站挂了、被盗刷、密钥外泄、数据被看光） | `incident-rescue` | skill |
| 没检查就上线、检查后又改了代码才上线 | 部署闸门（含 `git push` 触发的自动部署） | PreToolUse hook |
| 密钥写进代码 / 提交进 git | 密钥拦截 | PreToolUse hook |
| 误删数据、跑来路不明的脚本 | 危险命令确认 | PreToolUse hook |

## 结构

```
.claude-plugin/marketplace.json   Claude Code 的 marketplace
.agents/plugins/marketplace.json  Codex 的 marketplace
plugins/vibe-guard/
├── .claude-plugin/plugin.json    Claude Code 清单
├── .codex-plugin/plugin.json     Codex 清单（不写 hooks 字段 → 两边共用默认的 hooks/hooks.json）
├── hooks/
│   ├── hooks.json                两边共用
│   ├── session_start.py   注入新手模式纪律 + 项目安全状态（.env 是否外露、是否该体检）
│   ├── guard_write.py     密钥写进代码 → 拦；.env 没被忽略 → 拦
│   ├── guard_bash.py      删库 / 强推 / sudo / curl|sh → 用白话讲后果并要求确认；上线命令另外检查 ship-check 状态
│   └── autosave.py        停下时：Codex 自动 commit；CC 只扫描密钥。含密钥时都会拦下
├── lib/
│   ├── secret_scan.py     密钥规则（hook 与 ship-check 共用）
│   ├── compat.py          宿主识别、Codex apply_patch 解析、argv 形式的 Bash 命令
│   └── ship_state.py      部署闸门的状态：ship-check 结果 + 代码指纹、部署方式（存在项目的 .vibe-guard/）
└── skills/
    ├── idea-to-spec/      需求访谈 → SPEC.md
    ├── safe-start/        git、.gitignore、CLAUDE.md、预算告警
    ├── small-steps/       说方案 → 小步 → 实测 → 边界清单 → 诚实报告
    ├── debug-rescue/      止血 → 复现 → 证据 → 缩小 → 单一假设
    ├── explain-plain/     报错 / 概念 / 改动的白话翻译（附常见报错对照、术语表）
    ├── health-check/      体检脚本 + 结构检查 → HEALTH.md
    ├── ship-check/        自动扫描（--online 查依赖漏洞与包真实性）+ 代码审查 + 人工清单 → 上线结论
    ├── deploy-guide/      选平台 → 分环境 → 环境变量 → 改表结构 → 冒烟测试 → 回滚演练 → 监控 → CI
    └── incident-rescue/   止血 → 记录 → 评估影响 → 修复 → 复盘（五类事故手册 + 密钥轮换）
```

## 安装

前置：`python3` 与 `git`。macOS 未装开发者工具时，第一次执行 `git` 会提示安装。
建议只装在新手的项目里，不要全局安装（原因见「设计取舍」）。

**Claude Code**

```bash
claude --plugin-dir ~/projects/vibe-guard/plugins/vibe-guard     # 本机试用
# 或
/plugin marketplace add ~/projects/vibe-guard
/plugin install vibe-guard@vibe-guard
```

**Codex**

```bash
codex plugin marketplace add ~/projects/vibe-guard
codex plugin add vibe-guard@vibe-guard
```

装完之后**必须在 Codex 里执行一次 `/hooks`，逐条审核并信任这 4 个 hook**。Codex 默认会跳过没被信任的 hook，而且 plugin 每次更新后都要重新信任（信任记录绑定的是 hook 内容的哈希）。
不做这一步，就只有 skill 生效，护栏形同虚设。这一步要由懂的人帮新手做。

## 两个平台的差异

| 项目 | Claude Code | Codex | vibe-guard 的处理 |
|---|---|---|---|
| Skill 格式 | `SKILL.md` | `SKILL.md`（顶层只接受 name / description / license / allowed-tools / metadata） | `version` 放在 `metadata` 下，两边的校验器都通过 |
| 调用 skill | 模型自动调用，或 `/vibe-guard:ship-check` | 模型自动调用，或 `$ship-check` | 规则里只写技能名称，不写调用语法 |
| 项目说明书 | `CLAUDE.md` | `AGENTS.md` | `safe-start` 以 `AGENTS.md` 为正本，`CLAUDE.md` 只放一行 `@AGENTS.md` |
| 改文件的工具 | Write / Edit / MultiEdit / NotebookEdit | `apply_patch`（补丁文本，一次可改多个文件） | `compat.py` 统一解析，只检查新增的行 |
| Bash 命令格式 | 字符串 | 字符串或 argv 数组 | 统一还原成字符串 |
| 危险命令「先问」 | PreToolUse 返回 `ask`，由 CC 弹出确认框 | **不支持 `ask`**（会被当成 hook 失败，命令照样执行） | 在 Codex 上先拦下命令，让 AI 在对话里问用户；用户同意后，AI 在命令前加 `VIBE_GUARD_CONFIRMED=1` 重跑 |
| 宿主识别 | — | 带 `PLUGIN_ROOT` 环境变量，事件里有 `turn_id` | 自动识别；也可以用 `VIBE_GUARD_HOST=claude\|codex` 强制指定 |
| Hook 启用 | 装好就生效 | 要先在 `/hooks` 里信任 | 见上方安装说明 |
| 回退 | 自带 checkpoint + `/rewind`（不记录 Bash 造成的改动） | 没有内置回退 | **CC 默认关闭自动存档**，只在功能完成时做一次有意义的 commit；**Codex 默认开启**，每次停下都 commit |
| 代码审查 | `security-review`、`simplify`，AI 可以自己调用 | `/review` 只能由用户输入；AI 可以调用内置的 `review-agent` 技能 | `ship-check`、`health-check` 按平台调用各自的工具 |
| 分析代码库 | `init`，AI 可以自己调用，产出 CLAUDE.md | `/init` 只能由用户输入 | `safe-start`：CC 调用 `init` 后把内容搬进 AGENTS.md；Codex 由 AI 直接读代码填写 |
| 体检提醒 | 距上次体检 15 个存档点 | 距上次体检 60 个存档点 | 两边存档频率差很多，门槛也跟着不同 |

**Codex 的确认前缀有一个已知弱点**：这个前缀是 AI 自己加的，理论上它可以不问用户就直接加。hook 的提示里明确禁止这样做，实测中 Codex 也遵守了，但这属于「靠模型守规矩」，不是硬性拦截。唯一真正不能绕过的，是「`.env` 会被 git 提交」这一条，加前缀也照样拦。

## 设置

| 需求 | 做法 |
|---|---|
| 强制开启自动存档（例如想在 CC 上也开） | 环境变量 `VIBE_GUARD_AUTOSAVE=1`，或在项目根目录放 `.vibe-guard-autosave` |
| 强制关闭自动存档 | 环境变量 `VIBE_GUARD_AUTOSAVE=0`，或在项目根目录放 `.vibe-guard-no-autosave` |
| 自动存档太碎（Codex） | 功能完成后，可以请 AI 把多个 `autosave:` 提交整理成一个 |

**权限模式建议（新手）**

- **Claude Code**：保持默认权限模式，不要切到 acceptEdits / auto / bypassPermissions，也不要对命令点「以后不再询问」。vibe-guard 的危险命令确认，是在这些保护被关掉之后的最后一道防线，不是替代品。
- **Codex**：保持 `workspace-write` 沙箱加默认的审批策略，不要用 `--dangerously-bypass-approvals-and-sandbox`。

## 设计取舍

- **误报比漏报更伤**：新手看到误报会直接把护栏关掉。密钥规则只收高特异性格式；危险命令一律用 `ask`（问）而不是 `deny`（禁止），只有「`.env` 会被提交」这种没有正当理由的情况才用 `deny`
- **hook 出错时放行**：输入解析失败就放行，护栏不能把正常工作卡死
- **部署闸门用「代码内容指纹」判断检查是否过期**，不看 commit：Codex 每次停下都会自动 commit，但只要代码内容没变，检查结果就仍然有效。vibe-guard 自己写的文档（HEALTH.md、SPEC.md 等）不算改动
- **闸门只提醒、不硬拦**：没过检查时，确认框里会写明「还没做过检查 / 还有 N 项必须修 / 检查后又改过代码」，最终由用户决定。硬拦会逼新手去找绕过的办法
- **依赖检查「没查成」绝不显示成「通过」**：国内常用的 npm 镜像不支持漏洞查询，`npm audit` 会失败。vibe-guard 会改问官方仓库，仍然失败就显示 🟡「没查成」
- **关闭自动存档不等于关闭密钥检查**：CC 默认不自动存档，但每次停下仍会扫描未提交的改动，发现密钥照样拦下
- **自动存档防死循环**：因密钥拒绝存档时会让 AI 先处理；第二次（`stop_hook_active`）只提示，不再阻止停止
- **会装在全局吗**：不建议。新手模式的纪律（先说方案、白话解释）会拖慢工程师的节奏，请装在新手项目的 project scope

## 测试

```bash
python3 -m unittest discover -s tests -v   # 76 个确定性测试：两种模式的校验一致且资深模式提示更短、说明库每条都有四段和风险等级、引用的条目真实存在、4 个 hook（CC 与 Codex 两种输入）、部署闸门、6 个脚本（含本机假网站测冒烟测试）、结构规范
claude plugin validate .                   # marketplace 清单
claude plugin validate plugins/vibe-guard  # plugin 清单
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/vibe-guard   # Codex 清单
```

**还没有的**：skill 触发准确度与流程遵循度的 eval。按 `~/projects/agent-harness-standards/agent-eval-spec.md`，eval 案例必须有真实来源，要等真实的新手用户用过、积累了失败案例之后再建。

## 已知限制

- **skill 的 description 是按新手场景写的**（例如「给没有工程背景的人」）。资深模式下 skill 仍然会被触发，但主要靠每次对话开始注入的技能清单；如果发现资深用户场景下触发率偏低，可以再把 description 改成中性写法

- **部署闸门拦不到的上线方式**：在 GitHub 网页上合并 PR、在托管平台网页上点「重新部署」、别人推送代码。闸门只能管到 AI 在这台电脑上执行的命令
- **依赖真实性检查只覆盖 npm 与 PyPI**，最多 150 个包；PyPI 没有公开的下载量接口，只看发布时间
- **冒烟测试只发 GET 请求**，不会测登录、下单这类需要操作的流程，这些仍要亲手走一遍
- **各服务后台的菜单位置**（回滚、密钥轮换、预算设置）写的是查找方向，界面改版后要以实际画面为准
