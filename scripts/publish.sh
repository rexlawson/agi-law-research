#!/usr/bin/env bash
# 研究长文提交推送（GitHub）。
#
# 用法: scripts/publish.sh [commit_message]
# 仓库默认 ~/agi-law-research，可用 REPO_DIR 环境变量覆盖。
#
# 认证：优先用已导出的 GITHUB_TOKEN；否则自动从 Windows GitHub CLI（keyring）取。
# token 全程只在环境变量里，不写入 remote URL、不落盘到 git 配置。

set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/agi-law-research}"
MSG="${1:-docs: 更新 AGI 法律研究}"
cd "$REPO_DIR"

# --- 取 token ---
if [ -z "${GITHUB_TOKEN:-}" ]; then
  GH_WIN="/mnt/c/Program Files/GitHub CLI/gh.exe"
  if [ -x "$GH_WIN" ]; then
    GITHUB_TOKEN=$("$GH_WIN" auth token 2>/dev/null | tr -d '\r')
    export GITHUB_TOKEN
  fi
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "未找到 GitHub token：请先 export GITHUB_TOKEN=... 或在 Windows 侧执行 gh auth login" >&2
  exit 1
fi

# --- 提交 ---
git add -A
if git diff --cached --quiet; then
  echo "没有待提交变更，跳过 commit"
else
  git commit -m "$MSG"
fi

# --- 推送（token 用一次性 credential.helper 注入）---
git -c credential.helper='!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f' push
echo "推送完成 -> $(git remote get-url origin)"
