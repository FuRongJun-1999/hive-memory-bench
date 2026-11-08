# -*- coding: utf-8 -*-
"""K 面配对信度判分（含浮点容差与作废维度检查）。"""
import json, statistics
from pathlib import Path
from collections import defaultdict

TOL = 1.0 + 1e-9
MIN_VAR = 0.01

def load_cards(p):
    d = json.loads(Path(p).read_text(encoding='utf-8'))
    d.sort(key=lambda q: q['qid'])
    return [q for q in d if q['stage'] == 'T1/T2'], [q for q in d if q['stage'] == 'T3']

def norm_answer(arr, order):
    if arr and isinstance(arr[0], dict):
        return {x['qid']: x['score'] for x in arr}
    return {q['qid']: arr[i] for i, q in enumerate(order)}

def evaluate(cards_path, answer_path):
    L12, L3 = load_cards(cards_path)
    j = json.loads(Path(answer_path).read_text(encoding='utf-8'))
    r1 = norm_answer(j['round1'], L12)
    r2 = norm_answer(j['round2'], L12)
    r3 = norm_answer(j['round3'], L3)
    g = defaultdict(lambda: {'p1': [], 'n1': [], 'p2': [], 'pa': []})
    for q in L12:
        d = q['subface']
        (g[d]['p1'] if q['polarity'] == '正向' else g[d]['n1']).append(r1[q['qid']])
        if q['polarity'] == '正向':
            g[d]['p2'].append(r2[q['qid']])
    for q in L3:
        g[q['subface']]['pa'].append(r3[q['qid']])

    rows = []
    for d in sorted(g):
        v = g[d]
        p1 = statistics.mean(v['p1']); neg = statistics.mean(v['n1'])
        p2 = statistics.mean(v['p2']); pa = statistics.mean(v['pa'])
        var = statistics.pstdev(v['p1'])
        ok1 = abs(p1 - (6 - neg)) <= TOL
        ok2 = abs(p1 - p2) <= TOL
        ok3 = abs(p2 - pa) <= TOL
        rows.append((d, p1, neg, p2, pa, var, ok1, ok2, ok3))

    valid = [r for r in rows if r[5] >= MIN_VAR]
    dead = [r[0] for r in rows if r[5] < MIN_VAR]
    n1n = sum(r[6] for r in valid); n2n = sum(r[7] for r in valid); n3n = sum(r[8] for r in valid)
    alln = sum(all(r[6:9]) for r in valid)
    print('%-16s %6s %6s %6s %5s %5s %5s %4s' % ('维度', '正', '反', '后正', 'T1', 'T2', 'T3', '方差'))
    for r in rows:
        mark = ' 作废' if r[5] < MIN_VAR else ''
        print('%-16s %6.2f %6.2f %6.2f %5s %5s %5s %5.2f%s' % (
            r[0], r[1], r[2], r[3], 'OK' if r[6] else 'X', 'OK' if r[7] else 'X',
            'OK' if r[8] else 'X', r[5], mark))
    n = len(valid)
    print()
    print('T1 %d/%d | T2 %d/%d | T3 %d/%d | 三级全过 %d/%d' % (n1n, n, n2n, n, n3n, n, alln, n))
    if dead:
        print('⚠ 作废维度（分数恒定）:', dead)
    return alln, n, dead

if __name__ == '__main__':
    import sys
    evaluate(sys.argv[1], sys.argv[2])