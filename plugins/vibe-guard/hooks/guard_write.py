#!/usr/bin/env python3
"""PreToolUse(改文件)：拦住把密钥写进代码。CC 与 Codex 共用。

- CC：Write / Edit / MultiEdit / NotebookEdit
- Codex：apply_patch（一个补丁可能改多个文件，逐个检查）

规则：
- 密钥写进普通代码文件 → 拦（exit 2，理由回给 AI）
- 写 .env 但 .env 没被 git 忽略 → 拦，先补 .gitignore
- 其余放行
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from compat import edits  # noqa: E402
from secret_scan import is_env_file, scan  # noqa: E402
from mode import get_mode  # noqa: E402


def git_ignored(path):
    d = os.path.dirname(os.path.abspath(path)) or "."
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    inside = subprocess.run(["git", "-C", d, "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True)
    if inside.returncode != 0:
        return None  # 不是 git 项目，谈不上会不会被提交
    r = subprocess.run(["git", "-C", d, "check-ignore", "-q", os.path.abspath(path)])
    return r.returncode == 0


def deny(msg):
    sys.stderr.write(msg)
    sys.exit(2)


def check(path, text, expert=False):
    name = os.path.basename(path) or "文件"
    if is_env_file(path):
        if git_ignored(path) is False:
            if expert:
                return f"[vibe-guard] 拦截：{name} 未被 .gitignore 忽略。先在 .gitignore 加 `.env`、`.env.*`、`!.env.example`。"
            return (f"[vibe-guard] 已拦截：{name} 还没有被 .gitignore 忽略。\n"
                    "这个文件用来放密钥，一旦被 git 提交、推到 GitHub，别人就能看到。\n"
                    "请先在项目根目录的 .gitignore 里加上 `.env` 和 `.env.*`（保留 `!.env.example`），"
                    "再写这个文件。"
                    "用四段说明告诉用户：📌 要改成怎样 ｜ ❓ 为什么 ｜ ✅ 改了之后 ｜ ⚠️ 不改的话会怎样（标准讲法见 explain-plain 技能 references/why-library.md 的「把 .env 加进 .gitignore」）。")
        return None
    hits = scan(text)
    if not hits:
        return None
    if expert:
        where = "、".join(f"第 {ln} 行 {n}（{masked}）" for n, _, ln, masked in hits[:5])
        return (f"[vibe-guard] 拦截：{name} {where}。改为从环境变量读取；"
                "若是浏览器端代码，改由后端代为调用。")
    lines = "\n".join(f"  - 新增内容第 {ln} 行：{desc}（{n}，{masked}）" for n, desc, ln, masked in hits[:5])
    return (f"[vibe-guard] 已拦截：准备写进 {name} 的内容里有真实密钥。\n{lines}\n"
            "密钥写进代码文件，迟早会被提交到 git 或打包进网页，谁都能看到、能盗刷。\n"
            "请改成：密钥放进 .env（确认已被 .gitignore 忽略），代码里用环境变量读取；"
            "同时在 .env.example 里放一个假值当说明。\n"
            "如果这是浏览器里运行的前端代码，密钥连环境变量都不能放 —— 必须改成由后端调用对方服务。\n"
            "用四段说明告诉用户：📌 要改成怎样 ｜ ❓ 为什么 ｜ ✅ 改了之后 ｜ ⚠️ 不改的话会怎样（标准讲法见 explain-plain 技能 references/why-library.md 的「密钥只放 .env，前端代码不放任何密钥」）。")


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 解析失败就放行，护栏不能把正常工作卡死
    expert = get_mode(payload.get("cwd") or os.getcwd())[0] == "expert"
    problems = [m for m in (check(p, t, expert) for p, t in edits(payload)) if m]
    if problems:
        deny("\n\n".join(problems))
    sys.exit(0)


if __name__ == "__main__":
    main()
