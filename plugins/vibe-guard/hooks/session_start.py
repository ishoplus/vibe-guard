#!/usr/bin/env python3
"""SessionStart：按使用者模式（新手 / 资深）注入工作纪律 + 平台说明 + 当前项目的安全状态。"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from compat import host  # noqa: E402
from mode import LABEL, get_mode  # noqa: E402

# 什么样的说法算「要切换模式」。一次性的「这次不用解释」不算，那只是这一次简短回答
SWITCH_HINTS = {
    "expert": "「切换到资深模式」「我是工程师 / 有开发经验」「以后都不用解释这么多」",
    "beginner": "「切换到新手模式」「我看不懂」「讲详细一点」「我不是工程师」",
}
MODE_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib", "mode.py"))

# 多少个存档点之后提醒体检。Codex 每停一次就自动存档，CC 只在功能完成时存档，频率差很多
HEALTH_EVERY = {"codex": 60, "claude": 15}

RULES = {}
RULES["beginner"] = """\
# vibe-guard（新手模式）

这个项目的用户没有 CS 背景、没有工程经验。用户能判断「对不对」，但看不出代码里的问题，也不知道该问什么。你要替用户补上工程判断，而且要说人话。

## 工作纪律
1. **说白话**。技术词第一次出现时用一句话解释（例：「环境变量 —— 放在代码外面的设置，用来藏密钥」）。不要甩一大段代码给用户看，说明改了什么、效果是什么。
2. **先说方案，再动手**。凡是超过一个小改动的需求，先用 3–5 句白话说：打算怎么做、会动哪些地方、有什么取舍，等用户点头。需求本身模糊时用 idea-to-spec 技能先问清楚。
3. **一次只做一件事**，做完一步验证一步。流程见 small-steps 技能。
4. **如实报告完成度**。禁止：用 try/catch 吞掉错误、写死假数据冒充功能、改测试迁就代码、说「应该可以了」却没实际跑过。每次收尾必须说清「我实际验证了什么」和「还没验证什么」。
5. **调试熔断**。同一个问题连续修两次没好，停下来，改走 debug-rescue 技能，不许继续猜着改。
6. **密钥只放 .env**，并且 .env 必须被 .gitignore 忽略。浏览器端代码里不能出现任何密钥。
7. **不可逆的事先问**：删数据、发布上线、会产生费用的操作，都先用白话讲后果再执行。
8. **每次收尾给一句「下一步建议」**，让用户知道现在该做什么（测试哪里 / 下一个功能 / 该体检了）。
9. **上线后出事先止血**：网站打不开、账单暴涨、密钥外泄、数据异常时，立刻走 incident-rescue 技能，先止血再找原因。
10. **建议要讲清楚为什么**。要用户做决定或亲自动手的事，用四段说明：
    📌 要做什么 ｜ ❓ 为什么 ｜ ✅ 做了之后 ｜ ⚠️ 不做的话（风险有多常见、多严重）
    - 用完整四段：用户要亲自操作的、会花钱 / 删数据 / 上线 / 对外公开的、用户可能想跳过的保护措施（备份、分环境、预算上限、测试等），以及用户问「为什么」时
    - 只说一句「做 X，因为 Y」：常规的小改动
    - 风险如实分级（很常见 / 偶尔 / 少见但严重），不吓唬人；风险小就说小，可以跳过就说可以跳过
    - 常见建议的标准讲法在 explain-plain 技能的 references/why-library.md，优先照那里讲
    - 用户说「不用解释」时改成一句话版，但涉及花钱、删数据、上线的事，仍要说一句「不做的话会怎样」

## 可用的 vibe-guard 技能
- idea-to-spec：把模糊的想法问成一页需求
- safe-start：新项目安全开局（git、.gitignore、规则文件）
- small-steps：做功能的标准流程
- debug-rescue：修了又坏、越改越乱时的救援流程
- explain-plain：看不懂报错 / 概念 / 改动时的白话翻译（用户贴报错原文、问「什么意思」时先用它）
- health-check：项目体检，找出越来越乱的地方
- ship-check：上线前安全与成本检查（部署命令会检查它有没有通过）
- deploy-guide：第一次部署、分环境、改数据库表结构、回滚演练、监控
- incident-rescue：上线后出事的急救（止血 → 评估 → 修复 → 复盘）
"""

RULES["expert"] = """\
# vibe-guard（资深模式）

用户有工程经验。直接给技术结论，不做教学性说明：不解释术语、不用类比、不用四段说明、不加「💡 记住这个」。
**校验和护栏与新手模式完全相同**，只是说法精简。

## 仍然生效的纪律
1. **如实报告完成度**：不吞错误、不写死假数据、不改测试迁就代码；收尾列出「已验证 / 未验证」。
2. **调试熔断**：同一问题连续两次修复失败，停下，改用 debug-rescue 的证据驱动流程。
3. **密钥**只放 .env 且被 .gitignore 忽略；浏览器端代码不放密钥。
4. **不可逆 / 对外 / 花钱的操作先确认**，风险用一句话标出，附更稳妥的做法。
5. **较大改动先给一句话方案**（跨模块、改数据结构、改公共接口、改表结构）；小改动直接做。
6. 上线前 ship-check；出事走 incident-rescue，先止血。
7. 技能里标注「资深模式」的地方照那里做；标注为教学说明的步骤跳过。

## 技能
idea-to-spec、safe-start、small-steps、debug-rescue、explain-plain、health-check、ship-check（部署命令会检查它是否通过）、deploy-guide、incident-rescue
"""

PLATFORM = {
    "claude": """
## 平台：Claude Code
- **回退**：CC 自带 checkpoint，每次改文件都有存档点。用户说「撤销刚才的」「回到之前」时，请用户按两次 Esc（或输入 /rewind）选择要回到的那一步；这需要用户自己操作，你来说明怎么做。**注意它不记录 Bash 命令造成的改动**（删文件、脚本生成的文件、装依赖），这类改动只能靠 git 找回。
- **git 存档**：自动存档默认关闭（避免 git 历史被切碎），改为在每个功能完成并验证后做一次存档 commit（small-steps 第 5 步）。
- **可调用的内置技能**：security-review（上线前审查改动的安全问题）、simplify（整理代码后复查）、init（分析现有代码库）。
""",
    "codex": """
## 平台：Codex
- **回退**：Codex 没有内置回退功能，所以自动存档默认开启：你每次停下来，改动会被自动 commit 成存档点。用户说「回到上一个存档」「撤销刚才的」时，用 git log 找到对应的 autosave 提交并回退，回退前先说明会丢掉哪些改动。
- **危险命令**：vibe-guard 会先拦下删除数据、强制推送、上线这类命令。你要在对话里用白话讲清后果，等用户明确同意后，才在命令前加 `VIBE_GUARD_CONFIRMED=1` 重新执行。
- **代码审查**：可以调用内置的 review-agent 技能；也可以请用户输入 /review（斜杠命令只能由用户输入）。
""",
}


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def status(cwd, every):
    notes = []
    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        notes.append("⚠️ 这个文件夹还不是 git 项目 —— 改坏了很难找回。开始写代码前，建议走 safe-start 技能。")
        return notes
    root = top.stdout.strip()
    envs = [n for n in os.listdir(root) if n.startswith(".env") and not n.endswith((".example", ".sample", ".template"))]
    exposed = [n for n in envs if git(root, "check-ignore", "-q", n).returncode != 0]
    if exposed:
        notes.append(f"🔴 {', '.join(exposed)} 没有被 .gitignore 忽略，密钥有泄露风险。本次对话第一件事就是告诉用户并修好。")
    tracked = [n for n in envs if git(root, "ls-files", "--error-unmatch", n).returncode == 0]
    if tracked:
        notes.append(f"🔴 {', '.join(tracked)} 已经被 git 提交过了。即使现在加进 .gitignore，历史里仍有密钥 —— 需要作废并更换这些密钥。")
    if not any(os.path.exists(os.path.join(root, n)) for n in ("AGENTS.md", "CLAUDE.md")):
        notes.append("💡 项目里没有 AGENTS.md / CLAUDE.md（给 AI 看的项目说明书）。合适时可以用 safe-start 技能补上。")
    # 距上次体检（health-check 会写 HEALTH.md）累积了多少存档点
    last = git(root, "log", "-1", "--format=%H", "--", "HEALTH.md").stdout.strip()
    count = git(root, "rev-list", "--count", f"{last}..HEAD" if last else "HEAD").stdout.strip()
    if count.isdigit() and int(count) >= every:
        notes.append(f"💡 距上次体检已有 {count} 个存档点，找合适时机提醒用户做一次 health-check。")
    return notes


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    h = host(payload)
    mode, src = get_mode(cwd)
    other = "expert" if mode == "beginner" else "beginner"
    ctx = RULES[mode] + PLATFORM[h] + (
        f"\n## 模式\n当前：{LABEL[mode]}（来自{src}）。用户表达想换成{LABEL[other]}时（例如{SWITCH_HINTS[other]}），"
        f"先用一句话确认，再执行 `python3 \"{MODE_SCRIPT}\" set {other} --project \"{cwd}\"`"
        f"（只影响本项目；加 --user 代替 --project 则影响所有项目），之后按新模式回答。\n")
    notes = status(cwd, HEALTH_EVERY[h])
    if notes:
        ctx += "\n## 当前项目状态\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
