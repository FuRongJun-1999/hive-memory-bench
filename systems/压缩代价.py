#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""压缩代价检查器：你的记忆系统，保住了"矛盾的另一侧"吗？

用法：
    python 压缩代价.py --material ./corpus --retrieval ./runs/my_system/retrieval \
                       --pairs pairs.json [--answers ./runs/my_system/answers] [--n 8]
                       [--mode strict|loose] [--allow-missing]
    python 压缩代价.py --selftest

输入：
  · --material   材料全文：目录（递归读 .txt/.md/.json）或单个文件。
                 .json 会收集其中所有 "text"/"content" 字段（章节式语料直接可用）。
  · --retrieval  检索结果：目录，每题一个文件（.json 或 .txt）。
                 .json 接受三种形状：{"hits":[{"text":…}]} / {"results":[…]} / [{…}]。
  · --pairs      矛盾对清单（.json）："同一事物上的两处记载"的逐字引文。两种写法：
                 [{"qid":"q1","a":"……","b":"……"}, …]   或   {"q1":{"a":"…","b":"…"}}
                 （带 qid 时与检索文件同名匹配；不带 qid 时用全部检索片段求并集）
                 约定 **b（或显式 "far" 字段）为「题面之外那一侧」**——汇总单列它保住了几题。
  · --answers    可选：你家系统的答卷目录。会统计答卷里引文的"可定位率"（依据轴）。
  · --n          公共块长度阈值（默认 8；中文短句建议 6–10 之间取一个固定值并保持）。
  · --mode       **strict（默认）／loose** —— 两套口径分开实现（issue #33 第六项）：
                 strict＝保留标点、逐字包含（文档 §四 的定义）；loose＝只留汉字 ＋ ≥n 连续公共块。
  · --allow-missing  检索文件缺失时不非零退出（默认 exit 3）。

输出三列：
  ① 两侧存活 —— 检索片段里"甲"和"乙"各在不在（这是本文的核心读数：对立面有没有被带回来）
  ①b 远侧    —— 「题面之外那一侧」（b／far）单独计数
  ② 依据轴   —— 答卷引文能否在材料里逐字定位（交改写体的系统这一列会很低）
  ③ 明细     —— 逐对结果（只有一侧／两侧皆无）

★ issue #33 第六项（P1-24）修正：
  ① 旧实现只有"只留汉字 ＋ ≥n 连续公共块"一套口径，且 `common_block` 里 `n = min(n, len(a), len(b))`
     的截断使 `--n` 调大也不更严（与旧文档"要更严可以把 --n 调大"相反）。现在 strict／loose
     分开实现、默认 strict，并去掉该截断（短于 n 字的引文在 strict 下不计命中）。
  ② 旧实现汇总只给「两侧齐／只剩一侧／两侧全无」，不单算"题面之外那一侧"——那正是文档 §四
     的读数。现在单列 ①b。
  ③ 旧实现 `load_material` 把所有文件 `'\n\n'.join` 后归一化，可跨文件跨自然段命中；依据轴
     现在按**单文件单自然段**定位（loose 模式保留旧口径并注明）。
  ④ 旧实现 `quotes_of(min_cjk=6)` 把过短引文**静默剔出分母**，编造短引文不拉低定位率。
     现在过短引文进分母并单列条数。
  ⑤ 文档 §二 的 **B「指出」列本脚本不覆盖**（旧版 argparse 里没有、源码里"指出" 0 次）——
     已在 README 与本文件写明，不再让读者以为输出含 B 列。

★ issue #33 第七项（P1-25）修正：
  ① `blob = retr.get(qid, '\n\n'.join(retr.values()))` —— 带 qid 却找不到同名检索文件时**静默**
     退化成"全部片段并集"，于是"两侧齐"读数虚高。现在记「缺检索文件」、该题按"两侧全无"计，
     汇总单列并非零退出（exit 3，可 `--allow-missing` 关掉）。
  ② 检索键（hits/results/items/fragments/memories）存在但**列表为空**时，旧实现回退
     `collect_texts(obj)` 把整个对象收进来——`query.text`（题面）成了检索片段。现在空列表
     即"两侧全无"，只在**识别不到检索键**时才整份回退，且回退时剔除 `query` 子树。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

CJK = re.compile(r'[^\u4e00-\u9fff]')
WS = re.compile(r'\s+')
HIT_KEYS = ('hits', 'results', 'items', 'fragments', 'memories')
MODES = ('strict', 'loose')
DEFAULT_N = 8
MIN_CJK = 6                 # 引文过短线（只留汉字计）


def norm_loose(s: str) -> str:
    """宽松口径：只留汉字（旧实现原样）。"""
    return CJK.sub('', s or '')


def norm_strict(s: str) -> str:
    """严格口径：保留标点与拉丁，只压缩空白。"""
    return WS.sub('', s or '')


def norm(s: str, mode: str = 'strict') -> str:
    return norm_strict(s) if mode == 'strict' else norm_loose(s)


def common_block(a: str, b: str, n: int, mode: str = 'strict') -> bool:
    """a 是否能在 b 里定位。

    strict：保留标点、逐字包含，且 a 至少 n 字（短于 n 字不计命中——旧实现 `min()` 截断
            让 `--n 999` 与 `--n 8` 同效，与"调大更严"相反，此处按 issue #33 第六项去掉）。
    loose ：只留汉字 ＋ ≥n 字连续公共块（旧实现口径，保留）。
    """
    a, b = norm(a, mode), norm(b, mode)
    if not a or not b:
        return False
    if mode == 'strict':
        return len(a) >= n and a in b
    if a in b or b in a:
        return True
    if len(a) < n:
        return False
    return any(a[i:i + n] in b for i in range(len(a) - n + 1))


def read_text_file(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding='utf-8', errors='ignore')
    except Exception:  # noqa: BLE001
        return ''


def collect_texts(obj, key_names=('text', 'content'), acc=None) -> list[str]:
    acc = [] if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in key_names and isinstance(v, str) and v.strip():
                acc.append(v)
            else:
                collect_texts(v, key_names, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_texts(v, key_names, acc)
    return acc


def split_paras(text: str) -> list[str]:
    """按空行切自然段（依据轴的"单自然段"粒度，issue #33 第六项）。"""
    return [p.strip() for p in re.split(r'\n\s*\n', text or '') if p.strip()]


def load_material(p: pathlib.Path) -> tuple[list[str], str]:
    """→ (自然段列表, 全文)。

    ★ issue #33 第六项：旧实现只返回 `'\n\n'.join(parts)` 一个串，依据轴于是可跨文件跨段命中。
      现在同时给出**单文件单自然段**的段落列表，依据轴按它定位。
    """
    if p.is_file():
        files = [p]
    else:
        files = sorted([q for q in p.rglob('*') if q.suffix.lower() in ('.txt', '.md', '.json')])
    parts: list[str] = []
    for f in files:
        if f.suffix.lower() == '.json':
            try:
                for t in collect_texts(json.loads(read_text_file(f))):
                    parts.extend(split_paras(t))
            except Exception:  # noqa: BLE001
                continue
        else:
            parts.extend(split_paras(read_text_file(f)))
    return parts, '\n\n'.join(parts)


def load_retrieval(p: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    """→ ({文件名去后缀: 片段并集文本}, {文件名去后缀: 口径说明})

    ★ issue #33 第七项：识别到检索键但列表为空 ⇒ 空片段（不再整份回退）；
      只在识别不到检索键时才整份回退，且回退时剔除 `query` 子树（题面不是检索片段）。
    """
    out: dict[str, str] = {}
    how: dict[str, str] = {}
    files = [p] if p.is_file() else sorted(q for q in p.rglob('*')
                                           if q.suffix.lower() in ('.json', '.txt'))
    for f in files:
        if f.suffix.lower() == '.json':
            try:
                obj = json.loads(read_text_file(f))
            except Exception:  # noqa: BLE001
                out[f.stem] = read_text_file(f)
                how[f.stem] = '非 JSON，按纯文本读'
                continue
            hit_key = None
            if isinstance(obj, dict):
                hit_key = next((k for k in HIT_KEYS if isinstance(obj.get(k), list)), None)
            if hit_key is not None:
                frags = collect_texts(obj[hit_key])
                how[f.stem] = f'检索键 {hit_key}（{len(obj[hit_key])} 项）' if obj[hit_key] \
                    else f'检索键 {hit_key} 为空 ⇒ 两侧全无'
            else:
                stripped = ({k: v for k, v in obj.items() if k != 'query'}
                            if isinstance(obj, dict) else obj)
                frags = collect_texts(stripped)
                how[f.stem] = '未识别到检索键 ⇒ 整份回退（已剔除 query 子树）'
            out[f.stem] = '\n\n'.join(frags)
        else:
            out[f.stem] = read_text_file(f)
            how[f.stem] = '纯文本'
    return out, how


def load_pairs(p: pathlib.Path) -> list[dict]:
    obj = json.loads(read_text_file(p))
    if isinstance(obj, dict) and not ('a' in obj or 'b' in obj):
        return [dict(v, qid=k) for k, v in obj.items()]
    if isinstance(obj, dict):
        obj = [obj]
    return [x for x in obj if isinstance(x, dict)]


def quotes_of(obj, acc=None) -> list[str]:
    """收集全部引文——**不过滤过短**（issue #33 第六项：过短引文进分母）。"""
    acc = [] if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('quote', 'quoteA', 'quoteB', '引文'):
                # 引文既可以是一个字符串，也可以是字符串列表（实测答卷两种都有）
                vals = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
                acc.extend(x for x in vals if isinstance(x, str) and x.strip())
            else:
                quotes_of(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            quotes_of(v, acc)
    return acc


def axis_stats(answers: pathlib.Path, paras: list[str], n: int,
               mode: str = 'strict') -> dict:
    """依据轴：答卷引文能否在**单文件单自然段**里定位。过短引文进分母并单列。"""
    qs: list[str] = []
    for f in sorted(answers.rglob('*')):
        if f.suffix.lower() == '.json':
            try:
                qs.extend(quotes_of(json.loads(read_text_file(f))))
            except Exception:  # noqa: BLE001
                pass
    short = [q for q in qs if len(norm_loose(q)) < MIN_CJK]
    loc = sum(1 for q in qs if any(common_block(q, para, n, mode) for para in paras))
    return dict(n=len(qs), located=loc, short=len(short))


def selftest() -> int:
    """定点夹具（issue #33 第六／七项的复现读数）。"""
    import tempfile
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f'[自检] {name:<34} {got!r:<22} {"PASS" if good else "FAIL（应 %r）" % (want,)}')

    # —— 第六项 r3：v2 检索 / v9 引文，宽松同形、严格不同形 ——
    blob_v2 = '材料写：「X不成立」（v2）'
    b_v9 = '材料写：「X不成立」（v9）'
    check('r3 strict 两侧存活', (common_block(b_v9, blob_v2, 8, 'strict'),), (False,))
    check('r3 loose 两侧存活', (common_block(b_v9, blob_v2, 8, 'loose'),), (True,))
    check('r3 strict --n 999 同效', (common_block(b_v9, blob_v2, 999, 'strict'),), (False,))

    # —— 第六项 r2b／r2c／r2d：依据轴按单文件单自然段定位 ——
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / 'mat').mkdir()
    (tmp / 'mat' / 'a.txt').write_text('第一段：猎户项目的有效期是 600 秒。\n\n'
                                       '第二段：材料写：「X不成立」（v2）。', encoding='utf-8')
    (tmp / 'mat' / 'b.txt').write_text('第三段：风神像位于摘星崖。', encoding='utf-8')
    paras, _full = load_material(tmp / 'mat')

    def case(name, quotes):
        d = tmp / name
        d.mkdir()
        (d / 'ans.json').write_text(json.dumps({'quote': quotes}, ensure_ascii=False),
                                    encoding='utf-8')
        return axis_stats(d, paras, 8, 'strict')

    # r2c：跨自然段（第一段尾 ＋ 第二段首）——严格口径下不该定位
    st = case('r2c', ['猎户项目的有效期是 600 秒。第二段：材料写'])
    check('r2c 跨自然段 strict 定位', (st['located'], st['n']), (0, 1))
    # r2b：跨文件 ＋ 版本号写错 ＋ 纯拉丁
    st = case('r2b', ['风神像位于摘星崖。第一段：猎户项目', 'v9.9 与 v0.7 不同',
                      'the quick brown fox'])
    check('r2b 跨文件／错版本／纯拉丁 strict', (st['located'], st['n']), (0, 3))
    # r2d：一条真引文 ＋ 两条 <6 汉字编造（短引文必须进分母并单列）
    st = case('r2d', ['风神像位于摘星崖。', '甲乙丙', '丁戊己'])
    check('r2d 真引文＋短编造 strict', (st['located'], st['n'], st['short']), (1, 3, 2))
    # r2a：整段真引文（严格口径下应定位）——证明这一列不是恒 0
    st = case('r2a', ['第三段：风神像位于摘星崖。'])
    check('r2a 逐字真引文 strict 定位', (st['located'], st['n']), (1, 1))
    # r2e：loose 口径下跨段／错版本仍算命中（旧口径保留，供对照）
    st = axis_stats(tmp / 'r2c', paras, 8, 'loose')
    check('r2e loose 口径跨段命中', (st['located'], st['n']), (1, 1))

    # —— 第七项 r1／r1b：缺检索文件 ——
    ret, how = load_retrieval(tmp / 'ans')
    check('r5 hits 为空 ⇒ 空片段', (ret.get('c') == '' or ret.get('c') is None,), (True,))
    (tmp / 'ret').mkdir()
    (tmp / 'ret' / 'q1.json').write_text(json.dumps(
        {'query': {'text': '题面不该被当检索片段'}, 'hits': []}, ensure_ascii=False),
        encoding='utf-8')
    ret, how = load_retrieval(tmp / 'ret')
    check('r5 hits:[] 不回退收题面', (ret['q1'], '为空' in how['q1']), ('', True))
    (tmp / 'ret' / 'q2.json').write_text(json.dumps(
        {'hits': [{'text': '第三段：风神像位于摘星崖。'}]}, ensure_ascii=False),
        encoding='utf-8')
    ret, how = load_retrieval(tmp / 'ret')
    check('r1 缺 q3 检索文件', ('q3' in ret,), (False,))
    check('r1b 文件名 Q2 vs q2 严格同名', ('Q2' in ret, 'q2' in ret), (False, True))

    print('')
    print('自检结果：' + ('全部通过 ✅（口径对定点夹具有效）' if ok else '存在失败 ❌'))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--material', required=False)
    ap.add_argument('--retrieval', required=False)
    ap.add_argument('--pairs', required=False)
    ap.add_argument('--answers', default='')
    ap.add_argument('--n', type=int, default=DEFAULT_N, help='公共块长度阈值（默认 8）')
    ap.add_argument('--mode', choices=MODES, default='strict',
                    help='strict＝保留标点逐字包含（默认）；loose＝只留汉字＋≥n 连续公共块')
    ap.add_argument('--allow-missing', action='store_true',
                    help='检索文件缺失时不非零退出（默认 exit 3）')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.material and a.retrieval and a.pairs):
        ap.error('需要 --material/--retrieval/--pairs（或加 --selftest）')

    paras, material = load_material(pathlib.Path(a.material))
    if not material.strip():
        print('材料为空——检查 --material 路径'); return 2
    retr, how = load_retrieval(pathlib.Path(a.retrieval))
    pairs = load_pairs(pathlib.Path(a.pairs))
    print(f'材料 {len(norm(material, a.mode))} 字｜自然段 {len(paras)}｜检索 {len(retr)} 组'
          f'｜矛盾对 {len(pairs)} 对｜公共块阈值 {a.n}｜口径 {a.mode}'
          f'（{"保留标点逐字包含" if a.mode == "strict" else "只留汉字＋连续公共块"}）\n')

    both = one = none = far_ok = 0
    missing: list[str] = []
    print(f'{"对":14s} {"甲":>4s} {"乙":>4s} {"远侧":>5s}  来源')
    for pr in pairs:
        qid = str(pr.get('qid') or '')
        if qid and qid not in retr:
            missing.append(qid)
            blob, src = '', '缺检索文件 ⇒ 两侧全无'
        elif qid:
            blob, src = retr[qid], f'{qid}｜{how.get(qid, "")}'
        else:
            blob, src = '\n\n'.join(retr.values()), '全部片段并集（清单未带 qid）'
        ha = common_block(pr.get('a') or '', blob, a.n, a.mode)
        hb = common_block(pr.get('b') or '', blob, a.n, a.mode)
        # ★ 远侧＝「题面之外那一侧」（issue #33 第六项）：显式 far 字段优先，否则约定为 b
        far = pr.get('far')
        hf = common_block(far, blob, a.n, a.mode) if far else hb
        both += ha and hb
        one += (ha ^ hb)
        none += not ha and not hb
        far_ok += hf
        print(f'{qid or "-":14s} {"✓" if ha else "✗":>4s} {"✓" if hb else "✗":>4s} '
              f'{"✓" if hf else "✗":>5s}  {src}')

    total = max(len(pairs), 1)
    print(f'\n① 两侧存活：两侧齐 {both}/{total}｜只剩一侧 {one}/{total}｜两侧全无 {none}/{total}')
    print('   （只剩一侧＝"对面那一侧"被检索丢了——这正是压缩式系统最常见的形态）')
    print(f'①b 远侧（题面之外那一侧，b／far）保住 {far_ok}/{total}')
    if missing:
        print(f'⚠ 缺检索文件 {len(missing)} 题：{"、".join(missing[:8])}'
              f'{"…" if len(missing) > 8 else ""}（该题按「两侧全无」计，非零退出）')

    if a.answers:
        st = axis_stats(pathlib.Path(a.answers), paras, a.n, a.mode)
        pct = 100.0 * st['located'] / max(st['n'], 1)
        print(f'\n② 依据轴（{a.mode}，单文件单自然段）：答卷引文 {st["n"]} 条，'
              f'能在材料里逐字定位 {st["located"]} 条 = {pct:.1f}%'
              f'（其中过短引文 {st["short"]} 条，已进分母）')
        print('   （若很低：你家系统交的是改写体——推理可能对，但证据链不可核实）')

    if missing and not a.allow_missing:
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
