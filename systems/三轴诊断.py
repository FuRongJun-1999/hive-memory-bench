#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三轴诊断器：一个记忆系统「丢的是哪一层」？（纯机械，不依赖判官）

把某系统的检索结果与材料比对，量三件事：

  L1 逐字率    返回片段里有多少能**逐字**在材料里定位（与材料有 ≥N 字连续公共块）。
               抽取式系统（把原文改写成条目）在这项上会低——**那本身就是读数**。
  L2 逐字保地基 你标过的**地基句**（抽掉它结论就塌的前提）保住了几句，可按 group 分组。
  L2′ 关键词覆盖  地基句的**关键术语全部**出现在返回片段里 ⇒ 算「制度内容拿到了」，
               哪怕措辞被改写（把「改写掉了」与「丢了」分开）。
               ★ 校准注意（2026-10 口径更正）：它只量**术语出现过没有**——对极性/否定/语序不敏感
               （把「必须」改成「不必」不会压低它）。**它不是蕴含/正确性检查**；
               原名「语义存活」已弃用。校准对照：`--selftest`（极性夹具，
               复现自 Dedale-Project 在 hive-memory-bench discussion #5215 的留言）。

用法：
  python 三轴诊断.py --material 语料/ --retrieval 检索结果/
                    [--foundations 地基清单.json] [--keyterms 术语.json] [--min 20] [--json 出.json]
  python 三轴诊断.py --selftest   # 内置极性校准夹具（零依赖；三行读数应为 2/2·2/2·2/2 → 0/0·0/0·2/2 → 0/0·0/0·0/0）

输入格式（都很宽松）：
  · material   目录（读其中 *.json 的 chapters[].text）｜单个 .json｜纯文本 .md/.txt
  · retrieval  目录（读其中 *.json 的 hits[].text）；hits 也可直接是字符串列表
  · foundations  JSON 数组： [{"text": "<地基句原文>", "group": "<分组名，可选>"}, ...]
  · keyterms     JSON 对象： {"<地基句原文里的一个短标识串>": ["术语1", "术语2"], ...}（可选）
"""
import argparse
import json
import pathlib
import re
import sys

ZW = ('\u200b', '\u200c', '\u200d', '\u2060', '\ufeff')


def norm(s: str, keep: str = 'cjk') -> str:
    """归一化。**口径必须与要对齐的报告一致，否则 20 字窗含不含标点会改变读数**
    （实测「地基使用」一项可差 ±1–2 句）。

    keep='cjk'   只留汉字（U+4E00–U+9FFF）——本仓库报告里的 L1／L2 用此口径；
    keep='alnum' 留汉字＋字母＋数字，去标点空白——非中文语料用这个。
    """
    s = str(s or '')
    for z in ZW:
        s = s.replace(z, '')
    if keep == 'cjk':
        return re.sub(r'[^\u4e00-\u9fff]', '', s)
    return re.sub(r'[^\w]', '', s, flags=re.UNICODE)


def grams(s: str, n: int) -> set:
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else set()


def has_block(text: str, gset: set, n: int) -> bool:
    """text 与长文有没有 ≥n 字连续公共块——等价于查 text 的 n-gram 是否落在长文的 n-gram 集里。
    比 LCB 的动态规划快几个数量级（实测 2 万字材料上从分钟级降到秒级）。"""
    if len(text) < n:
        return False
    return bool(grams(text, n) & gset)


def load_material(p: pathlib.Path, keep: str = 'cjk') -> str:
    files = sorted(p.glob('*.json')) if p.is_dir() else [p]
    out = []
    for f in files:
        if f.suffix.lower() == '.json':
            d = json.loads(f.read_text(encoding='utf-8'))
            for ch in d.get('chapters') or []:
                out.append(ch.get('text') or '')
        else:
            out.append(f.read_text(encoding='utf-8'))
    return norm(''.join(out), keep)


def load_segments(p: pathlib.Path, keep: str = 'cjk') -> list:
    files = sorted(p.glob('**/*.json')) if p.is_dir() else [p]
    segs = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            continue
        hits = d.get('hits') if isinstance(d, dict) else d
        for h in hits or []:
            t = norm(h.get('text') if isinstance(h, dict) else h, keep)
            if t:
                segs.append(t)
    return segs


def load_foundations(p):
    if not p:
        return []
    d = json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    if isinstance(d, dict):
        d = d.get('foundations') or d.get('rules') or []
    return [r for r in d if (r.get('text') if isinstance(r, dict) else r)]


def selftest() -> int:
    """内置极性校准夹具（复现自 Dedale-Project 留言，hive-memory-bench discussion #5215）。

    同一地基句、同一 keyterms，只把极性词反转（必须→不必、可以→不可以）：
    L1/L2（逐字轴）应掉到 0，而 L2′（关键词覆盖）保持 — 证明 L2′ 不是蕴含检查。
    """
    s1 = '遇到过期快照时必须回滚事务并重新读取库存后再计算预订数量。'
    s2 = '遇到临时写锁时可以在限定等待预算内等另一个写事务提交。'
    s1r = '遇到过期快照时不必回滚事务并重新读取库存后再计算预订数量。'
    s2r = '遇到临时写锁时不可以等待预算内等另一个写事务提交。'
    w = '明天多云转晴，气温十八到二十四度，适合外出活动。'
    matg = grams(norm(s1 + s2, 'cjk'), 20)
    key = {'过期快照': ['过期快照', '回滚', '重新读取库存'],
           '临时写锁': ['临时写锁', '等待预算', '提交']}
    fnd = [s1, s2]

    def run(segs):
        sn = [norm(t, 'cjk') for t in segs]
        segjoin = ''.join(sn)
        segset = {g for t in sn for g in grams(t, 20)}
        l1 = sum(1 for t in sn if grams(t, 20) & matg)
        l2 = sum(1 for r in fnd if grams(norm(r, 'cjk'), 20) & segset)
        lp = sum(1 for r in fnd if any(k in r and all(tm in segjoin for tm in ts)
                                       for k, ts in key.items()))
        return l1, l2, lp

    cases = [('两句原文', [s1, s2], (2, 2, 2)),
             ('极性反转（必须→不必；可以→不可以）', [s1r, s2r], (0, 0, 2)),
             ('无关句', [w], (0, 0, 0))]
    print('极性校准夹具（三轴诊断 · --selftest）｜同一地基句/术语，仅改极性词')
    ok = True
    for name, segs, expect in cases:
        got = run(segs)
        good = got == expect
        ok = ok and good
        print('  %-36s L1 %d/%d  L2 %d/%d  L2′ %d/%d   %s'
              % (name, got[0], len(segs), got[1], len(fnd), got[2], len(fnd),
                 '✓' if good else f'✗（期望 {expect}）'))
    print('结论：L1/L2（逐字轴）对极性反转敏感；L2′（关键词覆盖）不敏感——'
          '它量「术语出现过没有」，不是蕴含检查。')
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--material', help='材料（--selftest 时可省）')
    ap.add_argument('--retrieval', help='检索结果（--selftest 时可省）')
    ap.add_argument('--foundations')
    ap.add_argument('--keyterms')
    ap.add_argument('--min', type=int, default=20)
    ap.add_argument('--keep', choices=('cjk', 'alnum'), default='cjk',
                    help="归一化口径：cjk＝只留汉字（默认，与仓库报告一致）；alnum＝留字母数字（非中文语料）")
    ap.add_argument('--json')
    ap.add_argument('--selftest', action='store_true', help='跑内置极性校准夹具后退出')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.material or not a.retrieval:
        ap.error('--material/--retrieval 必填（或用 --selftest 跑校准夹具）')

    n = a.min
    MAT = load_material(pathlib.Path(a.material), a.keep)
    MATG = grams(MAT, n)
    segs = load_segments(pathlib.Path(a.retrieval), a.keep)
    if not MAT or not segs:
        print('材料或检索结果为空——检查路径与格式（见 --help）。')
        return 2

    verb = sum(1 for t in segs if has_block(t, MATG, n))
    F = load_foundations(a.foundations)
    kt = json.loads(pathlib.Path(a.keyterms).read_text(encoding='utf-8')) if a.keyterms else {}
    segset = {g for t in segs for g in grams(t, n)}
    segjoin = ''.join(segs)
    kept = [r for r in F if grams(norm(r['text'], a.keep), n) & segset]
    alive = [r for r in F if any(k in r['text'] and all(tm in segjoin for tm in ts)
                                 for k, ts in kt.items())]

    print(f'材料 {len(MAT)} 字｜返回片段 {len(segs)} 段｜地基句 {len(F)} 条｜阈值 {n} 字｜归一化 {a.keep}')
    print(f'L1 逐字率      {verb}/{len(segs)} = {100*verb/len(segs):.1f}%')
    if F:
        print(f'L2 逐字保地基  {len(kept)}/{len(F)} = {100*len(kept)/len(F):.1f}%')
        grps = sorted({(r.get('group') if isinstance(r, dict) else None) for r in F} - {None})
        for g in grps:
            tot = sum(1 for r in F if r.get('group') == g)
            k = sum(1 for r in kept if r.get('group') == g)
            print(f'   · {g:<10} {k}/{tot}')
    if kt:
        print(f'L2′ 关键词覆盖 {len(alive)}/{len(F)} = {100*len(alive)/max(1,len(F)):.1f}%')
    print('\n读法：L1 低而 L2 高 ＝「知道这条前提、但交不出原文」；'
          'L2 只量保没保住，不量保住得对不对；'
          'L2′ 只量关键术语出现过没有（对极性/否定不敏感），**不是蕴含检查**。')

    if a.json:
        out = {'材料汉字': len(MAT), '返回段': len(segs), '阈值': n,
               'L1_逐字率': round(100 * verb / len(segs), 1),
               'L1': f'{verb}/{len(segs)}',
               '地基句': len(F)}
        if F:
            out['L2_逐字保地基'] = round(100 * len(kept) / len(F), 1)
            out['L2'] = f'{len(kept)}/{len(F)}'
        if kt:
            # 2026-10 口径更正：原名「语义存活」→「关键词覆盖」（非蕴含检查）；
            # 旧键保留为别名（同值），供既有消费者过渡。
            out['L2p_关键词覆盖'] = round(100 * len(alive) / max(1, len(F)), 1)
            out['L2p_语义存活'] = out['L2p_关键词覆盖']
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'（已写出 {a.json}）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
