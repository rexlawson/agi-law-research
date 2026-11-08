#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 GitHub REST Git Data API 推送本地提交（git over HTTPS 在本网络不稳定的兜底路径）。

原理：不依赖远端 commit 对象在本地存在。比较"本地 HEAD 的 blob 列表"与"远端 tree 的
blob 列表"，把有差异的路径做成 blob → tree → commit → 更新 refs/heads/main，最后自校验。

安全约束：
  * 默认**不删除**远端文件。本地缺失的远端路径只报告，不动远端
    （本地可能因 fetch 失败而落后，误删会造成数据丢失）。要删必须显式加 --allow-delete。
  * 只上传本地存在的文件；本地缺失即报错，不静默跳过。

用法: python3 push_via_api.py <repo_dir> [owner/repo] [--allow-delete]
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

GH = "/mnt/c/Program Files/GitHub CLI/gh.exe"


def run(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("%s 失败: %s" % (" ".join(args[:4]), (p.stderr or "").strip()[:200]))
    return p.stdout.strip()


def api(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        raise RuntimeError("%s %s -> HTTP %s %s" % (method, url, e.code, detail)) from None
    return json.loads(body) if body else {}


def local_tree(repo_dir, ref):
    out = run(["git", "-c", "core.quotePath=false", "ls-tree", "-r", "--full-tree", ref], repo_dir)
    tree = {}
    for line in out.split("\n"):
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        mode, _kind, sha = meta.split()
        tree[path] = (mode, sha)
    return tree


def remote_tree(base, token, sha):
    data = api("GET", base + "/git/trees/" + sha + "?recursive=1", token)
    tree = {}
    for item in data.get("tree", []):
        if item.get("type") == "blob":
            tree[item["path"]] = ("100755" if item.get("mode") == "100755" else "100644", item["sha"])
    return tree


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow_delete = "--allow-delete" in sys.argv
    repo_dir = args[0] if args else os.getcwd()
    remote = args[1] if len(args) > 1 else ""
    if not remote:
        url = run(["git", "remote", "get-url", "origin"], repo_dir)
        url = url.replace("github.com:", "")
        parts = [s for s in url.replace("https://", "").replace("http://", "").split("/") if s]
        if parts[-1].endswith(".git"):
            parts[-1] = parts[-1][:-4]
        remote = "/".join(parts[-2:])

    token = subprocess.run([GH, "auth", "token"], capture_output=True, text=True).stdout.strip().replace("\r", "")
    base = "https://api.github.com/repos/" + remote

    head = run(["git", "rev-parse", "HEAD"], repo_dir)
    remote_sha = api("GET", base + "/git/ref/heads/main", token)["object"]["sha"]
    remote_tree_sha = api("GET", base + "/git/commits/" + remote_sha, token)["tree"]["sha"]

    lt = local_tree(repo_dir, "HEAD")
    rt = remote_tree(base, token, remote_tree_sha)

    changed, deleted = [], []
    for path, (mode, sha) in sorted(lt.items()):
        if rt.get(path) and rt[path][1] == sha:
            continue
        full = os.path.join(repo_dir, path)
        if not os.path.isfile(full):
            raise RuntimeError("本地缺少文件，拒绝静默跳过: " + path)
        with open(full, "rb") as fh:
            content = base64.b64encode(fh.read()).decode()
        blob = api("POST", base + "/git/blobs", token, {"content": content, "encoding": "base64"})
        changed.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
        print("blob:", path, blob["sha"][:7])

    for path in sorted(rt):
        if path not in lt:
            deleted.append(path)

    if deleted and not allow_delete:
        print("远端有而本地无（默认不删除，需 --allow-delete）：")
        for p in deleted:
            print("  -", p)

    if not changed and not (deleted and allow_delete):
        print("本地内容与远端一致，无需推送")
        return 0

    entries = list(changed)
    if deleted and allow_delete:
        entries += [{"path": p, "mode": "100644", "type": "blob", "sha": None} for p in deleted]

    tree = api("POST", base + "/git/trees", token, {"base_tree": remote_tree_sha, "tree": entries})["sha"]
    print("tree:", tree[:7], "| 变更", len(changed), "个，删除", len(deleted) if allow_delete else 0, "个")

    fmt = "%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%cI%x1f%B"
    meta = run(["git", "show", "-s", "--format=" + fmt, "HEAD"], repo_dir).split(chr(31))
    author = {"name": meta[0], "email": meta[1], "date": meta[2]}
    committer = {"name": meta[3], "email": meta[4], "date": meta[5]}
    message = meta[6]

    commit = api("POST", base + "/git/commits", token,
                 {"message": message, "tree": tree, "parents": [remote_sha],
                  "author": author, "committer": committer})
    api("PATCH", base + "/git/refs/heads/main", token, {"sha": commit["sha"], "force": False})
    print("远端已更新 ->", commit["sha"][:7], "| 本地 HEAD", head[:7])

    verify = remote_tree(base, token, commit["sha"])
    bad = [p for p, (m, s) in lt.items() if verify.get(p, (None, None))[1] != s]
    print("自校验:", "全部一致" if not bad else "不一致: " + ", ".join(bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
