#!/usr/bin/env bash
# 首次建仓：本地 git init + 通过 REST API 在 GitHub 建仓 + 绑定远端。
# 用法: scripts/init_repo.sh [repo_name]
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/agi-law-research}"
REPO_NAME="${1:-agi-law-research}"
cd "$REPO_DIR"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  GH_WIN="/mnt/c/Program Files/GitHub CLI/gh.exe"
  GITHUB_TOKEN=$("$GH_WIN" auth token 2>/dev/null | tr -d '\r')
  export GITHUB_TOKEN
fi
[ -n "${GITHUB_TOKEN:-}" ] || { echo "无 token，先 export GITHUB_TOKEN" >&2; exit 1; }

ACCOUNT=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user | python3 -c "import sys,json;print(json.load(sys.stdin)['login'])")
echo "目标账号: $ACCOUNT"

git init -b main 2>/dev/null || true
git add -A
git commit -q -m "feat: 初始化仓库" 2>/dev/null || true

echo "--- 建仓 ---"
curl -s -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H 'Accept: application/vnd.github+json' \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO_NAME\",\"description\":\"AGI/人工智能法律研究\",\"private\":false,\"auto_init\":false}" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('full_name') and ('已创建: '+d['html_url']) or ('失败: '+str(d.get('message'))))"

git remote add origin "https://github.com/$ACCOUNT/$REPO_NAME.git" 2>/dev/null || git remote set-url origin "https://github.com/$ACCOUNT/$REPO_NAME.git"
git -c credential.helper='!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f' push -u origin main
echo "完成: https://github.com/$ACCOUNT/$REPO_NAME"
