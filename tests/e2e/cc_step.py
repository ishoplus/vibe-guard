#!/usr/bin/env python3
"""Claude Code 端到端试跑：跑一个阶段，记录实际调用了哪些 skill、改了哪些文件、执行了哪些命令、最后的回答。

用法：
  python3 tests/e2e/cc_step.py <项目目录> <编号> <new|continue> "<用户说的话>" [--model sonnet] [--expert]

- 直接从源码载入插件（--plugin-dir），改完插件不用重装
- 日志写到 <项目目录>/../logs/<编号>.md
- 非交互模式下，不在允许清单里的命令会被直接拒绝（真实使用时会弹确认），报告里的「被拒的工具」要对照着看
- --expert：用资深模式跑（设置 VIBE_GUARD_MODE=expert）

完整试跑的阶段设计与判读方式见 docs/开发与发布.md 的「端到端试跑」一节。
"""
import argparse
import json
import os
import subprocess

PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "vibe-guard"))
ALLOWED = ["Bash(git:*)", "Bash(python3:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(node:*)", "Bash(npm:*)",
           "Bash(mkdir:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(wc:*)", "Bash(head:*)", "Bash(curl:*)",
           "Bash(sleep:*)", "Bash(kill:*)", "Bash(lsof:*)", "Bash(pkill:*)", "Skill"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("num")
    ap.add_argument("mode", choices=["new", "continue"])
    ap.add_argument("prompt")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--expert", action="store_true")
    ap.add_argument("--allow", action="append", default=[], help="额外允许的工具，例如 'Bash(PORT=*)'")
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    logs = os.path.join(os.path.dirname(proj), "logs")
    os.makedirs(proj, exist_ok=True)
    os.makedirs(logs, exist_ok=True)
    cmd = ["claude", "-p", a.prompt, "--plugin-dir", PLUGIN, "--model", a.model,
           "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
           "--allowedTools", *ALLOWED, *a.allow]
    if a.mode == "continue":
        cmd.insert(2, "--continue")
    env = {**os.environ, **({"VIBE_GUARD_MODE": "expert"} if a.expert else {})}
    r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True, timeout=900, env=env)

    skills, bash, edits, denied, final = [], [], [], [], ""
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") != "tool_use":
                    continue
                name, inp = c.get("name"), c.get("input", {})
                if name == "Skill":
                    skills.append(inp.get("skill") or str(inp))
                elif name == "Bash":
                    bash.append(inp.get("command", "")[:160])
                elif name in ("Write", "Edit", "MultiEdit"):
                    edits.append(os.path.relpath(os.path.realpath(inp.get("file_path", "")), os.path.realpath(proj)))
        if ev.get("type") == "result":
            final = ev.get("result", "")
            denied = [d.get("tool_name") for d in ev.get("permission_denials", [])]

    text = "\n".join([
        f"## 阶段 {a.num}：{a.prompt}",
        f"- skill：{skills or '（无）'}",
        f"- 尝试改动的文件（含被拦下的）：{sorted(set(edits)) or '（无）'}",
        f"- 命令：{bash or '（无）'}",
        f"- 被拒的工具：{denied or '（无）'}",
        "", "### 最后回答", final, ""])
    with open(os.path.join(logs, f"{a.num}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    if r.returncode != 0:
        print("STDERR:", r.stderr[-800:])


if __name__ == "__main__":
    main()
