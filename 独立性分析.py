#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""题目独立性分析：92 道题实际依赖多少个「底层记忆结构」？

背景：**通过率不能读成"92 个独立任务里对 55 个"**——所有题出自同一部小说，
共享人物／事件／因果链，题与题之间存在真实的记忆依赖重叠。
本脚本把这件事**测出来**：依赖面直接写在答案键里（每张卡的
`supporting_evidence[].cid`、`evidence_pool[].cid`、`answer_points[].evidence[].cid`，
cid 形如 u01_c2 ＝ 第 1 单元的 c2 章），于是可以算依赖签名、重叠与聚类。

★ 不计 `must_exclude`：那是"字面相关、采信即错"的干扰项，不是依赖面。

用法：
  python -X utf8 独立性分析.py [--cut 0.5] [--json results/独立性读数.json]
"""
import argparse
import collections
import itertools
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
CARDS = HERE / 'cards'


def load() -> list:
    try:
        import yaml
    except ImportError:
        print('需要 pyyaml：pip install pyyaml'); sys.exit(2)
    out = []
    for f in sorted(CARDS.glob('*.yaml')):
        d = yaml.safe_load(f.read_text(encoding='utf-8'))
        cids = set()
        for e in (d.get('supporting_evidence') or []):      # 客观题
            if isinstance(e, dict) and e.get('cid'):
                cids.add(str(e['cid']))
        for e in (d.get('evidence_pool') or []):            # 开放题
            if isinstance(e, dict) and e.get('cid'):
                cids.add(str(e['cid']))
        for p in (d.get('answer_points') or []):
            if isinstance(p, dict):
                for e in (p.get('evidence') or []):
                    if isinstance(e, dict) and e.get('cid'):
                        cids.add(str(e['cid']))
        out.append({'qid': d.get('qid'), 'category': d.get('category'),
                    'kind': d.get('kind'), 'cids': cids})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--cut', type=float, default=0.5, help='聚类阈值（Jaccard），默认 0.5')
    ap.add_argument('--json', default=str(HERE / 'results' / '独立性读数.json'))
    a = ap.parse_args()

    Q = load()
    noev = [q['qid'] for q in Q if not q['cids']]
    print(f'=== 答案键 {len(Q)} 张卡；无证据依赖的卡 {len(noev)} 张 ===')
    lens = [len(q['cids']) for q in Q if q['cids']]
    print(f'每题依赖章节点数：中位 {sorted(lens)[len(lens)//2]}，范围 {min(lens)}–{max(lens)}，'
          f'均值 {sum(lens)/len(lens):.2f}')

    fan = collections.Counter()
    for q in Q:
        for c in q['cids']:
            fan[c] += 1
    tot = sum(fan.values())
    top10 = sum(n for _, n in fan.most_common(10))
    print(f'\n=== (1) 章级扇入（{len(fan)} 个章节点被引 {tot} 次）===')
    for c, n in fan.most_common(10):
        print(f'   {c}: {n} 题依赖')
    print(f'   前 10 个章节点占 {top10}/{tot} = {100*top10/tot:.0f}%')

    Qe = [q for q in Q if q['cids']]
    js = []
    for x, y in itertools.combinations(Qe, 2):
        inter = len(x['cids'] & y['cids'])
        union = len(x['cids'] | y['cids'])
        js.append((inter / union if union else 0.0, x['qid'], y['qid']))
    js.sort(reverse=True)
    same = [(x, y) for v, x, y in js if v == 1.0]
    hier = sum(1 for A, B in itertools.combinations(Qe, 2)
               if A['cids'] and B['cids'] and A['cids'] != B['cids']
               and (A['cids'] < B['cids'] or B['cids'] < A['cids']))
    nz = sum(1 for v, _, _ in js if v > 0)
    print(f'\n=== (2) 题间依赖重叠（{len(js)} 对）===')
    print(f'   至少共享 1 个章节点：{nz} = {100*nz/len(js):.0f}%；'
          f'平均 Jaccard {sum(v for v, _, _ in js)/len(js):.3f}')
    print(f'   **依赖面完全相同（J=1.00）：{len(same)} 对** —— '
          + '、'.join(f'{x}~{y}' for x, y in same))
    print(f'   存在真包含（一方是另一方子集）：{hier} 对')

    par = {q['qid']: q['qid'] for q in Qe}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for v, x, y in js:
        if v >= a.cut:
            rx, ry = find(x), find(y)
            if rx != ry:
                par[rx] = ry
    sizes = sorted(collections.Counter(find(q['qid']) for q in Qe).values(), reverse=True)
    print(f'\n=== (3) 依赖图连通分量（阈值 Jaccard ≥ {a.cut}）===')
    print(f'   {len(Qe)} 题 → {len(sizes)} 个分量，规模 {sizes[:12]}')
    print(f'   ⇒ 有效独立样本量 ≤ {len(sizes)}；最大分量 {sizes[0]} 题（占 {100*sizes[0]/len(Qe):.0f}%）')

    used, newby = set(), []
    for q in sorted(Qe, key=lambda q: len(q['cids'])):
        newby.append(len(q['cids'] - used))
        used |= q['cids']
    print('\n=== (4) 增量信息 ===')
    print(f'   前 20 题引入 {sum(newby[:20])} 个新章节点；后 20 题引入 {sum(newby[-20:])} 个')

    print('\n★ 口径自限：用「章节点」当依赖面的代理比真实事实粒度粗 ⇒ 分量数偏少，'
          '有效样本量是**上界估计**；且分量数对阈值敏感，'
          '**只报与阈值无关的硬事实**（J=1.00 的题对、扇入集中度）与带阈值的区间。')

    out = pathlib.Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        '卡数': len(Q), '章节点数': len(fan),
        '章节点引用合计': tot, '前10章节点占比': round(100 * top10 / tot, 1),
        '章级扇入': dict(fan.most_common()),
        '每题依赖数中位': sorted(lens)[len(lens) // 2],
        '题对数': len(js), '至少共享一章的题对': nz,
        '平均Jaccard': round(sum(v for v, _, _ in js) / len(js), 4),
        '依赖面相同题对': [list(p) for p in same],
        '真包含题对': hier,
        '阈值': a.cut, '分量数': len(sizes), '分量规模': sizes,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'读数已写出：{out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
