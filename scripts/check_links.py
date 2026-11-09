#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自检：台账、README 与 articles 目录三者是否对得上。

检查：
  1. 台账里标为 published 的条目，articles/ 下必须有对应文件；
  2. articles/ 下的文件，台账里必须有登记；
  3. README"已写"一节里，每篇已发布文章都要有链接。

用法: python3 check_links.py [repo_dir]
"""
import json
import os
import sys

MARK_START = "<!-- WRITTEN:START -->"
MARK_END = "<!-- WRITTEN:END -->"


def main():
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    problems = []

    topics_path = os.path.join(repo_dir, "topics.json")
    published, known = [], set()
    if os.path.exists(topics_path):
        with open(topics_path, encoding="utf-8") as fh:
            topics = json.load(fh).get("topics", [])
        for t in topics:
            fname = t.get("file")
            if fname:
                known.add(fname)
            if t.get("status") == "published":
                published.append(t)

    for t in published:
        fname = t.get("file")
        if not fname:
            problems.append("已发布条目缺 file 字段: " + t.get("title", ""))
        elif not os.path.exists(os.path.join(repo_dir, "articles", fname)):
            problems.append("台账标为已发布但文件缺失: articles/" + fname)

    articles_dir = os.path.join(repo_dir, "articles")
    if os.path.isdir(articles_dir):
        for fn in sorted(os.listdir(articles_dir)):
            if fn.endswith(".md") and known and fn not in known:
                problems.append("文章未登记到 topics.json: " + fn)

    readme_path = os.path.join(repo_dir, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8") as fh:
            content = fh.read()
        if MARK_START in content and MARK_END in content:
            written = content.split(MARK_START)[1].split(MARK_END)[0]
            for t in published:
                fname = t.get("file") or ""
                if fname and fname not in written:
                    problems.append("README 已写列表缺少: " + fname)

    if problems:
        print("发现问题:")
        for p in problems:
            print(" -", p)
        return 1
    print("台账、README 与文章目录一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
