"""Claude Code / Codex 兼容层。

两边的 hook 协议大体相同（stdin JSON、hookSpecificOutput、exit 2 = 拦截），差异集中在：
- 宿主识别：Codex 给 plugin hook 设 PLUGIN_ROOT，事件里带 turn_id；CC 两者都没有
- 改文件：CC 是 Write/Edit/MultiEdit/NotebookEdit（file_path + 内容）；Codex 是 apply_patch（补丁文本）
- Bash 命令：CC 是字符串；Codex 可能是字符串或 argv 数组
- PreToolUse 的 ask：CC 支持；Codex 不支持（会当作 hook 失败并放行）
"""
import os
import shlex


def host(payload):
    forced = os.environ.get("VIBE_GUARD_HOST")
    if forced in ("claude", "codex"):
        return forced
    if os.environ.get("PLUGIN_ROOT") or "turn_id" in payload or payload.get("tool_name") == "apply_patch":
        return "codex"
    return "claude"


def bash_command(tool_input):
    cmd = (tool_input or {}).get("command", "")
    if isinstance(cmd, list):
        # ["bash", "-lc", "<script>"] 取脚本本体；其他 argv 还原成一行
        if len(cmd) >= 3 and os.path.basename(cmd[0]) in ("bash", "zsh", "sh") and cmd[1] in ("-c", "-lc"):
            return cmd[2]
        return shlex.join(str(c) for c in cmd)
    return cmd or ""


def parse_apply_patch(patch):
    """把 Codex 补丁拆成 [(路径, 新增的文字)]。删除的文件不列出。"""
    files, path, added = [], None, []

    def flush():
        if path is not None:
            files.append((path, "\n".join(added)))

    for line in (patch or "").splitlines():
        if line.startswith("*** Add File: ") or line.startswith("*** Update File: "):
            flush()
            path, added = line.split(": ", 1)[1].strip(), []
        elif line.startswith("*** Move to: ") and path is not None:
            path = line.split(": ", 1)[1].strip()
        elif line.startswith("*** Delete File: ") or line.startswith("*** End Patch"):
            flush()
            path, added = None, []
        elif path is not None and line.startswith("+"):
            added.append(line[1:])
    flush()
    return files


def edits(payload):
    """统一返回 [(绝对路径, 新增的文字)]。"""
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()
    if tool == "apply_patch":
        raw = ti.get("command") or ti.get("patch") or ti.get("input") or ""
        if isinstance(raw, list):
            raw = "\n".join(str(x) for x in raw)
        return [(p if os.path.isabs(p) else os.path.join(cwd, p), t) for p, t in parse_apply_patch(raw)]
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if tool == "Write":
        text = ti.get("content", "")
    elif tool == "Edit":
        text = ti.get("new_string", "")
    elif tool == "MultiEdit":
        text = "\n".join(e.get("new_string", "") for e in ti.get("edits", []))
    elif tool == "NotebookEdit":
        text = ti.get("new_source", "")
    else:
        return []
    return [(path, text)]
