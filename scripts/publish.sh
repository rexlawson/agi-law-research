#!/usr/bin/env bash
# 研究长文提交推送（GitHub）。
#
# 用法: scripts/publish.sh [commit_message]
# 仓库默认 ~/agi-law-research，可用 REPO_DIR 环境变量覆盖。
#
# 认证：优先用已导出的 GITHUB_TOKEN；否则自动从 Windows GitHub CLI（keyring）取。
#
# 推送：git over HTTPS 在本网络不稳定（SSL EOF / 504），所以不靠 git 的返回值判定成败：
#   1) git push 先 best-effort 试一次；
#   2) 随后一律跑 push_via_api.py —— 它按 tree blob 比对，幂等，且自带内容自校验，
#      最终的"推送完成"以它的自校验结果为准。
#
# 安全：token 全程只在环境变量里，不写入 remote URL、不落盘到 git 配置。

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
  echo "没有待提交变更"
else
  git commit -m "$MSG"
fi

# --- 1) git push：best effort，失败不致命 ---
echo "尝试 git push（best-effort）"
timeout 60 git -c credential.helper='!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f' push 2>&1 | tail -2 || true

# --- 2) API 路径：权威结果（幂等 + 自校验）---
echo "以 API 路径核验/补推（幂等，自带内容自校验）"
python3 scripts/push_via_api.py .
echo "推送完成 -> $(git remote get-url origin)"
