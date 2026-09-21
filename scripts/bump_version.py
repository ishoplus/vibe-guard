#!/usr/bin/env python3
"""同步修改版本号：CC 的 plugin.json、Codex 的 plugin.json、CC 的 marketplace.json 三处一起改。

用法：python3 scripts/bump_version.py 0.7.0
（Codex 的 .agents/plugins/marketplace.json 没有版本字段，不用改）
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = [
    "plugins/vibe-guard/.claude-plugin/plugin.json",
    "plugins/vibe-guard/.codex-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def versions():
    out = {}
    for f in FILES:
        with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
            data = json.load(fh)
        v = data.get("version") or next((p.get("version") for p in data.get("plugins", [])
                                        if p.get("name") == "vibe-guard"), None)
        out[f] = v
    return out


def main():
    if len(sys.argv) != 2 or not SEMVER.match(sys.argv[1]):
        print(__doc__)
        print("当前版本：", versions())
        sys.exit(2)
    new = sys.argv[1]
    old = set(versions().values())
    for f in FILES:
        p = os.path.join(ROOT, f)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        # 只替换 version 字段的值，保留原有格式与其余内容
        text, n = re.subn(r'("version"\s*:\s*")[^"]+(")', rf"\g<1>{new}\g<2>", text)
        if n != 1:
            print(f"❌ {f} 里找到 {n} 个 version 字段，预期 1 个，没有修改")
            sys.exit(1)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    got = set(versions().values())
    if got != {new}:
        print(f"❌ 修改后版本不一致：{versions()}")
        sys.exit(1)
    print(f"✅ 版本 {', '.join(sorted(old))} → {new}（{len(FILES)} 个文件）")
    print("接下来：在 CHANGELOG.md 写这一版的内容，然后按 docs/开发与发布.md 的发版清单走")


if __name__ == "__main__":
    main()
