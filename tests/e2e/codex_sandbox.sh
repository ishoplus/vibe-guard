#!/usr/bin/env bash
# Codex 端到端试跑：在临时 CODEX_HOME 里装好当前源码的 vibe-guard，跑一句话，跑完删掉临时环境。
#
# 用法：tests/e2e/codex_sandbox.sh <项目目录> "<用户说的话>" [--expert]
#
# - 不碰你真实的 ~/.codex（插件、设置、hook 信任记录都不受影响）
# - 会复制 ~/.codex/auth.json 到临时目录以便登录；脚本结束时（包括中途失败）一定删除
# - 用 --dangerously-bypass-hook-trust 跳过 /hooks 信任，只能在这种一次性测试里用
# - 注意：Codex 启动要连远端 MCP，单次常要 1–2 分钟
set -euo pipefail

proj="${1:?项目目录}"; prompt="${2:?要说的话}"; expert="${3:-}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
export CODEX_HOME="$(mktemp -d /tmp/vg-codex-home.XXXXXX)"
trap 'rm -rf "$CODEX_HOME"' EXIT

cp "$HOME/.codex/auth.json" "$CODEX_HOME/"
printf 'model_reasoning_effort = "low"\n' > "$CODEX_HOME/config.toml"
codex plugin marketplace add "$repo" >/dev/null
codex plugin add vibe-guard@vibe-guard >/dev/null

mkdir -p "$proj"
cd "$proj"
[ "$expert" = "--expert" ] && export VIBE_GUARD_MODE=expert
codex exec --dangerously-bypass-hook-trust -s workspace-write --skip-git-repo-check "$prompt" 2>&1 \
  | grep -v '^warning: `--dangerously-bypass-hook-trust`'
