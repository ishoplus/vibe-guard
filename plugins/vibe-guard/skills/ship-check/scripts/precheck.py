#!/usr/bin/env python3
"""上线前自动检查（只读）：能用程序判断的安全问题全部在这里判，其余留给人工清单。

用法：python3 precheck.py <项目根目录> [--online]
  --online  另外联网检查依赖：已知漏洞（npm audit / pip-audit）+ 依赖包是否真实存在（见 deps_check.py）
输出：🔴 必须修 / 🟡 要确认 / 🟢 通过，每项附白话说明。
结果会写进 .vibe-guard/ship-check.json，部署命令的闸门（guard_bash）靠它判断能不能上线。
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib"))
from secret_scan import ENV_EXAMPLE, is_env_file, scan  # noqa: E402
from ship_state import save_check  # noqa: E402

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".venv", "venv", "__pycache__",
             ".svelte-kit", "coverage", ".vercel", "vendor"}
TEXT_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".py", ".rb", ".go", ".php",
            ".java", ".kt", ".swift", ".dart", ".json", ".yaml", ".yml", ".toml", ".html", ".sql", ".rules",
            ".env", ".md", ".txt", ".sh", ".cfg", ".ini"}
SERVER_PATH = re.compile(r"(^|/)(api|server|backend|functions|supabase/functions|netlify/functions|routes|lib/server)/"
                         r"|\.server\.[a-z]+$|(^|/)route\.[jt]s$")
PUBLIC_PREFIX = re.compile(r"\b(NEXT_PUBLIC_|VITE_|REACT_APP_|EXPO_PUBLIC_|NUXT_PUBLIC_|PUBLIC_)"
                           r"([A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE|OPENAI|ANTHROPIC|CLAUDE|STRIPE_SECRET|DATABASE_URL)[A-Z0-9_]*)")

red, yellow, green = [], [], []


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def files(root):
    r = git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    if r.returncode == 0:
        lst = r.stdout.splitlines()
    else:
        lst = []
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            lst += [os.path.relpath(os.path.join(d, f), root) for f in fs]
    return [f for f in lst if not (set(f.split("/")) & SKIP_DIRS)
            and (os.path.splitext(f)[1] in TEXT_EXT or os.path.basename(f).startswith(".env"))]


def read(root, f):
    try:
        return open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""


POLICY = re.compile(r"(?is)create\s+policy\s+(?:\"[^\"]*\"|\S+)\s+on\s+(?:public\.)?\"?(\w+)\"?(.*)")


def check_policies(sql, rls_tables):
    """RLS 开了但规则写成 using (true)，等于没开。"""
    with_policy = set()
    for stmt in sql.split(";"):
        m = POLICY.search(stmt)
        if not m:
            continue
        table, rest = m.group(1), m.group(2)
        with_policy.add(table)
        cmd = re.search(r"(?i)\bfor\s+(all|select|insert|update|delete)\b", rest)
        cmd = (cmd.group(1) if cmd else "all").lower()
        wide = re.search(r"(?i)\b(using|with\s+check)\s*\(\s*true\s*\)", rest)
        if not wide:
            continue
        if cmd == "select":
            yellow.append(f"Supabase 表 {table}：有一条规则让任何人都能读整张表 —— 确认这张表本来就该公开（例如商品列表），"
                          "如果存的是用户数据就要改成只能读自己的")
        else:
            red.append(f"Supabase 表 {table}：有一条规则（{cmd}）条件写成 true —— 任何人都能新增、修改或删除这张表的数据，"
                       "等于没设权限。要改成类似 auth.uid() = user_id 的条件")
    empty = sorted(rls_tables - with_policy)
    if empty:
        yellow.append(f"Supabase 这些表开了 RLS 但没写任何规则：{', '.join(empty)} —— 所有人（包括登录用户）都读写不了，"
                      "功能可能会坏；如果是故意只让后端用，可以忽略")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    online = "--online" in sys.argv
    root = os.path.abspath(args[0] if args else ".")
    is_git = git(root, "rev-parse", "--is-inside-work-tree").returncode == 0
    if is_git:
        root = git(root, "rev-parse", "--show-toplevel").stdout.strip()
    fl = files(root)
    texts = {f: read(root, f) for f in fl}

    # 1. 代码里的密钥
    leaks = []
    for f, t in texts.items():
        if is_env_file(f) or ENV_EXAMPLE.search(f):
            continue
        for name, desc, ln, masked in scan(t):
            leaks.append(f"{f}:{ln} {desc}（{masked}）")
    if leaks:
        red.append("代码文件里有真实密钥 —— 上线后任何人都可能拿到并盗刷：\n    " + "\n    ".join(leaks[:10]))
    else:
        green.append("代码文件里没有发现密钥")

    # 2. .env 状态 & git 历史
    if is_git:
        envs = [f for f in fl if is_env_file(f)]
        tracked = [f for f in envs if git(root, "ls-files", "--error-unmatch", f).returncode == 0]
        if tracked:
            red.append(f"{', '.join(tracked)} 被 git 提交了 —— 里面的密钥视为已泄露，要去原服务后台作废重发，再 git rm --cached")
        unignored = [f for f in envs if f not in tracked and git(root, "check-ignore", "-q", f).returncode != 0]
        if unignored:
            red.append(f"{', '.join(unignored)} 没有被 .gitignore 忽略，下次提交就会带上密钥")
        hist = git(root, "log", "--all", "-p", "--no-color", "--max-count=2000", "--format=@@COMMIT %h")
        cur, hist_leaks = "", []
        for line in hist.stdout.splitlines():
            if line.startswith("@@COMMIT "):
                cur = line.split()[1]
            elif line.startswith("+") and not line.startswith("+++"):
                for name, desc, _, masked in scan(line[1:]):
                    hist_leaks.append(f"提交 {cur}：{desc}（{masked}）")
        if hist_leaks:
            red.append("git 历史里曾经出现过密钥 —— 就算现在删了，历史里还在；推到 GitHub 就等于公开。"
                       "这些密钥必须作废重发：\n    " + "\n    ".join(sorted(set(hist_leaks))[:10]))
        elif not tracked and not unignored:
            green.append(".env 已被忽略，git 历史里没有发现密钥")
    else:
        yellow.append("项目不是 git 项目，无法检查历史 —— 建议先跑 safe-start")

    # 3. 前端暴露
    pub = sorted({m.group(0) for t in texts.values() for m in PUBLIC_PREFIX.finditer(t)})
    if pub:
        red.append(f"这些环境变量名带着「公开前缀」，会被打包进网页，任何人按 F12 都看得到：{', '.join(pub)}。"
                   "敏感密钥不能加这个前缀，要改成只在后端使用")
    browser_ai = [f for f, t in texts.items() if "dangerouslyAllowBrowser" in t
                  or (re.search(r"api\.(openai|anthropic)\.com", t) and not SERVER_PATH.search(f)
                      and os.path.splitext(f)[1] in {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html"})]
    if browser_ai:
        red.append(f"浏览器端代码直接调用 AI 服务：{', '.join(browser_ai[:5])} —— 密钥会暴露、会被盗刷。改成经过后端调用，并加每日次数上限")

    # 4. 数据库权限
    for f, t in texts.items():
        base = os.path.basename(f)
        if base.endswith(".rules") and re.search(r"allow\s+[\w\s,]+:\s*if\s+true", t):
            red.append(f"{f}：Firebase 权限规则是「所有人可读写」—— 任何人都能读光、改掉、删掉你的数据")
        elif base.endswith(".rules") and "request.time <" in t:
            yellow.append(f"{f}：Firebase 还在「测试模式」规则（到期前所有人可读写），上线前要改成正式规则")
        if base == "database.rules.json" and re.search(r"\"\.(read|write)\"\s*:\s*true", t):
            red.append(f"{f}：Realtime Database 规则是所有人可读写")
    uses_supabase = any("@supabase/supabase-js" in texts.get(p, "") for p in ("package.json",)) or \
        any("supabase" in f for f in fl)
    if uses_supabase:
        sql = "\n".join(t for f, t in texts.items() if f.endswith(".sql"))
        tables = set(re.findall(r"(?i)create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"?(\w+)", sql))
        rls = set(re.findall(r"(?i)alter\s+table\s+(?:public\.)?\"?(\w+)\"?\s+enable\s+row\s+level\s+security", sql))
        if tables - rls:
            red.append(f"Supabase 这些表没有开启 RLS（行级权限）：{', '.join(sorted(tables - rls))} —— "
                       "用网页里的公开 key 就能读写整张表")
        elif not tables:
            yellow.append("项目用了 Supabase，但找不到建表的 SQL —— 请到 Supabase 后台 Table Editor 确认每张表都开了 RLS")
        else:
            green.append("Supabase 建表 SQL 里每张表都开了 RLS")
        check_policies(sql, tables & rls)

    # 5. 其他配置
    for f, t in texts.items():
        if re.search(r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|origin\s*:\s*['\"]\*['\"]|allow_origins\s*=\s*\[\s*['\"]\*", t):
            yellow.append(f"{f}：CORS 允许任何网站调用你的后端。如果后端有登录或会花钱，要改成只允许自己的网址")
        if re.search(r"(?m)^\s*DEBUG\s*=\s*True|app\.run\([^)]*debug\s*=\s*True", t) and f.endswith(".py"):
            yellow.append(f"{f}：调试模式开着 —— 出错时会把内部信息显示给访客")
    if os.path.exists(os.path.join(root, "package.json")) and not any(
            os.path.exists(os.path.join(root, x)) for x in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock")):
        yellow.append("没有 lock 文件 —— 每次安装的依赖版本可能不同，线上和本地行为可能不一致")
    has_deps = any(os.path.exists(os.path.join(root, x)) for x in ("package.json", "requirements.txt", "pyproject.toml"))
    if online:
        from deps_check import run_all
        r, y, g = run_all(root)
        red.extend(r)
        yellow.extend(y)
        green.extend(g)
    elif has_deps:
        yellow.append("依赖没检查（漏洞、是否为 AI 编造的包名）—— 加上 --online 重跑")

    print(f"# 上线前自动检查：{root}\n")
    for title, lst in (("🔴 必须修（修好前不要上线）", red), ("🟡 要确认", yellow), ("🟢 通过", green)):
        print(f"## {title}")
        print("\n".join(f"- {x}" for x in lst) if lst else "- 无")
        print()
    print("自动检查只覆盖能用程序判断的部分。接下来照 references/manual-checklist.md 做人工检查。")
    if is_git:
        save_check(root, len(red), len(yellow))
        print("（结果已记录到 .vibe-guard/ship-check.json，部署时会用它判断检查是否还有效）")
    sys.exit(1 if red else 0)


if __name__ == "__main__":
    main()
