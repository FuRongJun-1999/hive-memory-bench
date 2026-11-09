# -*- coding: utf-8 -*-
"""评测公共件：语料按章聚合、中文数字、判分。全部纯标准库，无第三方依赖。

来源：从灵枢仓 scripts/bench_rubric_sut.py 抽出（只保留评测必需的三件），
使外部人不必安装灵枢即可复测评测链。
"""
import json
import os
import re

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
      '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
      '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
      '二十一': 21, '二十二': 22, '二十三': 23}


def cn2int(s):
    """中文数字 → int（支持 1-23）。"""
    s = (s or '').strip()
    if s.isdigit():
        return int(s)
    if s in CN:
        return CN[s]
    if len(s) == 2 and s[1] == '十':
        return CN.get(s[0], 0) * 10
    if len(s) == 2 and s[0] == '十':
        return 10 + CN.get(s[1], 0)
    if len(s) == 3 and s[1] == '十':
        return CN.get(s[0], 0) * 10 + CN.get(s[2], 0)
    return None


def chapters_text(bench):
    """按章聚合原文（章节 = 时间桶）：{章号: (标题, 全文)}。

    ⚠ 语料里第 18 章是一级标题（`# 第十八章`），其余是 `## `——
    只认 `##` 会整章丢失（实测 22/23 章，28 条断言直接引用它）。
    """
    path = os.path.join(bench, 'corpus', '语料.md')
    lines = open(path, encoding='utf-8').read().splitlines()
    cur, title, buf = None, '', []
    out = {}
    for ln in lines:
        m = re.match(r'^#{1,6}\s*第([一二三四五六七八九十\d]+)章', ln)
        if m:
            if cur is not None and buf:
                out[cur] = (title, chr(10).join(buf))
            n = cn2int(m.group(1))
            cur, title, buf = n, ln.strip('# ').strip(), []
            continue
        if cur is not None:
            buf.append(ln)
    if cur is not None and buf:
        out[cur] = (title, chr(10).join(buf))
    return out


def grade(bench, picks_path, bank='mcq/reasoning/题目_多跳六元素_rubric92_平衡掩码.json'):
    """机械判分：读题库金标 + 答卷，算 TPR/TNR/平衡准确率/φ。

    答卷格式（JSONL，每行一题）：
        {"qid": "o001", "answers": [{"idx": 0, "answer": "是"}, {"idx": 1, "answer": false}]}
    `answer` 接受 是/否、true/false、T/F、Y/N。
    """
    data = json.load(open(os.path.join(bench, bank), encoding='utf-8'))
    gold = {}
    for q in data:
        for j, pt in enumerate(q.get('points') or []):
            gold['%s#%d' % (q['qid'], j)] = bool(pt['answer'])
    picks = {}
    for line in open(picks_path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        for a in d.get('answers') or []:
            key = '%s#%s' % (d.get('qid'), a.get('idx'))
            v = a.get('answer')
            if isinstance(v, str):
                v = v.strip() in ('是', 'true', 'True', 'T', 'Y', 'yes')
            picks[key] = bool(v)
    tp = tn = fp = fn = 0
    for key, g in gold.items():
        p = picks.get(key)
        if p is None:
            continue
        if g and p:
            tp += 1
        elif g and not p:
            fn += 1
        elif (not g) and p:
            fp += 1
        else:
            tn += 1
    pos, neg = tp + fn, tn + fp
    tpr = tp / pos if pos else 0.0
    tnr = tn / neg if neg else 0.0
    bal = (tpr + tnr) / 2
    n = tp + tn + fp + fn
    denom = ((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)) ** 0.5
    phi = ((tp * tn - fp * fn) / denom) if denom else 0.0
    return {'n': n, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
            'tpr': round(tpr, 4), 'tnr': round(tnr, 4),
            'balanced_accuracy': round(bal, 4), 'phi': round(phi, 4)}