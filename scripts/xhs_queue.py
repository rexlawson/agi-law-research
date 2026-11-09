#!/usr/bin/env python3
"""小红书笔记队列选择器：挑出"今天该发"的那一篇。

给自动化发布任务调用。判定规则（与 skills/xhs-longform 的排期纪律一致）：
  1) 草稿状态必须是「待发布」——已发布、废弃的一律跳过
  2) 草稿必须写明「最早可发日：YYYY-MM-DD」；没写 -> 进 blocked 列表，不静默放过
  3) 距上一篇已发布笔记至少间隔 2 天（同一天不连发，分 2-3 天）
  4) 满足以上且今天 >= 最早可发日 -> due，只取最早的那一篇

输出 JSON 到 stdout：
  {"today","last_published","due","pending","blocked"}

用法：
  python3 scripts/xhs_queue.py
  python3 scripts/xhs_queue.py --today 2026-11-11
  python3 scripts/xhs_queue.py --repo /path/to/repo
退出码：0 正常（含 due=null）；2 输入缺失或格式坏。
"""

import argparse
import datetime as dt
import io
import json
import os
import re
import sys

MIN_GAP_DAYS = 2

RE_STATUS = re.compile(r'^\s*状态：(\S+)')
RE_EARLIEST = re.compile(r'^\s*最早可发日：(\d{4}-\d{2}-\d{2})')
RE_TITLE = re.compile(r'^\s*标题：(.+)$')
RE_PUB_AT = re.compile(r'已发布[（(](\d{4}-\d{2}-\d{2})')


def die(msg):
    print("xhs_queue: " + msg, file=sys.stderr)
    sys.exit(2)


def parse_draft(path):
    try:
        text = io.open(path, encoding='utf-8').read()
    except Exception as e:
        die("读取失败 %s: %s" % (path, e))
    d = {'file': path}
    for line in text.splitlines():
        m = RE_STATUS.match(line)
        if m and 'status' not in d:
            d['status'] = m.group(1)
            continue
        m = RE_EARLIEST.match(line)
        if m and 'earliest' not in d:
            d['earliest'] = m.group(1)
            continue
        m = RE_TITLE.match(line)
        if m and 'title' not in d:
            d['title'] = m.group(1).strip()
    return d


def last_published(repo):
    """最近一篇已发布笔记的时间。优先看 topics.json 台账，回退到草稿状态行。"""
    best = None
    tp = os.path.join(repo, 'topics.json')
    if os.path.exists(tp):
        try:
            data = json.load(io.open(tp, encoding='utf-8'))
        except Exception as e:
            die('topics.json 解析失败: %s' % e)
        for t in data.get('topics', []):
            v = t.get('xhs_published_at')
            if v:
                if best is None or v > best:
                    best = v
    xd = os.path.join(repo, 'xhs')
    if os.path.isdir(xd):
        for fn in sorted(os.listdir(xd)):
            if not fn.endswith('.md'):
                continue
            try:
                text = io.open(os.path.join(xd, fn), encoding='utf-8').read()
            except Exception:
                continue
            for line in text.splitlines():
                m = RE_STATUS.match(line)
                if m and m.group(1).startswith('已发布'):
                    p = RE_PUB_AT.search(line)
                    if p:
                        v = p.group(1)
                        if best is None or v > str(best)[:10]:
                            best = v
                    break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=os.path.expanduser('~/agi-law-research'))
    ap.add_argument('--today', default=None)
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    if not os.path.isdir(repo):
        die('仓库不存在: %s' % repo)
    xd = os.path.join(repo, 'xhs')
    if not os.path.isdir(xd):
        die('缺 xhs 目录: %s' % xd)

    today = a.today or dt.date.today().isoformat()
    try:
        today_d = dt.date.fromisoformat(today)
    except Exception:
        die('--today 格式应为 YYYY-MM-DD')

    last = last_published(repo)
    last_d = None
    if last:
        try:
            last_d = dt.date.fromisoformat(str(last)[:10])
        except Exception:
            last_d = None

    # 最早允许发稿日 = 上一篇 + 2 天
    earliest_allowed = (last_d + dt.timedelta(days=MIN_GAP_DAYS)) if last_d else None

    due, pending, blocked = [], [], []
    for fn in sorted(os.listdir(xd)):
        if not fn.endswith('.md'):
            continue
        d = parse_draft(os.path.join(xd, fn))
        status = d.get('status', '')
        if not status.startswith('待发布'):
            continue
        d['file'] = fn
        if 'title' not in d:
            blocked.append({'file': fn, 'reason': '缺「标题：」字段'})
            continue
        if 'earliest' not in d:
            blocked.append({'file': fn, 'title': d['title'],
                            'reason': '缺「最早可发日：YYYY-MM-DD」字段，无法排期'})
            continue
        try:
            e_d = dt.date.fromisoformat(d['earliest'])
        except Exception:
            blocked.append({'file': fn, 'title': d['title'],
                            'reason': '最早可发日格式非法: %s' % d['earliest']})
            continue
        d['earliest_date'] = d['earliest']
        if earliest_allowed and e_d < earliest_allowed:
            d['reason'] = '距上一篇不足 %d 天（最早 %s）' % (MIN_GAP_DAYS, earliest_allowed.isoformat())
            pending.append(d)
            continue
        if e_d > today_d:
            d['reason'] = '未到最早可发日 %s' % d['earliest']
            pending.append(d)
            continue
        due.append(d)

    due.sort(key=lambda x: (x['earliest_date'], x['file']))
    out = {
        'today': today,
        'last_published': last,
        'earliest_allowed': earliest_allowed.isoformat() if earliest_allowed else None,
        'due': due[0] if due else None,
        'pending': pending,
        'blocked': blocked,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
