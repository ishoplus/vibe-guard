#!/usr/bin/env python3
"""PreToolUse(Bash)：不可逆 / 对外 / 花钱的命令，先让用户用白话确认。CC 与 Codex 共用。

这些命令有正当用途，要的是「用户知道后果再点头」，所以不直接禁止：
- CC：返回 ask，由 CC 弹出确认框，理由里写白话后果
- Codex：PreToolUse 不支持 ask（会当作 hook 失败并放行），改成先拦下，
  要求 AI 在对话里问用户；用户明确同意后，AI 在命令前加 CONFIRM_PREFIX 重跑才放行
唯一无条件拦截的是 git add 会把没被忽略的 .env 一起加进去。
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from compat import bash_command, host  # noqa: E402
from ship_state import gate, load_deploy, repo_root  # noqa: E402
from mode import get_mode  # noqa: E402

CONFIRM_PREFIX = "VIBE_GUARD_CONFIRMED=1 "

SAFE_RM_TARGETS = re.compile(
    r"^(\./)?(node_modules|dist|build|out|\.next|\.nuxt|\.turbo|\.cache|coverage|__pycache__|"
    r"\.pytest_cache|tmp|\.parcel-cache|\.svelte-kit|target)/?$"
)

# 为什么要先确认：三类原因
LOST = "做了就撤不回来 —— 这些改动或数据不在任何存档里，删掉就没了"
PUBLIC = "会直接影响真实用户，或把东西公开到网上，发出去就收不回"
EXPOSE = "会让你的电脑或网站暴露在风险里，出事往往要过一段时间才发现"

# (正则, 这条命令会做什么, 为什么要先确认, 更稳妥的做法)
RULES = [
    (r"\bgit\s+reset\s+--hard\b", "丢弃所有还没存档的改动，找不回来", LOST,
     "只想撤销某个文件，就只还原那个文件；不确定时先 `git stash` 把改动暂存起来，之后还能拿回来"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f", "永久删除所有没被 git 记录的新文件", LOST,
     "先用 `git clean -n` 列出会删掉哪些文件，确认后再删"),
    (r"\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)", "丢弃当前所有未存档的改动", LOST,
     "先 `git stash` 暂存起来，确定不要了再丢；或只还原某一个文件"),
    (r"\bgit\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b)", "强制覆盖远端（GitHub 上）的历史，别人的版本可能被抹掉", LOST,
     "先 `git pull` 把远端的新改动合并进来，再正常 push"),
    (r"\bgit\s+branch\s+-D\b", "强制删除一个分支，上面没合并的工作会丢", LOST,
     "用 `git branch -d`（小写），它会在分支还有没合并的工作时拒绝删除"),
    (r"(?i)\bdrop\s+(table|database|schema)\b", "删除整张数据表 / 整个数据库，里面的数据全部消失", LOST,
     "先确认连的是测试数据库而不是正式数据库；正式数据库要先备份"),
    (r"(?i)\btruncate\s+(table\s+)?\w", "清空整张数据表", LOST,
     "先确认连的是测试数据库；只想删部分数据就用带条件的 DELETE"),
    (r"(?i)\bdelete\s+from\s+\w+\s*(;|\"|'|$)", "删除整张表的所有数据（没有 WHERE 条件）", LOST,
     "加上 WHERE 条件只删要删的那几行；先用同样条件的 SELECT 看一下会删到哪些"),
    (r"\bprisma\s+migrate\s+reset\b", "重置数据库，所有数据会被清空", LOST,
     "确认这是本机的测试数据库；要改表结构用 `prisma migrate dev` 新增一个 migration"),
    (r"\bprisma\s+db\s+push\b.*--(force-reset|accept-data-loss)", "为了改表结构而接受数据丢失", LOST,
     "改成「先加新栏位、搬数据、再删旧栏位」，不用接受数据丢失"),
    (r"\bsupabase\s+db\s+reset\b", "重置数据库，所有数据会被清空", LOST,
     "确认这是本机的测试数据库；要改表结构就新增一个 migration 文件"),
    (r"\b(rails|rake)\s+db:(drop|reset)\b", "删除 / 重置数据库", LOST,
     "确认这是本机的测试数据库；要改表结构就新增一个 migration"),
    (r"(curl|wget)\s[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "从网上下载一段脚本并直接执行，内容没人检查过", EXPOSE,
     "先把脚本下载下来看一眼内容，确认来源是官方网站再执行"),
    (r"\bsudo\s", "用管理员权限执行，出错可能影响整台电脑", EXPOSE,
     "多数开发工具不需要管理员权限；装包失败通常是安装方式不对，换成不需要 sudo 的方式"),
    (r"\bchmod\s+(-R\s+)?777\b", "把文件权限开放给所有人，是常见的安全漏洞", EXPOSE,
     "只给需要的权限，例如 `chmod 755`（脚本）或 `chmod 644`（一般文件）"),
]
_RULES = [(re.compile(p), what, why, safer) for p, what, why, safer in RULES]

# 上线类命令：除了讲后果，还要带上「上线前检查」的状态
DEPLOY_RULES = [
    (r"\bvercel\b.*(\s--prod\b|\sdeploy\s+--prod)", "把当前代码发布到正式网站，真实用户会立刻看到"),
    (r"\bnetlify\s+deploy\b.*--prod", "把当前代码发布到正式网站，真实用户会立刻看到"),
    (r"\bfirebase\s+deploy\b", "发布到 Firebase 正式环境（包括数据库权限规则）"),
    (r"\b(railway\s+up|fly\s+deploy|wrangler\s+(deploy|publish))\b", "发布到线上服务器"),
    (r"\bnpm\s+publish\b", "把代码公开发布到 npm，全世界都能下载"),
]
_DEPLOY_RULES = [(re.compile(p), why) for p, why in DEPLOY_RULES]
DEPLOY_SAFER = "先做 ship-check；能先部署到预览环境（Preview）确认没问题，再上正式环境"
RM_SAFER = "先用 ls 看一下里面有什么；不确定时先把文件夹改名（mv），确认没问题再删"


def pushed_branches(cmd, root):
    """git push 会推到哪些分支（没写分支时就是当前分支）。"""
    out = []
    for m in re.finditer(r"\bgit\s+push\b([^;&|]*)", cmd):
        args = m.group(1).split()
        if any(a in ("--dry-run", "-n", "--tags", "--delete", "-d") for a in args):
            continue
        pos = [a for a in args if not a.startswith("-")]
        if len(pos) >= 2:
            out += [r.lstrip("+").split(":")[-1].replace("refs/heads/", "") for r in pos[1:]]
        else:
            cur = subprocess.run(["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
            out.append(cur)
    return out


def deploy_reason(cmd, root):
    for rx, why in _DEPLOY_RULES:
        if rx.search(cmd):
            return why
    # deploy-guide 记录过「推到某分支就自动上线」时，git push 到那个分支也算上线
    deploy = load_deploy(root) if root else None
    if deploy and deploy.get("auto_deploy_branch"):
        branch = deploy["auto_deploy_branch"]
        if branch in pushed_branches(cmd, root):
            where = deploy.get("platform") or "托管平台"
            return f"推送到 {branch} 分支 —— {where} 会自动把它发布到正式网站，真实用户会立刻看到"
    return None


def risky_rm(cmd):
    for m in re.finditer(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*\s+|-[a-zA-Z]*\s+-[rR]\s+|--recursive\s+)+([^;&|]+)", cmd):
        targets = [t for t in m.group(2).split() if not t.startswith("-")]
        if any(not SAFE_RM_TARGETS.match(t) for t in targets):
            return "递归删除文件夹，删掉的东西不进回收站"
    return None


def env_would_be_staged(cmd, cwd):
    if not re.search(r"\bgit\s+add\s+(-A\b|--all\b|\.(\s|$)|\*)", cmd) and not re.search(r"\bgit\s+commit\s+[^|;&]*-[a-zA-Z]*a", cmd):
        return None
    top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        return None
    root = top.stdout.strip()
    for name in os.listdir(root):
        if name.startswith(".env") and not re.search(r"\.(example|sample|template)$", name):
            if subprocess.run(["git", "-C", root, "check-ignore", "-q", name]).returncode != 0:
                return name
    return None


def ask(what, why, safer, on_codex, expert=False):
    """新手：会做什么 / 为什么要先确认 / 更稳妥的做法。资深：一行讲完，确认流程不变。"""
    if expert:
        if on_codex:
            sys.stderr.write(
                f"[vibe-guard] 已暂停：{what}。建议：{safer}。\n"
                f"用户确认后在原命令前加 `{CONFIRM_PREFIX.strip()}` 重跑；未经用户确认不得自行添加。")
            sys.exit(2)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "ask",
            "permissionDecisionReason": f"[vibe-guard] {what}。建议：{safer}"}}, ensure_ascii=False))
        sys.exit(0)
    if on_codex:
        sys.stderr.write(
            f"[vibe-guard] 这条命令已暂停。\n"
            f"📌 它会：{what}\n"
            f"❓ 为什么要先确认：{why}\n"
            f"✅ 更稳妥的做法：{safer}\n"
            "请先停下，用这三点加上「不做 / 换做法的话会怎样」向用户说明，问用户要怎么做，然后等回答。\n"
            f"只有用户在对话里明确同意执行原命令之后，才可以在原命令最前面加上 `{CONFIRM_PREFIX.strip()}` 重新执行。"
            "用户没有明确同意时，不许自己加这个前缀。"
        )
        sys.exit(2)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (f"[vibe-guard] 📌 这条命令会：{what}\n"
                                         f"❓ 为什么要先确认：{why}\n"
                                         f"✅ 更稳妥的做法：{safer}\n确定要执行吗？"),
        }
    }, ensure_ascii=False))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    cmd = bash_command(payload.get("tool_input"))
    cwd = payload.get("cwd") or os.getcwd()
    on_codex = host(payload) == "codex"
    expert = get_mode(cwd)[0] == "expert"

    leaked = env_would_be_staged(cmd, cwd)
    if leaked:
        sys.stderr.write(
            f"[vibe-guard] 已拦截：{leaked} 没有被 .gitignore 忽略，这条 git 命令会把里面的密钥一起提交。\n"
            "先把 `.env` 和 `.env.*`（以及 `!.env.example`）加进 .gitignore，再重新执行。"
        )
        sys.exit(2)

    if on_codex and cmd.lstrip().startswith(CONFIRM_PREFIX):
        sys.exit(0)  # 用户已在对话里确认过
    root = repo_root(cwd)
    why = deploy_reason(cmd, root)
    if why:
        ok, state = gate(root)
        if ok:
            ask(why, f"{PUBLIC}（{state}）", "发布后亲手走一遍核心流程；出问题先回滚", on_codex, expert)
        if expert:
            ask(f"{why}；⚠️ {state}", PUBLIC, "先跑 ship-check，或先部署到 Preview 验证", on_codex, expert)
        ask(why, f"{PUBLIC}。⚠️ {state}", DEPLOY_SAFER, on_codex)
    what = risky_rm(cmd)
    if what:
        ask(what, LOST, RM_SAFER, on_codex, expert)
    for rx, what, why, safer in _RULES:
        if rx.search(cmd):
            ask(what, why, safer, on_codex, expert)
    sys.exit(0)


if __name__ == "__main__":
    main()
