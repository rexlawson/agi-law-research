#!/usr/bin/env bash
# 研究长文提交推送（GitHub）。
#
# 用法: scripts/publish.sh [commit_message]
# 仓库默认 ~/agi-law-research，可用 REPO_DIR 环境变量覆盖。
#
# 认证：优先用已导出的 GITHUB_TOKEN；否则自动从 Windows GitHub CLI（keyring）取。
# 推送：先走 git over HTTPS（带超时与重试）；失败则自动回退到 REST Git Data API
#       （scripts/push_via_api.py，自带内容自校验）。本机 git over HTTPS 不稳定，
#       API 通道才是可靠路径。
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

# --- 推送：先 git，失败回退 API ---
push_ok=0
for i in 1 2; do
  if timeout 60 git -c credential.helper='!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f' push 2>&1 | tail -2; then
    if timeout 20 git ls-remote --heads origin main >/dev/null 2>&1; then push_ok=1; fi
  fi
  [ "$push_ok" = "1" ] && break
  echo "git push 第 $i 次未成功，3 秒后重试" >&2
  sleep 3
done

if [ "$push_ok" != "1" ]; then
  echo "git over HTTPS 不稳定，改用 REST Git Data API 推送" >&2
  python3 scripts/push_via_api.py .
  echo "提示：API 推送会重建 commit（SHA 与本地不同），如需本地对齐执行：git fetch origin main && git reset --hard origin/main" >&2
else
  echo "推送完成 -> $(git remote get-url origin)"
fi
