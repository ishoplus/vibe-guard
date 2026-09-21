"""上线闸门的共享状态：ship-check 写，guard_bash 读。

存在项目根目录的 .vibe-guard/ 下（safe-start 会把它加进 .gitignore）：
- ship-check.json：最近一次 precheck 的结果 + 当时的代码指纹
- deploy.json：deploy-guide 记录的部署方式（哪个分支一推就上线）

指纹是「文件内容」的哈希而不是 commit：Codex 的自动存档会一直产生新 commit，
但只要代码内容没变，检查结果就仍然有效。
"""
import hashlib
import json
import os
import subprocess
import time

STATE_DIR = ".vibe-guard"
# vibe-guard 自己写的文档，改了不代表要重新检查
DOC_FILES = {"HEALTH.md", "INCIDENTS.md", "SPEC.md", "AGENTS.md", "CLAUDE.md"}


def _git(root, *args, **kw):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, **kw)


def repo_root(cwd):
    r = _git(cwd, "rev-parse", "--show-toplevel")
    return r.stdout.strip() if r.returncode == 0 else None


def fingerprint(root):
    files = _git(root, "ls-files", "-co", "--exclude-standard", "-z").stdout.split("\0")
    files = sorted({f for f in files if f and not f.startswith(STATE_DIR + "/") and f not in DOC_FILES
                    and os.path.isfile(os.path.join(root, f))})
    if not files:
        return hashlib.sha256(b"").hexdigest()
    hashes = _git(root, "hash-object", "--stdin-paths", input="\n".join(files)).stdout.split()
    h = hashlib.sha256()
    for f, blob in zip(files, hashes):
        h.update(f"{f}\0{blob}\n".encode())
    return h.hexdigest()


def _path(root, name):
    return os.path.join(root, STATE_DIR, name)


def _load(root, name):
    try:
        with open(_path(root, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(root, name, data):
    os.makedirs(os.path.join(root, STATE_DIR), exist_ok=True)
    with open(_path(root, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_check(root, red, yellow):
    _save(root, "ship-check.json", {"time": int(time.time()), "red": red, "yellow": yellow,
                                    "fingerprint": fingerprint(root)})


def load_deploy(root):
    return _load(root, "deploy.json")


def save_deploy(root, data):
    _save(root, "deploy.json", data)


def gate(root):
    """返回 (是否通过, 白话说明)。"""
    if not root:
        return False, "这里不是 git 项目，无法确认是否做过上线前检查"
    state = _load(root, "ship-check.json")
    if not state:
        return False, "这个项目还没做过上线前检查（ship-check）"
    if state.get("red"):
        return False, f"上次上线前检查还有 {state['red']} 项必须修的问题（🔴）没解决"
    if state.get("fingerprint") != fingerprint(root):
        days = max(0, int((time.time() - state.get("time", 0)) / 86400))
        when = "今天" if days == 0 else f"{days} 天前"
        return False, f"上线前检查是{when}做的，之后代码又改过，检查结果已经不算数"
    return True, "上线前检查已通过，且之后代码没有改动"
