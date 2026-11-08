#!/usr/bin/env bash
# 从 Windows 侧 GitHub CLI 取已登录账号的 token，并导出 GITHUB_TOKEN。
#
# 背景：本机 WSL 无 gh CLI，Linux 官方 release CDN 被挡（504）；
# 但 Windows 侧装了 GitHub CLI，token 存在 Windows 凭据管理器（keyring），
# gh.exe 可直接读出。当前已登录账号：rexlawson。
#
# 用法：  source scripts/gh_token.sh
# 之后：  curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user
#
# 安全：token 只存在于当前 shell 环境变量，不落盘、不进 remote URL、不入 git 配置。

GH_WIN="/mnt/c/Program Files/GitHub CLI/gh.exe"

if [ ! -x "$GH_WIN" ]; then
  echo "未找到 Windows GitHub CLI: $GH_WIN" >&2
  echo "请在 Windows 侧执行 gh auth login，或手动设置 GITHUB_TOKEN 环境变量。" >&2
  return 1 2>/dev/null || exit 1
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  GITHUB_TOKEN=$("$GH_WIN" auth token 2>/dev/null | tr -d '\r')
  export GITHUB_TOKEN
fi

if [ -z "$GITHUB_TOKEN" ]; then
  echo "取不到 GitHub token（gh auth token 无输出）。" >&2
  return 1 2>/dev/null || exit 1
fi

# 校验并显示账号（不显示 token）
ACCOUNT=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user | python3 -c "import sys,json;print(json.load(sys.stdin).get('login','?'))" 2>/dev/null)
echo "GitHub 已就绪：账号 $ACCOUNT（token 取自 Windows GitHub CLI keyring）" >&2
