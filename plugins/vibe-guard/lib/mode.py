#!/usr/bin/env python3
"""使用者模式：beginner（新手，默认）/ expert（资深）。

两种模式的校验和护栏完全一样，差别只在「怎么说」：
- beginner：白话、四段说明、类比、教学
- expert：技术结论 + 一句话风险 + 更稳妥的做法，不做教学说明

优先顺序：环境变量 VIBE_GUARD_MODE > 项目设置 <项目>/.vibe-guard/config.json > 个人设置 ~/.vibe-guard.json > beginner

命令行：
  python3 mode.py get [<项目路径>]
  python3 mode.py set expert|beginner --project <项目路径>   只影响这个项目
  python3 mode.py set expert|beginner --user                 影响这台电脑上的所有项目
"""
import json
import os
import subprocess
import sys

MODES = ("beginner", "expert")
LABEL = {"beginner": "新手模式", "expert": "资深模式"}


def _root(path):
    r = subprocess.run(["git", "-C", path or ".", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else os.path.abspath(path or ".")


def _project_file(root):
    return os.path.join(root, ".vibe-guard", "config.json")


def _user_file():
    return os.path.join(os.path.expanduser("~"), ".vibe-guard.json")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("mode")
    except (OSError, ValueError, AttributeError):
        return None


def get_mode(cwd=None):
    """返回 (模式, 来源)。"""
    env = os.environ.get("VIBE_GUARD_MODE")
    if env in MODES:
        return env, "环境变量 VIBE_GUARD_MODE"
    if cwd:
        m = _read(_project_file(_root(cwd)))
        if m in MODES:
            return m, "项目设置"
    m = _read(_user_file())
    if m in MODES:
        return m, "个人设置"
    return "beginner", "默认"


def set_mode(mode, project=None, user=False):
    if mode not in MODES:
        raise ValueError(f"模式只能是 {' / '.join(MODES)}")
    path = _user_file() if user else _project_file(_root(project))
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    data["mode"] = mode
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main(argv):
    if len(argv) >= 1 and argv[0] == "get":
        mode, src = get_mode(argv[1] if len(argv) > 1 else ".")
        print(f"{LABEL[mode]}（{mode}，来自{src}）")
        return 0
    if len(argv) >= 2 and argv[0] == "set":
        if "--user" in argv:
            path = set_mode(argv[1], user=True)
        elif "--project" in argv and argv.index("--project") + 1 < len(argv):
            path = set_mode(argv[1], project=argv[argv.index("--project") + 1])
        else:
            print("要指定 --project <项目路径> 或 --user")
            return 2
        mode, src = get_mode(argv[argv.index("--project") + 1] if "--project" in argv else None)
        print(f"已设为{LABEL[argv[1]]}，写入 {path}")
        if mode != argv[1]:
            print(f"⚠️ 但目前实际生效的是{LABEL[mode]}（来自{src}，优先级更高）")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
