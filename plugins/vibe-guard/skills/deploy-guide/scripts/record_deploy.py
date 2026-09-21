#!/usr/bin/env python3
"""记录这个项目怎么部署，写进 .vibe-guard/deploy.json。

用法：
  python3 record_deploy.py <项目根目录> --platform vercel --url https://myapp.vercel.app \
      [--auto-deploy-branch main] [--rollback "Vercel 后台 → Deployments → 上一个版本 → Promote to Production"]

--auto-deploy-branch：推到这个分支就会自动上线（连 GitHub 自动部署时必填）。
填了之后，vibe-guard 会把 `git push` 到这个分支当成「上线」，跟 vercel --prod 一样先检查、再确认。
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "lib"))
from ship_state import load_deploy, save_deploy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--platform", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--auto-deploy-branch")
    ap.add_argument("--rollback", help="用白话写回滚步骤")
    a = ap.parse_args()

    top = subprocess.run(["git", "-C", a.root, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        print("❌ 这里不是 git 项目，先跑 safe-start")
        sys.exit(1)
    root = top.stdout.strip()
    if not a.url.startswith("https://"):
        print("⚠️ 正式网址不是 https:// 开头，确认一下平台有没有开 HTTPS")
    data = {**(load_deploy(root) or {}), "platform": a.platform, "url": a.url,
            "auto_deploy_branch": a.auto_deploy_branch, "updated": int(time.time())}
    if a.rollback:
        data["rollback"] = a.rollback
    save_deploy(root, data)
    print(f"✅ 已记录：{a.platform}，正式网址 {a.url}")
    if a.auto_deploy_branch:
        print(f"   推到 {a.auto_deploy_branch} 分支 = 上线；之后 git push 到这个分支会先检查 ship-check 状态再请用户确认")
    if not data.get("rollback"):
        print("⚠️ 还没记录回滚方法 —— 找到平台的回滚按钮后，用 --rollback 补上")


if __name__ == "__main__":
    main()
