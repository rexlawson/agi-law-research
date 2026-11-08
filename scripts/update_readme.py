#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 topics.json 生成 README 索引段（幂等，可重复运行）。

规则：只有 articles/ 下真实存在的文件才渲染成链接；尚未写出的选题以纯文字列出，
避免 README 出现死链。

用法: python3 update_readme.py [repo_dir]
标记: README 中 <!-- INDEX:START --> 与 <!-- INDEX:END --> 之间会被整体替换。
"""
import json
import os
import sys

MARK_START = "<!-- INDEX:START -->"
MARK_END = "<!-- INDEX:END -->"

STATUS_LABEL = {
    "idea": "待写",
    "drafting": "写作中",
    "ready": "待发布",
    "published": "已发布",
}


def load_topics(repo_dir):
    path = os.path.join(repo_dir, "topics.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("topics", data if isinstance(data, list) else [])


def build_rows(topics, repo_dir):
    rows = ["| 状态 | 标题 | 议题 | 日期 |", "|---|---|---|---|"]
    articles_dir = os.path.join(repo_dir, "articles")
    # 已发布的排在最前，其余按选题编号
    for t in sorted(topics, key=lambda x: (0 if x.get("status") == "published" else 1, x.get("id", 0))):
        slug = t.get("slug", "")
        fname = t.get("file") or (slug + ".md")
        exists = os.path.exists(os.path.join(articles_dir, fname))
        title = t.get("title", "")
        if exists:
            link = t.get("github_url") or ("articles/" + fname)
            title_cell = "[%s](%s)" % (title, link)
        else:
            title_cell = "%s（待写）" % title
        status = STATUS_LABEL.get(t.get("status", ""), t.get("status", ""))
        rows.append("| %s | %s | %s | %s |" % (status, title_cell, t.get("topic", ""), t.get("date", "") or "-"))
    return "\n".join(rows)


def main():
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    topics = load_topics(repo_dir)
    readme = os.path.join(repo_dir, "README.md")
    with open(readme, encoding="utf-8") as fh:
        content = fh.read()
    if MARK_START not in content or MARK_END not in content:
        print("README 缺少索引标记，无法更新")
        return 1
    block = MARK_START + "\n\n" + build_rows(topics, repo_dir) + "\n\n" + MARK_END
    head = content.split(MARK_START)[0]
    tail = content.split(MARK_END)[1]
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(head + block + tail)
    print("README 索引已更新（%d 条选题）" % len(topics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
