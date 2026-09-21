"""密钥扫描：hook 与 ship-check 共用。

只收「误报率低」的规则 —— 新手看到误报会直接关掉护栏，宁可漏一点。
"""
import re

# (名称, 正则, 白话说明)
PATTERNS = [
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}", "Claude 的 API 密钥"),
    ("OpenAI API key", r"sk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{32,}", "OpenAI 的 API 密钥"),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b", "AWS 云服务的访问密钥"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "GitHub 的访问令牌"),
    ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b", "Google / Firebase 的 API 密钥"),
    ("Stripe secret key", r"\b[sr]k_live_[0-9A-Za-z]{20,}\b", "Stripe 正式环境的收款密钥"),
    ("Slack token", r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b", "Slack 的令牌"),
    ("Private key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "私钥文件内容"),
    ("Supabase service key", r"(?i)service_role[\"'\s:=]+eyJ[A-Za-z0-9_\-]{20,}", "Supabase 最高权限密钥"),
    ("Database URL with password", r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^:\s/]+:[^@\s]{3,}@", "带密码的数据库连接地址"),
]

_COMPILED = [(n, re.compile(p), d) for n, p, d in PATTERNS]

# 这些值一看就是占位符，不算泄露
_PLACEHOLDER = re.compile(r"(?i)(x{6,}|your[_\-]?|example|placeholder|dummy|<[^>]+>|\*{4,}|changeme)")


def scan(text):
    """返回 [(名称, 白话说明, 行号, 遮罩后的片段)]"""
    hits = []
    if not text:
        return hits
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, rx, desc in _COMPILED:
            m = rx.search(line)
            if not m or _PLACEHOLDER.search(m.group(0)):
                continue
            s = m.group(0)
            masked = s[:8] + "…" + s[-4:] if len(s) > 16 else s[:4] + "…"
            hits.append((name, desc, lineno, masked))
    return hits


# 允许放真实密钥的文件：.env 系列（前提是被 .gitignore 忽略）
ENV_FILE = re.compile(r"(^|/)\.env(\.[A-Za-z0-9_\-]+)?$")
ENV_EXAMPLE = re.compile(r"(^|/)\.env\.(example|sample|template)$")


def is_env_file(path):
    return bool(ENV_FILE.search(path or "")) and not ENV_EXAMPLE.search(path or "")
