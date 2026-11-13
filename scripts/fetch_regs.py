#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取 AGI 相关法规官方原文到 regs/ 本地档案。

用法：python3 scripts/fetch_regs.py [--out <目录>]

设计原则（都是踩过坑换来的）：
  1. 逐条校验内容后才落盘。校验不过的**不写文件**，宁可缺一条，
     也不能把报错页/空壳当法规原文存进档案——那比缺文件更坏。
  2. 每份文件首部写明来源 URL、抓取日期，引用前可回官方链接复核。
  3. 联邦公报 .txt 端点返回的是 <pre> 包着的正文（不是纯文本），要剥掉外壳。
  4. 404 / Cloudflare 拦截的源直接跳过并记录，不重试到把错误页当正文。
  5. 只用官方一手源。二手解读不进档案。
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')


def curl(url, timeout=45):
    r = subprocess.run(['curl', '-sL', '--max-time', str(timeout),
                        '-w', '\n__HTTP__%{http_code}',
                        '-H', 'User-Agent: ' + UA,
                        '-H', 'Accept: text/html,application/xhtml+xml,application/pdf,*/*;q=0.8',
                        url], capture_output=True)
    raw = r.stdout
    code = '?'
    i = raw.rfind(b'__HTTP__')
    if i >= 0:
        code = raw[i+8:].decode('ascii', 'ignore').strip()
        raw = raw[:i]
    return code, raw


def to_text(raw):
    try:
        s = raw.decode('utf-8')
    except UnicodeDecodeError:
        s = raw.decode('gb18030', 'ignore')
    s = re.sub(r'(?is)<(script|style|head)[^>]*>.*?</\1>', ' ', s)
    s = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>', '\n', s)
    s = re.sub(r'(?i)</td>|</th>', ' | ', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    for a, b in [('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"')]:
        s = s.replace(a, b)
    s = re.sub(r'[ \t\xa0]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def is_error_page(code, text):
    if code != '200':
        return 'HTTP ' + code
    head = text[:4000].lower()
    for sig in ['document not found', '404 not found', 'page you are looking for',
                'just a moment', 'attention required', 'cloudflare']:
        if sig in head:
            return '错误页: ' + sig
    return ''


def write(out, name, body, url, kind='text'):
    path = os.path.join(out, name)
    head = ('来源：%s\n' % url +
            '抓取日期：%s\n' % datetime.date.today().isoformat() +
            '说明：官方原文自动抓取，格式为纯文本；引用前请以官方链接为准。\n' +
            '=' * 60 + '\n\n')
    if kind == 'pdf':
        open(path, 'wb').write(body)
    else:
        io.open(path, 'w', encoding='utf-8').write(head + body)
    return path


# (文件名, 标题, URL, 必须出现的关键词, 类型)
ITEMS = [
    ('CN-01-genai-interim.txt', '生成式人工智能服务管理暂行办法（七部门令第15号）',
     'https://www.gov.cn/zhengce/zhengceku/202307/content_6891752.htm',
     ['生成式人工智能服务管理暂行办法', '第十七条', '第二十四条'], 'text'),
    ('CN-02-deep-synthesis.txt', '互联网信息服务深度合成管理规定（令第12号）',
     'https://www.cac.gov.cn/2022-12/11/c_1672221949354811.htm',
     ['深度合成', '标识', '第二十五条'], 'text'),
    ('CN-03-algorithm-rec.txt', '互联网信息服务算法推荐管理规定（令第9号）',
     'https://www.gov.cn/zhengce/zhengceku/2022-01/04/content_5666429.htm',
     ['算法推荐管理规定', '第八条', '第二十四条'], 'text'),
    ('CN-04-content-labeling.txt', '人工智能生成合成内容标识办法',
     'https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm',
     ['标识', '第十四条', '显式标识'], 'text'),
    ('CN-05-data-reg.txt', '网络数据安全管理条例（国务院令第790号）',
     'https://www.gov.cn/zhengce/content/202409/content_6977766.htm',
     ['网络数据安全管理条例', '第七条', '人工智能'], 'text'),
    ('CN-06-minor.txt', '未成年人网络保护条例（国务院令第766号）',
     'https://www.gov.cn/zhengce/content/202310/content_6911288.htm',
     ['未成年人网络保护条例', '第四十条', '人工智能'], 'text'),
    ('CN-07-data-export.txt', '促进和规范数据跨境流动规定（令第16号）',
     'https://www.cac.gov.cn/2024-03/22/c_1712776611775634.htm',
     ['促进和规范数据跨境流动规定', '第十四条', '出境'], 'text'),
    ('EU-01-ai-act.txt', 'Regulation (EU) 2024/1689 (AI Act)',
     'https://eur-lex.europa.eu/eli/reg/2024/1689/oj',
     ['2024/1689', 'high-risk', 'Article'], 'text'),
    ('EU-02-gdpr.txt', 'Regulation (EU) 2016/679 (GDPR)',
     'https://eur-lex.europa.eu/eli/reg/2016/679/oj',
     ['2016/679', 'personal data', 'Article'], 'text'),
    ('EU-03-dsm.txt', 'Directive (EU) 2019/790 (DSM Directive)',
     'https://eur-lex.europa.eu/eli/dir/2019/790/oj',
     ['2019/790', 'text and data mining', 'Article'], 'text'),
    ('EU-04-gpai-code.txt', 'General-Purpose AI Code of Practice (EU)',
     'https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai',
     ['Code of Practice', 'general-purpose'], 'text'),
    ('EU-05-ai-act-timeline.txt', 'AI Act 实施时间线（欧盟委员会）',
     'https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai',
     ['AI Act', 'August 2026', 'high-risk'], 'text'),
    ('US-02-nist-rmf.pdf', 'NIST AI Risk Management Framework (AI RMF 1.0)',
     'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf', [], 'pdf'),
    ('US-03-nist-genai.pdf', 'NIST AI 600-1 Generative AI Profile',
     'https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf', [], 'pdf'),
]

# 美国总统文件：正文 URL 从 federalregister API 取，取到后再抓正文
EO_DOCS = [
    ('US-01-eo-14179', '2025-02172'),
    ('US-05-eo-14141', '2025-01395'),
    ('US-06-eo-14320', '2025-14218'),
    ('US-07-eo-14365', '2025-23092'),
    ('US-08-eo-14409', '2026-11415'),
    ('US-09-eo-14110', '2023-24283'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'regs'))
    args = ap.parse_args()
    out = args.out
    os.makedirs(out, exist_ok=True)
    report = []

    print('=== 抓取法规原文 ===')
    for name, title, url, must, kind in ITEMS:
        code, raw = curl(url)
        if kind == 'pdf':
            ok = code == '200' and raw[:5] == b'%PDF-'
            reason = '' if ok else ('HTTP ' + code if code != '200' else '非 PDF')
            body = raw
        else:
            body = to_text(raw)
            reason = is_error_page(code, body)
            if not reason:
                missing = [k for k in must if k not in body]
                if missing:
                    reason = '缺关键内容 ' + ','.join(missing[:3])
                elif len(body) < 1200:
                    reason = '正文过短 %d' % len(body)
            ok = not reason
        if ok:
            write(out, name, body, url, kind)
        report.append({'file': name, 'url': url, 'ok': ok, 'reason': reason})
        print(('  OK  ' if ok else '  SKIP') + ' %-26s %s' % (name, reason), flush=True)

    print('=== 抓取美国总统文件正文 ===')
    for name, doc in EO_DOCS:
        code, raw = curl('https://www.federalregister.gov/api/v1/documents/%s.json' % doc)
        try:
            d = json.loads(raw[raw.find(b'{'):].decode('utf-8', 'ignore'))
        except Exception as e:
            print('  SKIP %-26s API 解析失败' % name); continue
        url = d.get('raw_text_url') or ''
        if not url:
            print('  SKIP %-26s 无 raw_text_url' % name); continue
        code, raw = curl(url)
        body = to_text(raw)
        # 联邦公报 .txt 端点返回 <pre> 包着的正文，外壳已由 to_text 剥除
        reason = is_error_page(code, body)
        if not reason and len(body) < 1200:
            reason = '正文过短 %d' % len(body)
        if not reason and d.get('title', '').split(',')[0][:20] not in body[:3000]:
            reason = '首部与 API 标题不符'
        ok = not reason
        if ok:
            head = ('来源：%s\n' % url +
                    '抓取日期：%s\n' % datetime.date.today().isoformat() +
                    '美国联邦公报正文（Presidential Document 原文）：%s\n' % d.get('title') +
                    '公布日：%s  签署日：%s  公报文号：%s\n' % (d.get('publication_date'),
                    d.get('signing_date'), d.get('document_number')) +
                    '=' * 60 + '\n\n')
            io.open(os.path.join(out, name + '.txt'), 'w', encoding='utf-8').write(head + body)
        report.append({'file': name + '.txt', 'url': url, 'ok': ok, 'reason': reason})
        print(('  OK  ' if ok else '  SKIP') + ' %-26s %s' % (name, reason), flush=True)

    json.dump(report, io.open(os.path.join(out, '.fetch-report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    good = sum(1 for r in report if r['ok'])
    print()
    print('成功 %d / %d（未入库的项请看 .fetch-report.json）' % (good, len(report)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
