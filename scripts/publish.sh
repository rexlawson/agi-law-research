#!/usr/bin/env bash
# 研究长文提交推送。需环境变量 GITHUB_TOKEN（以及首次建仓时的仓库名/用户）。
set -euo pipefail
REPO_DIR="${1:-$HOME/agi-law-research}"
cd "$REPO_DIR"

MSG="${2:-docs: 更新 AGI 法律研究}"
git add -A
if git diff --cached --quiet; then
  echo "没有待提交变更"
else
  git commit -m "$MSG"
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "未设置 GITHUB_TOKEN，跳过推送。设置后重跑本脚本。"
  exit 0
fi

git -c credential.helper='!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f' push
echo "推送完成"
