"""vibe-guard hook 与脚本的确定性测试。

执行：python3 -m unittest discover -s tests -v
测试里的「假密钥」一律在运行时拼接，避免仓库本身被密钥扫描器误报。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "vibe-guard")
HOOKS = os.path.join(ROOT, "hooks")
FAKE_ANT = "sk-" + "ant-" + "api03-" + "Q7rT9mZ2kL4pW8nB5vC1dF6gH3jK0sA"
FAKE_AWS = "AKI" + "A" + "Q3M7T2R9W5Z1K8P4"
CODEX = {"turn_id": "t1"}  # 带 turn_id 的事件会被识别为 Codex


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# 测试不能被本机的个人设置（~/.vibe-guard.json）或环境变量影响
TEST_HOME = tempfile.mkdtemp()
os.environ["HOME"] = TEST_HOME
os.environ.pop("VIBE_GUARD_MODE", None)


def run(script, payload, cwd=None, env=None):
    return subprocess.run([sys.executable, script], input=json.dumps(payload), capture_output=True,
                          text=True, cwd=cwd, env={**os.environ, **(env or {})})


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)


def make_repo(ignore_env=True):
    d = tempfile.mkdtemp()
    git(d, "init", "-q")
    git(d, "config", "user.email", "t@t")
    git(d, "config", "user.name", "t")
    if ignore_env:
        write(os.path.join(d, ".gitignore"), ".env\n.env.*\n!.env.example\n")
    return d


class GuardWrite(unittest.TestCase):
    S = os.path.join(HOOKS, "guard_write.py")

    def test_blocks_secret_in_code(self):
        d = make_repo()
        r = run(self.S, {"tool_name": "Write", "tool_input": {
            "file_path": f"{d}/src/ai.js", "content": f'const key = "{FAKE_ANT}";'}})
        self.assertEqual(r.returncode, 2)
        self.assertIn("Claude 的 API 密钥", r.stderr)
        self.assertNotIn(FAKE_ANT, r.stderr)  # 回显时要遮罩
        self.assertNotIn("OpenAI", r.stderr)  # 同一个密钥不能被两条规则重复报告

    def test_blocks_secret_in_edit_and_multiedit(self):
        d = make_repo()
        r = run(self.S, {"tool_name": "Edit", "tool_input": {"file_path": f"{d}/a.py", "new_string": FAKE_AWS}})
        self.assertEqual(r.returncode, 2)
        r = run(self.S, {"tool_name": "MultiEdit", "tool_input": {"file_path": f"{d}/a.py",
                                                                  "edits": [{"new_string": "x"}, {"new_string": FAKE_AWS}]}})
        self.assertEqual(r.returncode, 2)

    def test_allows_placeholder(self):
        d = make_repo()
        r = run(self.S, {"tool_name": "Write", "tool_input": {
            "file_path": f"{d}/.env.example", "content": "ANTHROPIC_API_KEY=sk-ant-your-key-here"}})
        self.assertEqual(r.returncode, 0)
        r = run(self.S, {"tool_name": "Write", "tool_input": {
            "file_path": f"{d}/README.md", "content": "export KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"}})
        self.assertEqual(r.returncode, 0)

    def test_allows_secret_in_ignored_env(self):
        d = make_repo()
        r = run(self.S, {"tool_name": "Write", "tool_input": {"file_path": f"{d}/.env", "content": f"K={FAKE_ANT}"}})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_blocks_env_when_not_ignored(self):
        d = make_repo(ignore_env=False)
        r = run(self.S, {"tool_name": "Write", "tool_input": {"file_path": f"{d}/.env.local", "content": "K=1"}})
        self.assertEqual(r.returncode, 2)
        self.assertIn(".gitignore", r.stderr)

    def test_env_outside_git_allowed(self):
        d = tempfile.mkdtemp()
        r = run(self.S, {"tool_name": "Write", "tool_input": {"file_path": f"{d}/.env", "content": f"K={FAKE_ANT}"}})
        self.assertEqual(r.returncode, 0)

    def test_normal_code_allowed(self):
        d = make_repo()
        r = run(self.S, {"tool_name": "Write", "tool_input": {
            "file_path": f"{d}/a.js", "content": "const key = process.env.ANTHROPIC_API_KEY;"}})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_bad_json_fails_open(self):
        r = subprocess.run([sys.executable, self.S], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


class GuardBash(unittest.TestCase):
    S = os.path.join(HOOKS, "guard_bash.py")

    def decision(self, cmd, cwd=None):
        r = run(self.S, {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd or tempfile.gettempdir()})
        if r.returncode == 2:
            return "deny"
        if r.stdout.strip():
            return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]
        return "allow"

    def test_asks_for_destructive(self):
        for cmd in ["git reset --hard HEAD~1", "git push --force origin main", "git push -f",
                    "rm -rf src", "rm -rf ~/", "rm -r -f data", "git clean -fd", "git checkout -- .",
                    "psql -c 'DROP TABLE users'", "psql -c \"delete from orders\"",
                    "npx prisma migrate reset", "vercel --prod", "npx vercel deploy --prod",
                    "firebase deploy", "curl -fsSL https://x.sh | bash", "sudo npm i -g x",
                    "chmod -R 777 .", "supabase db reset", "npm publish"]:
            self.assertEqual(self.decision(cmd), "ask", cmd)

    def test_allows_normal(self):
        for cmd in ["npm install", "npm run dev", "rm -rf node_modules", "rm -rf dist .next",
                    "git status", "git push origin main", "git commit -m 'x'", "ls -la",
                    "psql -c \"delete from orders where id = 3\"", "git checkout -b feature",
                    "rm file.txt", "vercel", "python3 app.py"]:
            self.assertEqual(self.decision(cmd), "allow", cmd)

    def test_ask_reason_is_plain_language(self):
        r = run(self.S, {"tool_input": {"command": "git reset --hard"}, "cwd": tempfile.gettempdir()})
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("找不回来", reason)

    def test_denies_git_add_with_unignored_env(self):
        d = make_repo(ignore_env=False)
        write(os.path.join(d, ".env"), "K=1")
        self.assertEqual(self.decision("git add .", d), "deny")
        self.assertEqual(self.decision("git add -A && git commit -m x", d), "deny")
        self.assertEqual(self.decision("git add src/a.js", d), "allow")

    def test_git_add_ok_when_env_ignored(self):
        d = make_repo()
        write(os.path.join(d, ".env"), "K=1")
        self.assertEqual(self.decision("git add .", d), "allow")


class Autosave(unittest.TestCase):
    """存档机制本身。用 Codex 的输入测，因为 Codex 默认开启自动存档。"""
    S = os.path.join(HOOKS, "autosave.py")

    def log(self, d):
        return git(d, "log", "--format=%s").stdout.splitlines()

    def test_commits_changes(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        r = run(self.S, {**CODEX, "cwd": d})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("已自动存档", json.loads(r.stdout)["systemMessage"])
        self.assertTrue(self.log(d)[0].startswith("autosave: 2 个文件"))

    def test_noop_when_clean_or_not_repo(self):
        d = make_repo()
        run(self.S, {**CODEX, "cwd": d})
        n = len(self.log(d))
        r = run(self.S, {**CODEX, "cwd": d})
        self.assertEqual((r.returncode, r.stdout, len(self.log(d))), (0, "", n))
        r = run(self.S, {"cwd": tempfile.mkdtemp()})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_blocks_on_secret_and_leaves_nothing_staged(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), f'k="{FAKE_ANT}"')
        r = run(self.S, {**CODEX, "cwd": d})
        self.assertEqual(r.returncode, 2)
        self.assertIn("没有自动存档", r.stderr)
        self.assertEqual(self.log(d), [])
        self.assertEqual(git(d, "diff", "--cached", "--name-only").stdout, "")

    def test_secret_second_time_does_not_block(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), f'k="{FAKE_ANT}"')
        r = run(self.S, {**CODEX, "cwd": d, "stop_hook_active": True})
        self.assertEqual(r.returncode, 0)
        self.assertIn("没有自动存档", json.loads(r.stdout)["systemMessage"])

    def test_skips_unignored_env(self):
        d = make_repo(ignore_env=False)
        write(os.path.join(d, ".env"), "DB=1")
        write(os.path.join(d, "a.js"), "x")
        r = run(self.S, {**CODEX, "cwd": d})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(".env", json.loads(r.stdout)["systemMessage"])
        self.assertNotIn(".env", git(d, "ls-files").stdout.split())

    def test_opt_out(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        run(self.S, {**CODEX, "cwd": d}, env={"VIBE_GUARD_AUTOSAVE": "0"})
        self.assertEqual(self.log(d), [])
        write(os.path.join(d, ".vibe-guard-no-autosave"), "")
        run(self.S, {**CODEX, "cwd": d})
        self.assertEqual(self.log(d), [])

    def test_no_git_identity(self):
        d = tempfile.mkdtemp()
        git(d, "init", "-q")
        write(os.path.join(d, "a.js"), "x")
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
        r = run(self.S, {**CODEX, "cwd": d}, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("已自动存档", r.stdout)


class AutosaveClaude(unittest.TestCase):
    """CC 默认不自动存档（有 checkpoint / rewind），但仍要在停下时拦住密钥。"""
    S = os.path.join(HOOKS, "autosave.py")

    def log(self, d):
        return git(d, "log", "--format=%s").stdout.splitlines()

    def test_default_off_on_claude(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        r = run(self.S, {"cwd": d})
        self.assertEqual((r.returncode, r.stdout, self.log(d)), (0, "", []))

    def test_still_blocks_secret_in_new_file(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), f'k="{FAKE_ANT}"')
        r = run(self.S, {"cwd": d})
        self.assertEqual(r.returncode, 2)
        self.assertIn("改动里出现了真实密钥", r.stderr)
        self.assertEqual(self.log(d), [])

    def test_still_blocks_secret_in_tracked_file(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "init")
        write(os.path.join(d, "a.js"), f'k="{FAKE_AWS}"')
        self.assertEqual(run(self.S, {"cwd": d}).returncode, 2)

    def test_secret_in_ignored_env_is_fine(self):
        d = make_repo()
        write(os.path.join(d, ".env"), f"K={FAKE_ANT}")
        self.assertEqual(run(self.S, {"cwd": d}).returncode, 0)

    def test_opt_in(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        run(self.S, {"cwd": d}, env={"VIBE_GUARD_AUTOSAVE": "1"})
        self.assertEqual(len(self.log(d)), 1)
        write(os.path.join(d, "b.js"), "x")
        write(os.path.join(d, ".vibe-guard-autosave"), "")
        run(self.S, {"cwd": d})
        self.assertEqual(len(self.log(d)), 2)


class SessionStart(unittest.TestCase):
    S = os.path.join(HOOKS, "session_start.py")

    def ctx(self, d):
        r = run(self.S, {"cwd": d})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        return out["additionalContext"]

    def test_rules_injected(self):
        c = self.ctx(make_repo())
        self.assertIn("新手模式", c)
        self.assertIn("debug-rescue", c)

    def test_platform_section(self):
        d = make_repo()
        self.assertIn("平台：Claude Code", self.ctx(d))
        r = run(self.S, {"cwd": d}, env={"PLUGIN_ROOT": ROOT})
        c = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("平台：Codex", c)
        self.assertNotIn("/rewind", c)

    def test_warns_not_git(self):
        self.assertIn("还不是 git 项目", self.ctx(tempfile.mkdtemp()))

    def test_warns_env_exposed_and_tracked(self):
        d = make_repo(ignore_env=False)
        write(os.path.join(d, ".env"), "K=1")
        self.assertIn("没有被 .gitignore 忽略", self.ctx(d))
        git(d, "add", ".env")
        git(d, "commit", "-qm", "x")
        self.assertIn("已经被 git 提交过", self.ctx(d))


class Scripts(unittest.TestCase):
    SETUP = os.path.join(ROOT, "skills", "safe-start", "scripts", "setup.py")
    PRECHECK = os.path.join(ROOT, "skills", "ship-check", "scripts", "precheck.py")
    SNAPSHOT = os.path.join(ROOT, "skills", "health-check", "scripts", "snapshot.py")

    def sh(self, script, d):
        return subprocess.run([sys.executable, script, d], capture_output=True, text=True)

    def test_setup_idempotent(self):
        d = tempfile.mkdtemp()
        write(os.path.join(d, ".gitignore"), "mystuff/\n")
        r1 = self.sh(self.SETUP, d)
        self.assertIn("已建立 git", r1.stdout)
        gi = read(os.path.join(d, ".gitignore"))
        self.assertTrue(gi.startswith("mystuff/"))
        self.assertIn(".env", gi)
        self.assertIn("{项目名}", read(os.path.join(d, "AGENTS.md")))
        self.assertEqual(read(os.path.join(d, "CLAUDE.md")), "@AGENTS.md\n")
        r2 = self.sh(self.SETUP, d)
        self.assertIn(".gitignore 已完整", r2.stdout)
        self.assertEqual(read(os.path.join(d, ".gitignore")), gi)

    def test_setup_keeps_existing_claude_md(self):
        d = make_repo()
        write(os.path.join(d, "CLAUDE.md"), "# 我的规则\n")
        r = self.sh(self.SETUP, d)
        self.assertIn("只有 CLAUDE.md 没有 AGENTS.md", r.stdout)
        self.assertEqual(read(os.path.join(d, "CLAUDE.md")), "# 我的规则\n")
        self.assertFalse(os.path.exists(os.path.join(d, "AGENTS.md")))

    def test_setup_flags_committed_env(self):
        d = make_repo(ignore_env=False)
        write(os.path.join(d, ".env"), "K=1")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "x")
        r = self.sh(self.SETUP, d)
        self.assertIn("🔴 .env 已经被 git 提交过", r.stdout)
        self.assertIn("git 历史里曾经提交过 .env", r.stdout)

    def test_precheck_clean_project_passes(self):
        d = make_repo()
        write(os.path.join(d, "app.js"), "const k = process.env.OPENAI_API_KEY;\n")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "x")
        r = self.sh(self.PRECHECK, d)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_precheck_catches_problems(self):
        d = make_repo()
        os.makedirs(os.path.join(d, "src"))
        os.makedirs(os.path.join(d, "supabase", "migrations"))
        write(os.path.join(d, "old.js"), f'k="{FAKE_AWS}"')
        git(d, "add", "-A")
        git(d, "commit", "-qm", "leak")
        os.remove(os.path.join(d, "old.js"))
        write(os.path.join(d, "src", "chat.tsx"), 
            "const c = new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true })")
        write(os.path.join(d, "firestore.rules"), "match /{d=**} { allow read, write: if true; }")
        write(os.path.join(d, "supabase", "migrations", "1.sql"), 
            "create table notes (id int);\ncreate table users (id int);\n"
            "alter table users enable row level security;\n")
        r = self.sh(self.PRECHECK, d)
        self.assertEqual(r.returncode, 1)
        for s in ["git 历史里曾经出现过密钥", "VITE_OPENAI_API_KEY", "浏览器端代码直接调用 AI",
                  "所有人可读写", "没有开启 RLS（行级权限）：notes"]:
            self.assertIn(s, r.stdout)
        self.assertNotIn("users", r.stdout.split("没有开启 RLS")[1].split("\n")[0])

    def test_snapshot_runs(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "try { x() } catch (e) {}\nconsole.log(1)\n// TODO\n")
        write(os.path.join(d, "a.test.js"), "console.log(1)\n")
        r = self.sh(self.SNAPSHOT, d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("🔴 空的错误处理（错误被吞掉）：1 处", r.stdout)
        self.assertIn("调试残留（console.log / debugger）：1 处", r.stdout)  # 测试文件不计
        self.assertIn("1 个测试文件", r.stdout)


class Codex(unittest.TestCase):
    """Codex 的 hook 输入：改文件走 apply_patch，事件里带 turn_id，plugin hook 有 PLUGIN_ROOT。"""
    W = os.path.join(HOOKS, "guard_write.py")
    B = os.path.join(HOOKS, "guard_bash.py")

    def patch(self, d, body):
        return {"tool_name": "apply_patch", "turn_id": "t1", "cwd": d,
                "tool_input": {"command": "*** Begin Patch\n" + body + "\n*** End Patch"}}

    def test_patch_add_file_with_secret_blocked(self):
        d = make_repo()
        r = run(self.W, self.patch(d, f"*** Add File: src/ai.js\n+const k = 1;\n+const key = \"{FAKE_ANT}\";"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("ai.js", r.stderr)
        self.assertIn("第 2 行", r.stderr)

    def test_patch_update_only_checks_added_lines(self):
        d = make_repo()
        body = f"*** Update File: a.js\n@@\n-const key = \"{FAKE_ANT}\";\n+const key = process.env.KEY;"
        r = run(self.W, self.patch(d, body))
        self.assertEqual(r.returncode, 0, r.stderr)  # 删掉密钥是好事，不能拦

    def test_patch_multi_file_and_env(self):
        d = make_repo()
        body = f"*** Add File: .env\n+K={FAKE_ANT}\n*** Add File: b.js\n+ok()"
        self.assertEqual(run(self.W, self.patch(d, body)).returncode, 0)
        d2 = make_repo(ignore_env=False)
        r = run(self.W, self.patch(d2, "*** Add File: b.js\n+ok()\n*** Add File: .env\n+K=1"))
        self.assertEqual(r.returncode, 2)
        self.assertIn(".gitignore", r.stderr)

    def test_patch_move_to_env(self):
        d = make_repo(ignore_env=False)
        r = run(self.W, self.patch(d, "*** Update File: notes.txt\n*** Move to: .env\n@@\n+K=1"))
        self.assertEqual(r.returncode, 2)

    def test_bash_confirm_flow(self):
        base = {"tool_name": "Bash", "turn_id": "t1", "cwd": tempfile.gettempdir()}
        r = run(self.B, {**base, "tool_input": {"command": "git reset --hard HEAD~1"}})
        self.assertEqual(r.returncode, 2)  # Codex 不支持 ask，改为拦下并要求先问用户
        self.assertIn("VIBE_GUARD_CONFIRMED=1", r.stderr)
        self.assertIn("找不回来", r.stderr)
        r = run(self.B, {**base, "tool_input": {"command": "VIBE_GUARD_CONFIRMED=1 git reset --hard HEAD~1"}})
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_bash_argv_form(self):
        base = {"tool_name": "Bash", "turn_id": "t1", "cwd": tempfile.gettempdir()}
        r = run(self.B, {**base, "tool_input": {"command": ["bash", "-lc", "rm -rf src"]}})
        self.assertEqual(r.returncode, 2)
        r = run(self.B, {**base, "tool_input": {"command": ["git", "push", "--force"]}})
        self.assertEqual(r.returncode, 2)
        r = run(self.B, {**base, "tool_input": {"command": ["npm", "install"]}})
        self.assertEqual(r.returncode, 0)

    def test_confirm_prefix_ignored_on_claude(self):
        r = run(self.B, {"tool_name": "Bash", "cwd": tempfile.gettempdir(),
                         "tool_input": {"command": "VIBE_GUARD_CONFIRMED=1 git reset --hard"}})
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_env_does_not_leak_through_confirm(self):
        d = make_repo(ignore_env=False)
        write(os.path.join(d, ".env"), "K=1")
        r = run(self.B, {"tool_name": "Bash", "turn_id": "t1", "cwd": d,
                         "tool_input": {"command": "VIBE_GUARD_CONFIRMED=1 git add ."}})
        self.assertEqual(r.returncode, 2)

    def test_host_detected_from_plugin_root_env(self):
        r = run(self.B, {"tool_name": "Bash", "cwd": tempfile.gettempdir(),
                         "tool_input": {"command": "git push -f"}}, env={"PLUGIN_ROOT": ROOT})
        self.assertEqual(r.returncode, 2)

    def test_stop_and_session_start_accept_codex_payload(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        r = run(os.path.join(HOOKS, "autosave.py"),
                {"hook_event_name": "Stop", "turn_id": "t1", "cwd": d, "stop_hook_active": False,
                 "last_assistant_message": "done", "model": "gpt-5.5"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("systemMessage", json.loads(r.stdout))  # Codex 的 Stop 要求 stdout 是 JSON
        r = run(os.path.join(HOOKS, "session_start.py"),
                {"hook_event_name": "SessionStart", "source": "startup", "cwd": d})
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("没有 AGENTS.md / CLAUDE.md", ctx)


LIB = os.path.join(ROOT, "lib")
DEPLOY_SCRIPTS = os.path.join(ROOT, "skills", "deploy-guide", "scripts")
SHIP_SCRIPTS = os.path.join(ROOT, "skills", "ship-check", "scripts")
for _p in (LIB, SHIP_SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def precheck(d, *extra):
    return subprocess.run([sys.executable, os.path.join(SHIP_SCRIPTS, "precheck.py"), d, *extra],
                          capture_output=True, text=True)


class ShipState(unittest.TestCase):
    def setUp(self):
        import ship_state
        self.ss = ship_state

    def test_fingerprint_ignores_commits_docs_and_state(self):
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        fp = self.ss.fingerprint(d)
        git(d, "add", "-A")
        git(d, "commit", "-qm", "autosave")          # Codex 自动存档不应该让检查失效
        write(os.path.join(d, "HEALTH.md"), "体检")   # vibe-guard 自己的文档也不算
        os.makedirs(os.path.join(d, ".vibe-guard"))
        write(os.path.join(d, ".vibe-guard", "x.json"), "{}")
        self.assertEqual(self.ss.fingerprint(d), fp)
        write(os.path.join(d, "a.js"), "y")
        self.assertNotEqual(self.ss.fingerprint(d), fp)

    def test_gate_states(self):
        d = make_repo()
        write(os.path.join(d, "app.js"), "ok()")
        self.assertIn("还没做过", self.ss.gate(d)[1])
        self.ss.save_check(d, red=2, yellow=0)
        self.assertIn("2 项必须修", self.ss.gate(d)[1])
        self.ss.save_check(d, red=0, yellow=1)
        self.assertTrue(self.ss.gate(d)[0])
        write(os.path.join(d, "app.js"), "changed()")
        ok, why = self.ss.gate(d)
        self.assertFalse(ok)
        self.assertIn("之后代码又改过", why)


class DeployGate(unittest.TestCase):
    B = os.path.join(HOOKS, "guard_bash.py")

    def reason(self, d, cmd, codex=False):
        payload = {"tool_name": "Bash", "cwd": d, "tool_input": {"command": cmd}, **(CODEX if codex else {})}
        r = run(self.B, payload)
        if codex:
            return r.returncode, r.stderr
        if not r.stdout.strip():
            return None
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_deploy_reports_gate_status(self):
        d = make_repo()
        write(os.path.join(d, "app.js"), "const k = process.env.KEY;")
        self.assertIn("还没做过上线前检查", self.reason(d, "vercel --prod"))
        self.assertEqual(precheck(d).returncode, 0)
        self.assertIn("上线前检查已通过", self.reason(d, "vercel --prod"))
        write(os.path.join(d, "app.js"), "changed()")
        self.assertIn("之后代码又改过", self.reason(d, "npx vercel deploy --prod"))

    def test_codex_deploy_blocked_with_status(self):
        d = make_repo()
        code, err = self.reason(d, "firebase deploy", codex=True)
        self.assertEqual(code, 2)
        self.assertIn("ship-check", err)
        self.assertIn("VIBE_GUARD_CONFIRMED=1", err)

    def test_git_push_to_auto_deploy_branch_is_a_deploy(self):
        import ship_state
        d = make_repo()
        write(os.path.join(d, "a.js"), "x")
        git(d, "add", "-A")
        git(d, "commit", "-qm", "init")
        git(d, "branch", "-M", "main")
        self.assertIsNone(self.reason(d, "git push"))  # 还没记录部署方式时，push 就是普通 push
        ship_state.save_deploy(d, {"platform": "Vercel", "auto_deploy_branch": "main"})
        self.assertIn("Vercel 会自动", self.reason(d, "git push"))
        self.assertIn("Vercel 会自动", self.reason(d, "git push origin main"))
        self.assertIsNone(self.reason(d, "git push --dry-run origin main"))
        git(d, "checkout", "-qb", "feature")
        self.assertIsNone(self.reason(d, "git push -u origin feature"))
        self.assertIsNone(self.reason(d, "git push"))
        self.assertIn("Vercel 会自动", self.reason(d, "git push origin feature:main"))

    def test_record_deploy_script(self):
        import ship_state
        d = make_repo()
        r = subprocess.run([sys.executable, os.path.join(DEPLOY_SCRIPTS, "record_deploy.py"), d, "--platform", "Netlify",
                            "--url", "https://x.netlify.app", "--auto-deploy-branch", "main"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("还没记录回滚方法", r.stdout)
        self.assertEqual(ship_state.load_deploy(d)["auto_deploy_branch"], "main")


class Policies(unittest.TestCase):
    def test_rls_policy_content(self):
        d = make_repo()
        os.makedirs(os.path.join(d, "supabase", "migrations"))
        write(os.path.join(d, "supabase", "migrations", "1.sql"),
              "create table notes (id int); alter table notes enable row level security;\n"
              "create table products (id int); alter table products enable row level security;\n"
              "create table secrets (id int); alter table secrets enable row level security;\n"
              'create policy "anyone" on public.notes for all using (true);\n'
              'create policy "read" on products for select using ( true );\n'
              'create policy "own" on public.notes for select using (auth.uid() = user_id);\n')
        r = precheck(d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Supabase 表 notes：有一条规则（all）条件写成 true", r.stdout)
        self.assertIn("Supabase 表 products：有一条规则让任何人都能读", r.stdout)
        self.assertIn("开了 RLS 但没写任何规则：secrets", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(d, ".vibe-guard", "ship-check.json")))


class DepsCheck(unittest.TestCase):
    def setUp(self):
        import deps_check
        self.dc = deps_check

    def fake_fetch(self, url):
        if "downloads" in url:
            return (200, {"downloads": 5}) if "tiny" in url else (200, {"downloads": 900000})
        if "does-not-exist" in url or "fake-pkg" in url:
            return 404, None
        if "brand-new" in url:
            return 200, {"time": {"created": "2099-01-01T00:00:00Z"},
                         "releases": {"0.1": [{"upload_time_iso_8601": "2099-01-01T00:00:00Z"}]}}
        return 200, {"time": {"created": "2015-01-01T00:00:00Z"},
                     "releases": {"1.0": [{"upload_time_iso_8601": "2015-01-01T00:00:00Z"}]}}

    def no_run(self, *a, **kw):
        raise AssertionError("不该调用外部命令")

    def test_parsing_skips_non_registry_specs(self):
        d = tempfile.mkdtemp()
        write(os.path.join(d, "package.json"), json.dumps({
            "dependencies": {"react": "^18", "local": "file:../x", "gh": "github:a/b", "alias": "npm:react@18"},
            "devDependencies": {"vite": "5"}}))
        write(os.path.join(d, "requirements.txt"), "requests>=2\n# c\n-r other.txt\ngit+https://x\nflask[async]==3\n")
        self.assertEqual(self.dc.npm_packages(d), ["react", "vite"])
        self.assertEqual(self.dc.pip_packages(d), ["requests", "flask"])

    def test_registry_checks(self):
        d = tempfile.mkdtemp()
        write(os.path.join(d, "package.json"), json.dumps({"dependencies": {
            "react": "18", "does-not-exist": "1", "brand-new": "1", "tiny": "1"}}))
        write(os.path.join(d, "requirements.txt"), "fake-pkg\nrequests\n")
        red, yellow, green = self.dc.run_all(d, fetch=self.fake_fetch, run=self.no_run)
        text = "\n".join(red + yellow + green)
        self.assertIn("npm 上找不到 `does-not-exist`", text)
        self.assertIn("PyPI 上找不到 `fake-pkg`", text)
        self.assertIn("`brand-new`：发布才", text)
        self.assertIn("`tiny`：上周只有 5 次下载", text)
        self.assertEqual(len(red), 2)

    def test_offline_is_reported_not_silent(self):
        d = tempfile.mkdtemp()
        write(os.path.join(d, "package.json"), json.dumps({"dependencies": {"react": "18"}}))
        red, yellow, _ = self.dc.run_all(d, fetch=lambda u: (0, None), run=self.no_run)
        self.assertEqual(red, [])
        self.assertTrue(any("连不上包仓库" in y for y in yellow))

    def test_npm_audit_parsing(self):
        d = tempfile.mkdtemp()
        write(os.path.join(d, "package.json"), "{}")
        write(os.path.join(d, "package-lock.json"), "{}")

        class R:
            stdout = json.dumps({"metadata": {"vulnerabilities": {"critical": 1, "high": 2, "moderate": 0, "low": 3}}})
        import shutil
        if not shutil.which("npm"):
            self.skipTest("没有 npm")
        red, _, _ = self.dc.run_all(d, fetch=self.fake_fetch, run=lambda *a, **k: R())
        self.assertTrue(any("1 个严重、2 个高危" in x for x in red))


class AuditFailures(unittest.TestCase):
    """没查成绝不能显示成「没有漏洞」—— 这是在国内 npm 镜像上实际踩到的坑。"""

    def setUp(self):
        import shutil
        import deps_check
        if not shutil.which("npm"):
            self.skipTest("没有 npm")
        self.dc = deps_check
        self.d = tempfile.mkdtemp()
        write(os.path.join(self.d, "package.json"), "{}")
        write(os.path.join(self.d, "package-lock.json"), "{}")

    def fake(self, outputs):
        calls = []

        class R:
            def __init__(self, out):
                self.stdout = out

        def run(cmd, **kw):
            calls.append(cmd)
            return R(outputs[len(calls) - 1])
        return run, calls

    MIRROR_ERROR = json.dumps({"message": "404 Not Found - POST https://registry.npmmirror.com/-/npm/v1/security/audits/quick",
                               "statusCode": 404, "error": {"code": "E404"}})
    OK = json.dumps({"metadata": {"vulnerabilities": {"critical": 0, "high": 1, "moderate": 0, "low": 0}}})

    def test_mirror_retries_official_registry(self):
        run, calls = self.fake([self.MIRROR_ERROR, self.OK])
        _, yellow, green = self.dc.run_all(self.d, fetch=lambda u: (0, None), run=run)
        self.assertIn("--registry=https://registry.npmjs.org/", calls[1])
        self.assertTrue(any("1 个高危" in y and "已改用官方仓库" in y for y in yellow))
        self.assertFalse(any("npm audit" in g for g in green))

    def test_both_fail_is_not_green(self):
        run, _ = self.fake([self.MIRROR_ERROR, "not json"])
        _, yellow, green = self.dc.run_all(self.d, fetch=lambda u: (0, None), run=run)
        self.assertTrue(any("漏洞没查成" in y for y in yellow))
        self.assertFalse(any("npm audit" in g for g in green))


class SmokeTest(unittest.TestCase):
    """用本机的假网站测 smoke_test.py。"""

    @classmethod
    def setUpClass(cls):
        import http.server
        import threading

        class H(http.server.BaseHTTPRequestHandler):
            leak = False

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/broken":
                    self.send_response(500)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if self.path == "/.env" and H.leak:
                    self.wfile.write(b"SECRET_KEY=abc\n")
                else:
                    self.wfile.write(b"<html>home</html>")  # 像单页应用：任何路径都回首页

        cls.H = H
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def smoke(self, *paths):
        return subprocess.run([sys.executable, os.path.join(DEPLOY_SCRIPTS, "smoke_test.py"), self.url, *paths],
                              capture_output=True, text=True, timeout=60)

    def test_reports_http_broken_page_and_headers(self):
        self.H.leak = False
        r = self.smoke("/login", "/broken")
        self.assertEqual(r.returncode, 1)
        self.assertIn("/login 正常", r.stdout)
        self.assertIn("/broken 返回 500", r.stdout)
        self.assertIn("不是 HTTPS", r.stdout)
        self.assertIn("CSP", r.stdout)
        self.assertNotIn("防止浏览器把文件当成别的类型执行", r.stdout)  # 这个头有设
        self.assertIn("没有发现 .env、.git 这类文件被公开", r.stdout)  # 单页应用回首页不算泄露

    def test_detects_exposed_env(self):
        self.H.leak = True
        r = self.smoke()
        self.assertIn("/.env 可以直接下载", r.stdout)
        self.H.leak = False


WHY_LIBRARY = os.path.join(ROOT, "skills", "explain-plain", "references", "why-library.md")


class Explanations(unittest.TestCase):
    """除了引导，还要讲清楚：要做什么 / 为什么 / 做了之后 / 不做的风险。"""

    def library(self):
        import re
        entries = {}
        for block in re.split(r"(?m)^## ", read(WHY_LIBRARY))[1:]:
            title, _, body = block.partition("\n")
            entries[title.strip()] = body
        return entries

    def test_every_library_entry_has_four_parts_and_risk_level(self):
        entries = self.library()
        self.assertGreaterEqual(len(entries), 15)
        for title, body in entries.items():
            for mark in ("📌 **要做什么**", "❓ **为什么**", "✅ **做了之后**", "⚠️ **不做的话**"):
                self.assertIn(mark, body, f"「{title}」缺 {mark}")
            risk = [l for l in body.splitlines() if "⚠️" in l][0]
            self.assertRegex(risk, r"很常见|偶尔|少见但严重|严重", f"「{title}」没标风险等级")

    def test_referenced_entries_exist(self):
        import re
        titles = set(self.library())
        sources = [read(os.path.join(HOOKS, f)) for f in ("guard_write.py", "autosave.py")]
        sources += [read(os.path.join(ROOT, "skills", n, "SKILL.md")) for n in os.listdir(os.path.join(ROOT, "skills"))]
        cited = set()
        for src in sources:
            for m in re.finditer(r"why-library(?:\.md)?[^「\n]{0,12}「([^」]+)」(?:「([^」]+)」)?", src):
                cited.update(x for x in m.groups() if x)
        self.assertTrue(cited)
        self.assertEqual(cited - titles, set(), "引用了说明库里不存在的条目")

    def test_skills_that_ask_users_to_act_point_to_library(self):
        for n in ("safe-start", "small-steps", "ship-check", "deploy-guide", "explain-plain"):
            self.assertIn("why-library.md", read(os.path.join(ROOT, "skills", n, "SKILL.md")), n)

    def test_session_rules_define_four_parts(self):
        r = run(os.path.join(HOOKS, "session_start.py"), {"cwd": make_repo()})
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        for part in ("📌 要做什么", "❓ 为什么", "✅ 做了之后", "⚠️ 不做的话", "不吓唬人"):
            self.assertIn(part, ctx)

    def test_every_bash_rule_has_reason_and_safer_way(self):
        sys.path.insert(0, HOOKS)
        import importlib
        gb = importlib.import_module("guard_bash")
        for pattern, what, why, safer in gb.RULES:
            self.assertTrue(what and why and len(safer) > 10, pattern)

    def test_confirm_messages_explain(self):
        d = tempfile.gettempdir()
        r = run(os.path.join(HOOKS, "guard_bash.py"), {"tool_input": {"command": "rm -rf src"}, "cwd": d})
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        for part in ("📌 这条命令会", "❓ 为什么要先确认", "✅ 更稳妥的做法"):
            self.assertIn(part, reason)
        r = run(os.path.join(HOOKS, "guard_bash.py"), {**CODEX, "tool_input": {"command": "sudo rm x"}, "cwd": d})
        for part in ("📌 它会", "❓ 为什么要先确认", "✅ 更稳妥的做法", "VIBE_GUARD_CONFIRMED=1"):
            self.assertIn(part, r.stderr)


MODE_PY = os.path.abspath(os.path.join(ROOT, "lib", "mode.py"))


class Modes(unittest.TestCase):
    """新手 / 资深：校验完全一样，只有说法不同。"""

    def setUp(self):
        for f in (os.path.join(TEST_HOME, ".vibe-guard.json"),):
            if os.path.exists(f):
                os.remove(f)

    def set_mode(self, *args):
        return subprocess.run([sys.executable, MODE_PY, "set", *args], capture_output=True, text=True)

    def mode_of(self, d, env=None):
        r = subprocess.run([sys.executable, MODE_PY, "get", d], capture_output=True, text=True,
                           env={**os.environ, **(env or {})})
        return r.stdout

    def test_priority_env_project_user_default(self):
        d = make_repo()
        self.assertIn("新手模式（beginner，来自默认）", self.mode_of(d))
        self.set_mode("expert", "--user")
        self.assertIn("资深模式（expert，来自个人设置）", self.mode_of(d))
        r = self.set_mode("beginner", "--project", d)
        self.assertIn("已设为新手模式", r.stdout)
        self.assertIn("新手模式（beginner，来自项目设置）", self.mode_of(d))
        self.assertIn("来自环境变量", self.mode_of(d, {"VIBE_GUARD_MODE": "expert"}))
        r = self.set_mode("expert", "--project", d, )
        self.assertNotIn("⚠️", r.stdout)
        os.environ["VIBE_GUARD_MODE"] = "beginner"
        try:
            r = self.set_mode("expert", "--project", d)
            self.assertIn("实际生效的是新手模式", r.stdout)  # 被更高优先级盖住时要讲清楚
        finally:
            os.environ.pop("VIBE_GUARD_MODE")

    def test_project_setting_from_subdirectory(self):
        d = make_repo()
        os.makedirs(os.path.join(d, "src", "deep"))
        self.set_mode("expert", "--project", d)
        self.assertIn("资深模式", self.mode_of(os.path.join(d, "src", "deep")))

    def test_session_context_by_mode(self):
        d = make_repo()
        beginner = json.loads(run(os.path.join(HOOKS, "session_start.py"), {"cwd": d}).stdout)["hookSpecificOutput"]["additionalContext"]
        self.set_mode("expert", "--project", d)
        expert = json.loads(run(os.path.join(HOOKS, "session_start.py"), {"cwd": d}).stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("新手模式", beginner)
        self.assertIn("📌 要做什么", beginner)
        self.assertIn("资深模式", expert)
        self.assertNotIn("📌 要做什么", expert)
        for rule in ("如实报告完成度", "调试熔断", "密钥", "先确认", "ship-check", "incident-rescue"):
            self.assertIn(rule, expert, f"资深模式也必须保留：{rule}")
        self.assertIn(f'{MODE_PY}" set beginner --project', expert)  # 能切回去
        self.assertLess(len(expert), len(beginner))

    def test_bash_confirm_still_happens_but_terse(self):
        d = make_repo()
        self.set_mode("expert", "--project", d)
        r = run(os.path.join(HOOKS, "guard_bash.py"), {"tool_input": {"command": "git reset --hard"}, "cwd": d})
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertNotIn("❓", out["permissionDecisionReason"])
        self.assertIn("git stash", out["permissionDecisionReason"])
        r = run(os.path.join(HOOKS, "guard_bash.py"), {**CODEX, "tool_input": {"command": "vercel --prod"}, "cwd": d})
        self.assertEqual(r.returncode, 2)
        self.assertIn("还没做过上线前检查", r.stderr)  # 部署闸门照样检查
        self.assertIn("VIBE_GUARD_CONFIRMED=1", r.stderr)
        self.assertNotIn("❓", r.stderr)

    def test_secret_still_blocked_but_terse(self):
        d = make_repo()
        self.set_mode("expert", "--project", d)
        r = run(os.path.join(HOOKS, "guard_write.py"), {"tool_name": "Write", "cwd": d, "tool_input": {
            "file_path": f"{d}/a.js", "content": f'k="{FAKE_ANT}"'}})
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("四段", r.stderr)
        self.assertIn("环境变量", r.stderr)
        self.assertNotIn(FAKE_ANT, r.stderr)
        write(os.path.join(d, "b.js"), f'k="{FAKE_AWS}"')
        r = run(os.path.join(HOOKS, "autosave.py"), {"cwd": d})
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("四段", r.stderr)

    def test_switch_takes_effect_immediately_for_hooks(self):
        d = make_repo()
        cmd = {"tool_input": {"command": "rm -rf src"}, "cwd": d}
        self.assertIn("❓", run(os.path.join(HOOKS, "guard_bash.py"), cmd).stdout)
        self.set_mode("expert", "--project", d)
        self.assertNotIn("❓", run(os.path.join(HOOKS, "guard_bash.py"), cmd).stdout)

    def test_every_skill_has_expert_section(self):
        for n in os.listdir(os.path.join(ROOT, "skills")):
            text = read(os.path.join(ROOT, "skills", n, "SKILL.md"))
            self.assertIn("## 资深模式", text, n)
            self.assertIn("照做", text.split("## 资深模式")[1].split("## ")[0], f"{n} 的资深模式要写明哪些校验照做")


class Structure(unittest.TestCase):
    def test_skills_follow_spec(self):
        import re
        sk = os.path.join(ROOT, "skills")
        names = sorted(os.listdir(sk))
        self.assertEqual(len(names), 9)
        for n in names:
            text = read(os.path.join(sk, n, "SKILL.md"))
            fm = text.split("---")[1]
            self.assertRegex(fm, rf"(?m)^name: {re.escape(n)}$")
            self.assertNotRegex(fm, r"(?m)^version:", f"{n}：version 要放 metadata 下，Codex 不接受顶层 version")
            desc = fm.split("description:")[1].split("\nmetadata:")[0]
            self.assertLessEqual(len(desc.strip().lstrip(">").strip()), 1024, n)
            self.assertLess(text.count("\n"), 500, n)
            refs_dir = os.path.join(sk, n, "references")
            if os.path.isdir(refs_dir):
                for ref in os.listdir(refs_dir):
                    self.assertIn(f"references/{ref}", text, f"{n} 缺少 {ref} 的路标")

    def test_manifests_agree(self):
        cc = json.loads(read(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        cx = json.loads(read(os.path.join(ROOT, ".codex-plugin", "plugin.json")))
        mk = json.loads(read(os.path.join(ROOT, "..", "..", ".claude-plugin", "marketplace.json")))
        entry = [p for p in mk["plugins"] if p["name"] == "vibe-guard"][0]
        self.assertEqual((cc["name"], cc["version"]), (cx["name"], cx["version"]))
        self.assertEqual(entry["version"], cc["version"], "marketplace 里的版本号要和 plugin.json 一致")
        self.assertNotIn("hooks", cx)  # 不写就走默认 hooks/hooks.json，两边共用同一份

    def test_bump_version_script(self):
        import shutil
        repo = os.path.abspath(os.path.join(ROOT, "..", ".."))
        tmp = tempfile.mkdtemp()
        for rel in ("scripts", "plugins/vibe-guard/.claude-plugin", "plugins/vibe-guard/.codex-plugin", ".claude-plugin"):
            shutil.copytree(os.path.join(repo, rel), os.path.join(tmp, rel))
        script = os.path.join(tmp, "scripts", "bump_version.py")
        r = subprocess.run([sys.executable, script, "9.8.7"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for rel in ("plugins/vibe-guard/.claude-plugin/plugin.json", "plugins/vibe-guard/.codex-plugin/plugin.json",
                    ".claude-plugin/marketplace.json"):
            self.assertIn('"9.8.7"', read(os.path.join(tmp, rel)), rel)
        self.assertNotEqual(subprocess.run([sys.executable, script, "v1"], capture_output=True).returncode, 0)

    def test_hooks_json_paths_exist(self):
        cfg = json.loads(read(os.path.join(HOOKS, "hooks.json")))
        for groups in cfg["hooks"].values():
            for g in groups:
                for h in g["hooks"]:
                    self.assertIn("timeout", h)
                    path = h["command"].split('"')[1].replace("${CLAUDE_PLUGIN_ROOT}", ROOT)
                    self.assertTrue(os.path.exists(path), path)


if __name__ == "__main__":
    unittest.main()
