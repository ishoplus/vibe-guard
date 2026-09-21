#!/usr/bin/env python3
"""安全开局（幂等）：git init、补 .gitignore、生成 AGENTS.md（+ 指向它的 CLAUDE.md）、检查 .env 是否已被提交。

用法：python3 setup.py <项目根目录>
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "templates")


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    report = []

    if git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        git(root, "init", "-q")
        report.append("🟢 已建立 git 存档系统（git init）")
    else:
        root = git(root, "rev-parse", "--show-toplevel").stdout.strip()
        report.append("🟢 已经是 git 项目")

    if not git(root, "config", "user.email").stdout.strip():
        report.append("🟡 git 还不知道你是谁 —— 需要执行：git config --global user.name \"你的名字\" 和 "
                      "git config --global user.email \"你的邮箱\"（自动存档在没设时会用 vibe-guard 代签）")

    gi_path = os.path.join(root, ".gitignore")
    existing = open(gi_path, encoding="utf-8").read().splitlines() if os.path.exists(gi_path) else []
    wanted = open(os.path.join(TPL, "gitignore"), encoding="utf-8").read().splitlines()
    have = {l.strip() for l in existing}
    missing = [l for l in wanted if l.strip() and not l.startswith("#") and l.strip() not in have]
    if missing:
        with open(gi_path, "a", encoding="utf-8") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("# --- vibe-guard ---\n" + "\n".join(missing) + "\n")
        report.append(f"🟢 .gitignore 补上了 {len(missing)} 条规则（密钥、依赖包、系统垃圾文件）")
    else:
        report.append("🟢 .gitignore 已完整")

    # AGENTS.md 是唯一正本：Codex 直接读；Claude Code 读 CLAUDE.md，靠 @AGENTS.md 引用同一份
    agents, claude = os.path.join(root, "AGENTS.md"), os.path.join(root, "CLAUDE.md")
    had_agents, had_claude = os.path.exists(agents), os.path.exists(claude)
    if not had_agents and had_claude:
        report.append("🟡 只有 CLAUDE.md 没有 AGENTS.md —— Codex 读不到这些规则。"
                      "建议把 CLAUDE.md 内容搬进 AGENTS.md，CLAUDE.md 改成一行 @AGENTS.md（需用户同意）")
    elif not had_agents:
        shutil.copy(os.path.join(TPL, "AGENTS.md"), agents)
        report.append("🟢 已生成 AGENTS.md（给 AI 看的项目说明书），里面的 {…} 需要填写")
    else:
        report.append("🟢 AGENTS.md 已存在（未改动）")
    if not had_claude:
        with open(claude, "w", encoding="utf-8") as f:
            f.write("@AGENTS.md\n")
        report.append("🟢 已生成 CLAUDE.md（一行 @AGENTS.md，让 Claude Code 读同一份规则）")

    envs = [n for n in os.listdir(root) if n.startswith(".env") and not n.endswith((".example", ".sample", ".template"))]
    for n in envs:
        if git(root, "ls-files", "--error-unmatch", n).returncode == 0:
            report.append(f"🔴 {n} 已经被 git 提交过 —— 里面的密钥视为已泄露，要去原服务后台作废重发，"
                          f"并执行 git rm --cached {n}")
        elif git(root, "check-ignore", "-q", n).returncode != 0:
            report.append(f"🔴 {n} 没有被忽略（.gitignore 规则可能被覆盖），需要检查")
    history = git(root, "log", "--all", "--format=%h", "--diff-filter=A", "--", ".env", ".env.local", ".env.production").stdout.split()
    if history:
        report.append(f"🔴 git 历史里曾经提交过 .env（提交 {', '.join(history[:3])}）—— 里面的密钥视为已泄露，需要作废重发")

    print(f"项目根目录：{root}")
    print("\n".join(report))


if __name__ == "__main__":
    main()
