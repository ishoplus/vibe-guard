#!/usr/bin/env python3
"""依赖检查（需要联网）：已知漏洞 + 依赖包是否真实可信。

vibe coding 特有的风险：AI 会「编」出听起来合理但不存在的包名，攻击者会抢先注册这些名字放恶意代码
（slopsquatting）。所以除了跑漏洞扫描，还要逐个确认依赖包真实存在、不是刚冒出来的、有人在用。

单独执行：python3 deps_check.py <项目根目录>
precheck.py --online 会调用这里的 run_all()。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

NPM_REGISTRY = os.environ.get("VIBE_GUARD_NPM_REGISTRY", "https://registry.npmjs.org").rstrip("/")
NPM_DOWNLOADS = "https://api.npmjs.org/downloads/point/last-week"
PYPI = os.environ.get("VIBE_GUARD_PYPI", "https://pypi.org/pypi").rstrip("/")
NEW_DAYS = 30        # 发布不到这么多天的包，要人工确认
LOW_DOWNLOADS = 100  # 每周下载量低于这个数，要人工确认
MAX_PACKAGES = 150


def default_fetch(url):
    """返回 (HTTP 状态码, 解析后的 JSON 或 None)。连不上时状态码为 0。"""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),
                                    timeout=8) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def npm_packages(root):
    try:
        with open(os.path.join(root, "package.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    names = []
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            spec = str(spec)
            # 本地路径、git、别名、workspace 都不是从公共仓库装的，跳过
            if re.match(r"(file:|link:|workspace:|npm:|git|github:|https?:)", spec) or "/" in spec and ":" in spec:
                continue
            names.append(name)
    return names


def pip_packages(root):
    names = []
    req = os.path.join(root, "requirements.txt")
    if os.path.exists(req):
        with open(req, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if not line or line.startswith(("-", "git+", "http", ".", "/")):
                    continue
                m = re.match(r"[A-Za-z0-9][A-Za-z0-9._\-]*", line)
                if m:
                    names.append(m.group(0))
    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            import tomllib
            with open(pyproject, "rb") as f:
                deps = (tomllib.load(f).get("project") or {}).get("dependencies") or []
            for d in deps:
                m = re.match(r"[A-Za-z0-9][A-Za-z0-9._\-]*", d)
                if m:
                    names.append(m.group(0))
        except Exception:
            pass
    return sorted(set(names), key=names.index)


def _age_days(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).days
    except Exception:
        return None


def check_npm(name, fetch):
    code, data = fetch(f"{NPM_REGISTRY}/{urllib.parse.quote(name, safe='@')}")
    if code == 404:
        return "red", f"npm 上找不到 `{name}` —— 这个包不存在，很可能是 AI 编出来的名字。千万别装同名的包，先确认正确名称"
    if code != 200 or not data:
        return "unknown", name
    age = _age_days((data.get("time") or {}).get("created", ""))
    dl_code, dl = fetch(f"{NPM_DOWNLOADS}/{urllib.parse.quote(name, safe='@')}")
    downloads = (dl or {}).get("downloads") if dl_code == 200 else None
    notes = []
    if age is not None and age < NEW_DAYS:
        notes.append(f"发布才 {age} 天")
    if downloads is not None and downloads < LOW_DOWNLOADS:
        notes.append(f"上周只有 {downloads} 次下载")
    if notes:
        return "yellow", f"npm 包 `{name}`：{'、'.join(notes)} —— 可能是冒名或恶意包，确认这真是你要的那个包"
    return "ok", name


def check_pypi(name, fetch):
    code, data = fetch(f"{PYPI}/{urllib.parse.quote(name)}/json")
    if code == 404:
        return "red", f"PyPI 上找不到 `{name}` —— 这个包不存在，很可能是 AI 编出来的名字。千万别装同名的包，先确认正确名称"
    if code != 200 or not data:
        return "unknown", name
    uploads = [f.get("upload_time_iso_8601", "") for files in (data.get("releases") or {}).values() for f in files]
    ages = [a for a in (_age_days(u) for u in uploads if u) if a is not None]
    if ages and max(ages) < NEW_DAYS:
        return "yellow", f"PyPI 包 `{name}`：第一次发布才 {max(ages)} 天 —— 可能是冒名或恶意包，确认这真是你要的那个包"
    return "ok", name


OFFICIAL_NPM = "https://registry.npmjs.org/"


def _parse_npm_audit(stdout):
    """成功时返回各等级数量；失败（例如镜像不支持漏洞查询）返回 None —— 绝不能把失败当成 0 个漏洞。"""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    v = (data.get("metadata") or {}).get("vulnerabilities")
    if not isinstance(v, dict) or "error" in data:
        return None
    return {k: int(v.get(k, 0)) for k in ("critical", "high", "moderate", "low")}


def audit_npm(root, run):
    """返回 (结果, 说明)。结果为 None 表示没查成，说明里写原因。"""
    if not os.path.exists(os.path.join(root, "package-lock.json")):
        return None, "缺 package-lock.json —— 先 `npm install` 生成 lock 文件再检查"
    if not shutil.which("npm"):
        return None, "这台电脑没装 npm"
    r = run(["npm", "audit", "--json"], cwd=root, capture_output=True, text=True, timeout=120)
    res = _parse_npm_audit(r.stdout)
    if res is not None:
        return res, ""
    # 国内常用的 npm 镜像不支持漏洞查询接口，改问官方仓库
    r = run(["npm", "audit", "--json", f"--registry={OFFICIAL_NPM}"], cwd=root, capture_output=True, text=True,
            timeout=120)
    res = _parse_npm_audit(r.stdout)
    if res is not None:
        return res, "（当前的 npm 镜像不支持漏洞查询，已改用官方仓库）"
    return None, "npm audit 没有成功（常见原因：用了国内镜像且连不上官方仓库）"


def audit_pip(root, run):
    """返回 (漏洞数, 说明)。漏洞数为 None 表示没查成。"""
    if not shutil.which("pip-audit"):
        return None, "没装 pip-audit —— 可执行 `pip install pip-audit` 后重跑"
    r = run(["pip-audit", "-r", "requirements.txt", "-f", "json", "--progress-spinner", "off"],
            cwd=root, capture_output=True, text=True, timeout=300)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return None, "pip-audit 没有成功（可能是网络问题，或 requirements.txt 里有装不了的包）"
    deps = data.get("dependencies") if isinstance(data, dict) else data
    if not isinstance(deps, list):
        return None, "pip-audit 的输出看不懂，没查成"
    return sum(len(d.get("vulns", [])) for d in deps if isinstance(d, dict)), ""


def run_all(root, fetch=default_fetch, run=subprocess.run):
    red, yellow, green = [], [], []

    # 1. 已知漏洞
    if os.path.exists(os.path.join(root, "package.json")):
        npm, note = audit_npm(root, run)
        if npm is None:
            yellow.append(f"npm 依赖的漏洞没查成：{note}")
        elif npm["critical"] or npm["high"]:
            (red if npm["critical"] else yellow).append(
                f"npm audit：{npm['critical']} 个严重、{npm['high']} 个高危漏洞{note} —— 执行 `npm audit fix`，"
                "修不掉的逐个看是否影响你的用法")
        else:
            green.append(f"npm audit：没有严重 / 高危漏洞（中危 {npm['moderate']}、低危 {npm['low']}）{note}")
    if os.path.exists(os.path.join(root, "requirements.txt")):
        n, note = audit_pip(root, run)
        if n is None:
            yellow.append(f"Python 依赖的漏洞没查成：{note}")
        elif n:
            yellow.append(f"pip-audit：{n} 个已知漏洞 —— 升级对应的包")
        else:
            green.append("pip-audit：没有已知漏洞")

    # 2. 依赖包是否真实可信
    jobs = [(check_npm, n) for n in npm_packages(root)] + [(check_pypi, n) for n in pip_packages(root)]
    jobs = jobs[:MAX_PACKAGES]
    if jobs:
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(lambda j: j[0](j[1], fetch), jobs))
        unknown = [d for s, d in results if s == "unknown"]
        red += [d for s, d in results if s == "red"]
        yellow += [d for s, d in results if s == "yellow"]
        if len(unknown) == len(results):
            yellow.append("连不上包仓库，依赖包的真实性没检查 —— 网络恢复后重跑；国内网络可设 VIBE_GUARD_NPM_REGISTRY 用镜像")
        elif unknown:
            yellow.append(f"{len(unknown)} 个依赖包查询失败，没检查到：{', '.join(unknown[:8])}")
        ok = sum(1 for s, _ in results if s == "ok")
        if ok:
            green.append(f"{ok} 个依赖包确认真实存在、不是新冒出来的冷门包")
    return red, yellow, green


if __name__ == "__main__":
    r, y, g = run_all(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "."))
    for mark, lst in (("🔴", r), ("🟡", y), ("🟢", g)):
        for x in lst:
            print(f"{mark} {x}")
    sys.exit(1 if r else 0)
