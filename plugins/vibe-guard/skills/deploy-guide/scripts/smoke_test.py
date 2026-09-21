#!/usr/bin/env python3
"""部署后冒烟测试（只读，只发 GET 请求）。

用法：python3 smoke_test.py <正式网址> [要检查的路径 ...]
例：  python3 smoke_test.py https://myapp.vercel.app /login /dashboard

检查：
- 每个页面能打开（2xx / 3xx），记录耗时
- 网址是 HTTPS；http:// 会自动跳到 https://
- 安全响应头（HSTS、CSP、防嗅探、防嵌入、Referrer-Policy）
- 不该公开的文件没被公开：/.env、/.git/config、/.env.local 等
有 🔴 时退出码为 1。
"""
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EXPOSED = ["/.env", "/.env.local", "/.env.production", "/.git/config", "/.git/HEAD", "/.vibe-guard/ship-check.json"]
# 这些内容出现在响应里，才算真的泄露（很多网站对任何路径都返回首页 200）
LEAK_MARKERS = ("=", "[core]", "ref: refs/", "\"fingerprint\"")
HEADERS = [
    ("strict-transport-security", "HSTS：强制浏览器只用加密连线"),
    ("content-security-policy", "CSP：限制网页能加载哪些脚本，能挡住大部分 XSS 攻击"),
    ("x-content-type-options", "防止浏览器把文件当成别的类型执行"),
    ("referrer-policy", "控制跳到别的网站时会不会带出你的网址"),
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def get(url, follow=True, timeout=15):
    """返回 (状态码, 最终网址, 响应头 dict, 正文前 2KB, 耗时秒)。连不上时状态码为 0。"""
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "vibe-guard-smoke-test"})
    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.geturl(), {k.lower(): v for k, v in r.headers.items()}, \
                r.read(2048).decode("utf-8", "ignore"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, url, {k.lower(): v for k, v in (e.headers or {}).items()}, \
            (e.read(2048) or b"").decode("utf-8", "ignore"), time.time() - t0
    except Exception as e:
        return 0, url, {}, str(e), time.time() - t0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    base = sys.argv[1].rstrip("/")
    paths = sys.argv[2:] or ["/"]
    if "/" not in paths:
        paths = ["/"] + paths
    red, yellow, green = [], [], []

    # 1. 页面能不能打开
    home_headers, home_body = {}, ""
    for p in paths:
        code, final, headers, body, sec = get(base + p)
        if p == "/":
            home_headers, home_body = headers, body
        if code == 0:
            red.append(f"{p} 打不开：{body[:120]}")
        elif code >= 400:
            red.append(f"{p} 返回 {code} —— 用户会看到错误页")
        else:
            (yellow if sec > 3 else green).append(f"{p} 正常（{code}，{sec:.1f} 秒）" + ("—— 有点慢" if sec > 3 else ""))

    # 2. HTTPS
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https":
        red.append("正式网址不是 HTTPS —— 登录、表单内容会被同一个网络里的人看到")
    else:
        code, _, headers, _, _ = get("http://" + parsed.netloc + "/", follow=False)
        loc = headers.get("location", "")
        if code in (301, 302, 307, 308) and loc.startswith("https://"):
            green.append("http:// 会自动跳到 https://")
        elif code:
            yellow.append("用 http:// 打开时没有自动跳到 https:// —— 在平台设置里打开「强制 HTTPS」")

    # 3. 安全响应头
    if home_headers:
        missing = [desc for name, desc in HEADERS if name not in home_headers]
        framing = "x-frame-options" in home_headers or "frame-ancestors" in home_headers.get("content-security-policy", "")
        if not framing:
            missing.append("防止网页被别的网站嵌进去（点击劫持）")
        if missing:
            yellow.append("缺少这些安全响应头：" + "；".join(missing) +
                          " —— 多数托管平台可以在配置文件（如 vercel.json、netlify.toml、_headers）里加")
        else:
            green.append("常见的安全响应头都有")

    # 4. 不该公开的文件
    for p in EXPOSED:
        code, final, _, body, _ = get(base + p)
        if code == 200 and body and body.strip() != home_body.strip() and any(m in body for m in LEAK_MARKERS):
            red.append(f"{p} 可以直接下载 —— 里面可能有密钥或代码历史，立刻从部署内容里移除，并把相关密钥作废重发")
    if not any(p in x for x in red for p in EXPOSED):
        green.append("没有发现 .env、.git 这类文件被公开")

    print(f"# 部署冒烟测试：{base}\n")
    for title, lst in (("🔴 必须修", red), ("🟡 要确认", yellow), ("🟢 正常", green)):
        print(f"## {title}")
        print("\n".join(f"- {x}" for x in lst) if lst else "- 无")
        print()
    print("自动测试只能确认「打得开、配置对」。核心流程（注册、下单、存数据）仍要亲手走一遍。")
    sys.exit(1 if red else 0)


if __name__ == "__main__":
    main()
