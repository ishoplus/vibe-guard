#!/usr/bin/env python3
"""Stop：AI 每停一次，就把改动自动存成一个 git 存档点。

新手最大的调试痛点是「改坏了回不去」。这个 hook 让回退永远有得退，
不依赖任何人记得 commit。

按平台决定默认值：
- Codex：默认开启 —— Codex 没有内置的回退功能，git 是唯一退路
- Claude Code：默认关闭 —— CC 自带 checkpoint + /rewind，每次改文件都能退，
  再自动 commit 只会把 git 历史切碎。关闭时仍会扫描未提交的改动，发现密钥照样拦
强制开关：环境变量 VIBE_GUARD_AUTOSAVE=1 / 0；或在项目根目录放 .vibe-guard-autosave / .vibe-guard-no-autosave。

安全阀：
- 不是 git 项目、没有改动、正在 merge/rebase → 什么都不做
- 改动里有密钥 → 不存档，把问题丢回给 AI 处理
- .env 类文件没被忽略 → 从暂存里拿掉，照常存其余文件
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from compat import host  # noqa: E402
from secret_scan import is_env_file, scan  # noqa: E402
from mode import get_mode  # noqa: E402


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def say(msg):
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
    sys.exit(0)


def autosave_enabled(payload, root):
    env = os.environ.get("VIBE_GUARD_AUTOSAVE")
    if env in ("0", "1"):
        return env == "1"
    if os.path.exists(os.path.join(root, ".vibe-guard-no-autosave")):
        return False
    if os.path.exists(os.path.join(root, ".vibe-guard-autosave")):
        return True
    return host(payload) == "codex"


def block_on_secret(payload, hits, saved, root=None):
    detail = "；".join(f"{desc}（{masked}）" for _, desc, _, masked in hits[:3])
    if get_mode(root)[0] == "expert":
        names = "、".join(f"{n}（{masked}）" for n, _, _, masked in hits[:3])
        msg = f"[vibe-guard] {'未自动存档：' if saved else ''}未提交的改动含密钥：{names}。移到 .env。"
    else:
        msg = (f"[vibe-guard] {'这次没有自动存档：' if saved else ''}改动里出现了真实密钥 —— {detail}。"
               "请把密钥移到 .env 并确认 .gitignore 忽略它，然后"
               "用四段说明告诉用户：📌 要改成怎样 ｜ ❓ 为什么 ｜ ✅ 改了之后 ｜ ⚠️ 不改的话会怎样（标准讲法见 explain-plain 技能 references/why-library.md 的「密钥只放 .env，前端代码不放任何密钥」）。")
    if payload.get("stop_hook_active"):
        say(msg)  # 已经被拦过一次，不再阻止停止，免得死循环
    sys.stderr.write(msg)
    sys.exit(2)


def scan_only(root, payload):
    """不存档时也要守住密钥：扫描未提交的改动（已追踪文件的 diff + 新文件）。"""
    has_head = git(root, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
    diff = git(root, "diff", "HEAD" if has_head else "--cached", "-U0", "--no-color").stdout
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    for f in git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines():
        if is_env_file(f):
            continue
        try:
            with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                added.append(fh.read(200_000))
        except OSError:
            pass
    hits = scan("\n".join(added))
    if hits:
        block_on_secret(payload, hits, saved=False, root=root)
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    top = git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        sys.exit(0)
    root = top.stdout.strip()
    if not autosave_enabled(payload, root):
        scan_only(root, payload)
    gitdir = git(root, "rev-parse", "--git-dir").stdout.strip()
    gitdir = gitdir if os.path.isabs(gitdir) else os.path.join(root, gitdir)
    for busy in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        if os.path.exists(os.path.join(gitdir, busy)):
            sys.exit(0)
    if not git(root, "status", "--porcelain").stdout.strip():
        sys.exit(0)

    git(root, "add", "-A")
    staged = [f for f in git(root, "diff", "--cached", "--name-only").stdout.splitlines() if f]

    # .env 没被忽略：拿出来，不存它
    dropped = [f for f in staged if is_env_file(f)]
    for f in dropped:
        git(root, "reset", "-q", "--", f)
    staged = [f for f in staged if f not in dropped]
    if not staged:
        sys.exit(0)

    added = "\n".join(
        l[1:] for l in git(root, "diff", "--cached", "-U0", "--no-color").stdout.splitlines()
        if l.startswith("+") and not l.startswith("+++")
    )
    hits = scan(added)
    if hits:
        git(root, "reset", "-q")
        block_on_secret(payload, hits, saved=True, root=root)

    env = dict(os.environ)
    if not git(root, "config", "user.email").stdout.strip():
        env.update(GIT_AUTHOR_NAME="vibe-guard", GIT_AUTHOR_EMAIL="vibe-guard@localhost",
                   GIT_COMMITTER_NAME="vibe-guard", GIT_COMMITTER_EMAIL="vibe-guard@localhost")
    names = ", ".join(os.path.basename(f) for f in staged[:4]) + (" …" if len(staged) > 4 else "")
    r = subprocess.run(["git", "-C", root, "commit", "-q", "-m", f"autosave: {len(staged)} 个文件（{names}）"],
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        git(root, "reset", "-q")
        say(f"[vibe-guard] 自动存档失败：{(r.stderr or r.stdout).strip()[:200]}")

    note = f"💾 已自动存档 {len(staged)} 个文件。改坏了可以说「回到上一个存档」。"
    if dropped:
        note += f" ⚠️ {', '.join(dropped)} 没被 .gitignore 忽略，已跳过没存 —— 建议让 AI 修好 .gitignore。"
    say(note)


if __name__ == "__main__":
    main()
