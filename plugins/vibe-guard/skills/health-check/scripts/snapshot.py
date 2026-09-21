#!/usr/bin/env python3
"""项目体检数据：规模、大文件、调试残留、跳过检查、空 catch、测试、依赖。

用法：python3 snapshot.py <项目根目录>
只读，不改任何文件。
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter

CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".py", ".rb", ".go", ".java", ".kt",
            ".swift", ".php", ".cs", ".rs", ".dart", ".html", ".css", ".scss"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".venv", "venv", "__pycache__",
             ".svelte-kit", "coverage", ".turbo", ".vercel", "target", "vendor"}
BIG_FILE = 400

CHECKS = {
    "调试残留（console.log / debugger）": re.compile(r"\bconsole\.log\(|\bdebugger\b"),
    "跳过检查（ts-ignore / any / eslint-disable / type: ignore / noqa）":
        re.compile(r"@ts-ignore|@ts-nocheck|:\s*any\b|as any\b|eslint-disable|#\s*type:\s*ignore|#\s*noqa"),
    "待办标记（TODO / FIXME / HACK）": re.compile(r"\b(TODO|FIXME|HACK|XXX)\b"),
    "写死的本机地址（localhost / 127.0.0.1）": re.compile(r"https?://(localhost|127\.0\.0\.1)"),
}
EMPTY_CATCH = re.compile(r"catch\s*(\([^)]*\))?\s*\{\s*\}|except[^:\n]*:\s*\n\s*pass\b")
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[a-z]+$|(^|/)test_[^/]+\.py$")


def list_files(root):
    r = subprocess.run(["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return [f for f in r.stdout.splitlines() if not (set(f.split("/")) & SKIP_DIRS)]
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        out += [os.path.relpath(os.path.join(d, f), root) for f in files]
    return out


def deps(root):
    out = []
    pj = os.path.join(root, "package.json")
    if os.path.exists(pj):
        try:
            data = json.load(open(pj, encoding="utf-8"))
            out.append(f"package.json：{len(data.get('dependencies', {}))} 个依赖、"
                       f"{len(data.get('devDependencies', {}))} 个开发依赖")
        except Exception:
            out.append("package.json：无法解析（格式有误）")
    rq = os.path.join(root, "requirements.txt")
    if os.path.exists(rq):
        n = sum(1 for l in open(rq, encoding="utf-8") if l.strip() and not l.startswith("#"))
        out.append(f"requirements.txt：{n} 个依赖")
    return out


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    files = [f for f in list_files(root) if os.path.splitext(f)[1] in CODE_EXT]
    lines_by_ext, sizes, hits, empty_catch = Counter(), [], {k: [] for k in CHECKS}, []
    tests = [f for f in files if TEST_FILE.search(f)]

    for f in files:
        try:
            text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        n = text.count("\n") + 1
        lines_by_ext[os.path.splitext(f)[1]] += n
        sizes.append((n, f))
        if f in tests:
            continue
        for name, rx in CHECKS.items():
            c = len(rx.findall(text))
            if c:
                hits[name].append((c, f))
        c = len(EMPTY_CATCH.findall(text))
        if c:
            empty_catch.append((c, f))

    print(f"# 体检数据：{root}\n")
    print(f"## 规模\n- 代码文件 {len(files)} 个，共 {sum(lines_by_ext.values())} 行")
    print("- 按类型：" + "、".join(f"{e} {n} 行" for e, n in lines_by_ext.most_common(6)))
    commits = subprocess.run(["git", "-C", root, "rev-list", "--count", "HEAD"], capture_output=True, text=True)
    if commits.returncode == 0:
        print(f"- 存档点（commit）{commits.stdout.strip()} 个")

    print(f"\n## 最大的文件（超过 {BIG_FILE} 行标 ⚠️）")
    for n, f in sorted(sizes, reverse=True)[:8]:
        print(f"- {'⚠️ ' if n > BIG_FILE else ''}{f}：{n} 行")

    print("\n## 需要注意的写法")
    print(f"- {'🔴' if empty_catch else '🟢'} 空的错误处理（错误被吞掉）：{sum(c for c, _ in empty_catch)} 处"
          + (f" —— {', '.join(f for _, f in sorted(empty_catch, reverse=True)[:5])}" if empty_catch else ""))
    for name, lst in hits.items():
        total = sum(c for c, _ in lst)
        mark = "🟢" if total == 0 else "🟡"
        top = ", ".join(f"{f}({c})" for c, f in sorted(lst, reverse=True)[:5])
        print(f"- {mark} {name}：{total} 处" + (f" —— {top}" if top else ""))

    print("\n## 测试")
    print(f"- {'🟡 没有任何测试文件' if not tests else f'🟢 {len(tests)} 个测试文件'}")

    d = deps(root)
    if d:
        print("\n## 依赖\n" + "\n".join(f"- {x}" for x in d))

    last = subprocess.run(["git", "-C", root, "log", "-1", "--format=%ci", "--", "HEALTH.md"],
                          capture_output=True, text=True).stdout.strip()
    print(f"\n上次体检：{last or '从未'}")


if __name__ == "__main__":
    main()
