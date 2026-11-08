#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""链接自检：README 索引链接、topics.json 与 articles 目录三者是否一致。

用法: python3 check_links.py [repo_dir]
退出码 0 表示全部通过，1 表示有问题。
"""
import json
import os
import re
import sys

LINK_RE = re.compile(r"\]\((articles/[^)]+)\)")


def main():
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    problems = []

    readme_path = os.path.join(repo_dir, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8") as fh:
            content = fh.read()
        for rel in set(LINK_RE.findall(content)):
            if not os.path.exists(os.path.join(repo_dir, rel)):
                problems.append(f"README 链接失效: {rel}")

    topics_path = os.path.join(repo_dir, "topics.json")
    if os.path.exists(topics_path):
        with open(topics_path, encoding="utf-8") as fh:
            topics = json.load(fh).get("topics", [])
        for t in topics:
            slug = t.get("slug", "")
            if t.get("status") == "published":
                fname = t.get("file") or (slug + ".md")
                if not os.path.exists(os.path.join(repo_dir, "articles", fname)):
                    problems.append(f"台账标为已发布但文件缺失: articles/{fname}")

    articles_dir = os.path.join(repo_dir, "articles")
    if os.path.isdir(articles_dir):
        known = set(t.get("slug", "") for t in topics) if os.path.exists(topics_path) else set()
        for fn in os.listdir(articles_dir):
            if not fn.endswith(".md"):
                continue
            slug = fn[:-3]
            if known and slug not in known:
                problems.append(f"文章未登记到 topics.json: {fn}")

    if problems:
        print("发现问题:")
        for p in problems:
            print(" -", p)
        return 1
    print("链接与台账自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
