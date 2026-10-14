#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""题目独立性分析：92 道题实际依赖多少个「底层记忆结构」？

背景：**通过率不能读成"92 个独立任务里对 55 个"**——所有题出自同一部小说，
共享人物／事件／因果链，题与题之间存在真实的记忆依赖重叠。
本脚本把这件事**测出来**：依赖面直接写在答案键里（每张卡的
`supporting_evidence[].cid`、`evidence_pool[].cid`、`answer_points[].evidence[].cid`，
cid 形如 u01_c2 ＝ 第 1 单元的 c2 章），于是可以算依赖签名、重叠与聚类。

★ 不计 `must_exclude`：那是"字面相关、采信即错"的干扰项，不是依赖面。

★ 两种依赖面粒度都算（issue #32）：**章级**（cid 集合，主口径）与**句级**（把卡里自带的
  `quote` 定位到语料里的句子）。章级是**粗代理**：两题只是同章就会被并进同一分量 ⇒
  分量数**偏少**。所以章级分量数是**下界方向**的估计，真值（更细的事实粒度）**只会更大**；
  旧文档把它写成「上界、真值只会更小」，方向反了。

用法：
  python -X utf8 独立性分析.py [--cut 0.5] [--json results/独立性读数.json] [--no-sentence]
"""
import argparse
import collections
import itertools
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
CARDS = HERE / 'cards'


_SPLIT = None


def _norm(s) -> str:
    import re
    import unicodedata
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', str(s or '')))


def sent_index() -> dict:
    """cid → 规范化后的句子列表（按 。！？换行 切句）。用于**句级**依赖面（issue #32）。"""
    import re
    idx = {}
    for f in sorted((HERE / 'corpus').glob('u*.json')):
        for ch in json.loads(f.read_text(encoding='utf-8')).get('chapters', []):
            idx[ch['cid']] = [n for n in (_norm(s) for s in re.split(r'[。！？!?\n]+',
                                                                     ch.get('text') or '')) if n]
    return idx


def load(with_sentences: bool = False) -> list:
    try:
        import yaml
    except ImportError:
        print('需要 pyyaml：pip install pyyaml'); sys.exit(2)
    sents = sent_index() if with_sentences else {}
    out = []
    for f in sorted(CARDS.glob('*.yaml')):
        d = yaml.safe_load(f.read_text(encoding='utf-8'))
        cids, sentset, evs = set(), set(), []
        for e in (d.get('supporting_evidence') or []):      # 客观题
            if isinstance(e, dict) and e.get('cid'):
                evs.append(e)
        for e in (d.get('evidence_pool') or []):            # 开放题
            if isinstance(e, dict) and e.get('cid'):
                evs.append(e)
        for p in (d.get('answer_points') or []):
            if isinstance(p, dict):
                for e in (p.get('evidence') or []):
                    if isinstance(e, dict) and e.get('cid'):
                        evs.append(e)
        for e in evs:
            c = str(e['cid'])
            cids.add(c)
            q = _norm(e.get('quote'))
            hit = {(c, i) for i, s in enumerate(sents.get(c, [])) if q and (q in s or s in q)}
            # ★ 定位不到句子的 quote 退回章级（偏保守：只会把题并得更少，不会虚增分量）
            sentset |= hit or {(c, '章')}
        out.append({'qid': d.get('qid'), 'category': d.get('category'),
                    'kind': d.get('kind'), 'cids': cids, 'sents': sentset})
    return out


def components(Q, key, cut):
    """同一套 Jaccard ＋ 连通分量：返回 (分量规模列表, 题对数, 平均 Jaccard, J=1 的题对)。"""
    Qe = [q for q in Q if q[key]]
    js = []
    for x, y in itertools.combinations(Qe, 2):
        inter = len(x[key] & y[key])
        union = len(x[key] | y[key])
        js.append((inter / union if union else 0.0, x['qid'], y['qid']))
    js.sort(reverse=True)
    par = {q['qid']: q['qid'] for q in Qe}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for v, x, y in js:
        if v >= cut:
            rx, ry = find(x), find(y)
            if rx != ry:
                par[rx] = ry
    sizes = sorted(collections.Counter(find(q['qid']) for q in Qe).values(), reverse=True)
    same = [(x, y) for v, x, y in js if v == 1.0]
    avg = sum(v for v, _, _ in js) / len(js) if js else 0.0
    return sizes, js, avg, same


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--cut', type=float, default=0.5, help='聚类阈值（Jaccard），默认 0.5')
    ap.add_argument('--json', default=str(HERE / 'results' / '独立性读数.json'))
    ap.add_argument('--no-sentence', action='store_true',
                    help='不算句级对照读数（只跑章级主口径）')
    a = ap.parse_args()

    Q = load(with_sentences=not a.no_sentence)
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
    sizes, js, avgj, same = components(Q, 'cids', a.cut)
    hier = sum(1 for A, B in itertools.combinations(Qe, 2)
               if A['cids'] and B['cids'] and A['cids'] != B['cids']
               and (A['cids'] < B['cids'] or B['cids'] < A['cids']))
    nz = sum(1 for v, _, _ in js if v > 0)
    print(f'\n=== (2) 题间依赖重叠（{len(js)} 对，章级）===')
    print(f'   至少共享 1 个章节点：{nz} = {100*nz/len(js):.0f}%；平均 Jaccard {avgj:.3f}')
    print(f'   **章级依赖面完全相同（J=1.00）：{len(same)} 对** —— '
          + '、'.join(f'{x}~{y}' for x, y in same))
    print('   （★ 这是**章级**的相同，不等于「两题真的不独立」；句级读数见 (3b)）')
    print(f'   存在真包含（一方是另一方子集）：{hier} 对')

    print(f'\n=== (3) 依赖图连通分量（章级，阈值 Jaccard ≥ {a.cut}）===')
    print(f'   {len(Qe)} 题 → {len(sizes)} 个分量，规模 {sizes[:12]}')
    print(f'   最大分量 {sizes[0]} 题（占 {100*sizes[0]/len(Qe):.0f}%）')

    # ★ (3b) 句级对照（issue #32）：章级是粗代理 ⇒ 把只共享章、不共享句的题也并了进来
    #   ⇒ 分量数偏少。句级用卡里自带的 quote 定位到句子，同一套 Jaccard＋连通分量重算。
    sent = None
    if not a.no_sentence:
        Qs = [q for q in Q if q['sents']]
        s_sizes, s_js, s_avg, s_same = components(Q, 'sents', a.cut)
        sent = dict(分量数=len(s_sizes), 分量规模=s_sizes, 平均Jaccard=round(s_avg, 4),
                    依赖面相同题对=[list(p) for p in s_same], 题对数=len(s_js))
        print(f'\n=== (3b) 句级对照（阈值 Jaccard ≥ {a.cut}；issue #32）===')
        print(f'   {len(Qs)} 题 → {len(s_sizes)} 个分量，规模 {s_sizes[:12]}')
        print(f'   平均 Jaccard {s_avg:.3f}（章级 {avgj:.3f}）；'
              f'句级仍 J=1.00 的题对 {len(s_same)} 对'
              + ('：' + '、'.join(f'{x}~{y}' for x, y in s_same) if s_same else '（无）'))
        print('   ⇒ 章级分量数 %d vs 句级 %d：章级是**粗代理**（只是同章就并）⇒ 分量偏少；'
              '句级是**细代理**（只有逐字引文句相同才算共享）⇒ 分量偏多。'
              '真值在两者之间——**「≤%d」既不是上界也不是可靠下界**，'
              '不得据它把区间按 24 折算。' % (len(sizes), len(s_sizes), len(sizes)))

    used, newby = set(), []
    for q in sorted(Qe, key=lambda q: len(q['cids'])):
        newby.append(len(q['cids'] - used))
        used |= q['cids']
    print('\n=== (4) 增量信息 ===')
    print(f'   前 20 题引入 {sum(newby[:20])} 个新章节点；后 20 题引入 {sum(newby[-20:])} 个')

    print('\n★ 口径自限（issue #32 更正）：用「章节点」当依赖面的代理比真实事实粒度**粗** ⇒ '
          '只是同章、不共享句的题也被并进同一分量 ⇒ **分量数偏少**，'
          '章级分量数是**偏保守（下界方向）**的估计，真值只会**更大**——'
          '旧版写「上界、真值只会更小」，方向反了。'
          '另：分量数对阈值敏感，**只报与阈值无关的硬事实**（章级 J=1.00 的题对、扇入集中度）'
          '与**连着阈值**的区间。')

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
        '口径说明': '分量数为**章级**粗代理读数：偏保守（下界方向），真值只会更大；'
                    '句级对照见 句级分量数（issue #32）',
        **({'句级分量数': sent['分量数'], '句级分量规模': sent['分量规模'],
            '句级平均Jaccard': sent['平均Jaccard'],
            '句级依赖面相同题对': sent['依赖面相同题对']} if sent else {}),
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'读数已写出：{out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
