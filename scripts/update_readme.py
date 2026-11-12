#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 topics.json 里已发布的文章，渲染成 README「已写」一节的列表（幂等）。

README 中 <!-- WRITTEN:START --> 与 <!-- WRITTEN:END --> 之间会被整体替换。
小红书链接一并从 topics.json 渲染（xhs_url / xhs_notes），避免手写链接被脚本覆盖。
用法: python3 update_readme.py [repo_dir]
"""
import json
import os
import sys

MARK_START = "<!-- WRITTEN:START -->"
MARK_END = "<!-- WRITTEN:END -->"


def xhs_lines(t):
    out = []
    url = t.get("xhs_url")
    if url:
        if t.get("xhs_status") == "rejected_by_platform":
            out.append("  小红书同版（平台审核未通过，已下架）：%s" % url)
        else:
            out.append("  小红书同版：%s" % url)
    for n in (t.get("xhs_notes") or []):
        label = "小红书（%s）" % (n.get("type") or "笔记")
        if n.get("risk"):
            label += "，%s" % n["risk"]
        out.append("  %s：%s" % (label, n.get("url") or ""))
    return out


def main():
    repo_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    with open(os.path.join(repo_dir, "topics.json"), encoding="utf-8") as fh:
        topics = json.load(fh).get("topics", [])

    published = [t for t in topics if t.get("status") == "published"]
    published.sort(key=lambda t: t.get("date", ""), reverse=True)

    lines = []
    for t in published:
        title = t.get("title", "")
        date = t.get("date", "")
        url = t.get("url") or ("articles/" + (t.get("file") or ""))
        summary = (t.get("summary") or "").strip()
        head = "- [%s（%s）](%s)" % (title, date, url)
        lines.append(head + (" —— " + summary if summary else ""))
        lines.extend(xhs_lines(t))
    block = MARK_START + "\n" + "\n".join(lines) + "\n" + MARK_END

    readme = os.path.join(repo_dir, "README.md")
    with open(readme, encoding="utf-8") as fh:
        content = fh.read()
    if MARK_START not in content or MARK_END not in content:
        print("README 缺少 WRITTEN 标记，无法更新")
        return 1
    head = content.split(MARK_START)[0]
    tail = content.split(MARK_END)[1]
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(head + block + tail)
    print("README 已写列表已更新（%d 篇）" % len(published))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
