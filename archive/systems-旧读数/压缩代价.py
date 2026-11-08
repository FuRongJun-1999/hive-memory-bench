#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""压缩代价检查器：你的记忆系统，保住了"矛盾的另一侧"吗？

用法：
    python 压缩代价.py --material ./corpus --retrieval ./runs/my_system/retrieval \
                       --pairs pairs.json [--answers ./runs/my_system/answers] [--n 8]
                       [--mode strict|loose] [--allow-missing] [--union]
                       [--questions ./questions.json]
    python 压缩代价.py --selftest

输入：
  · --material   材料全文：目录（递归读 .txt/.md/.json）或单个文件。
                 .json 会收集其中所有 "text"/"content" 字段（章节式语料直接可用）。
  · --retrieval  检索结果：目录，每题一个文件（.json 或 .txt）。
                 .json 接受三种形状：{"hits":[{"text":…}]} / {"results":[…]} / [{…}]。
  · --pairs      矛盾对清单（.json）："同一事物上的两处记载"的逐字引文。两种写法：
                 [{"qid":"q1","a":"……","b":"……"}, …]   或   {"q1":{"a":"…","b":"…"}}
                 （带 qid 时与检索文件同名匹配；不带 qid 时用全部检索片段求并集——**这只在
                 检索目录里只有一个文件时是无歧义的**，否则 exit 4，除非显式 --union）
                 约定 **b（或显式 "far" 字段）为「题面之外那一侧」**——汇总单列它保住了几题。
  · --answers    可选：你家系统的答卷目录。会统计答卷里引文的"可定位率"（依据轴）。
  · --n          公共块长度阈值（默认 8；中文短句建议 6–10 之间取一个固定值并保持）。
  · --mode       **strict（默认）／loose** —— 两套口径分开实现（issue #33 第六项）：
                 strict＝保留标点、逐字包含（文档 §四 的定义）；loose＝只留汉字 ＋ ≥n 连续公共块。
  · --allow-missing  检索文件缺失时不非零退出（默认 exit 3）。
  · --union      显式允许"不带 qid 时拿全部检索片段的并集比较"（默认在检索目录多于一个
                 文件时 exit 4——并集会让"两侧齐"虚高）。
  · --questions  题面文件（.json）：{"q1": "题面原文", …} 或 ["题面1", "题面2"]。给了就
                 先剔除"引文是题面子串"的答卷引文再算依据轴定位率（＝本文 C 表口径）。

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
     已在 `README.md`「压缩的代价」节与 `docs/压缩的代价就是因果丢失_v1.0.md` §四 写明
     （issue #45-5 R4：旧注释声称"已写明"，而两处都找不到这层意思）。

★ issue #33 第七项（P1-25）修正：
  ① `blob = retr.get(qid, '\n\n'.join(retr.values()))` —— 带 qid 却找不到同名检索文件时**静默**
     退化成"全部片段并集"，于是"两侧齐"读数虚高。现在记「缺检索文件」、该题按"两侧全无"计，
     汇总单列并非零退出（exit 3，可 `--allow-missing` 关掉）。
  ② 检索键（hits/results/items/fragments/memories）存在但**列表为空**时，旧实现回退
     `collect_texts(obj)` 把整个对象收进来——`query.text`（题面）成了检索片段。现在空列表
     即"两侧全无"，只在**识别不到检索键**时才整份回退，且回退时剔除 `query` 子树。

★ issue #45 第五项（T5，P1-24／P1-25 的残留）修正：
  R1 清单不带 qid 时，旧实现对**每一对**都拿"全部题目检索的并集"比较（`:337-338`），
     而文档 §四 给的示例恰好不带 qid ⇒ 照文档写法跑出的"两侧齐"虚高且 exit 0。
     现在：不带 qid 而检索目录里多于一个文件 ⇒ **exit 4**（并集是"每题都拿到全部材料"，
     不是检索的功劳）；只有一个文件时无歧义，照旧；确实要并集请显式 `--union`。
  R3 依据轴口径是"剔除题面自带引文后"（`readings.json` 口径.依据轴／文档 C 表），旧实现
     没有题面输入、全部计入。现在加 `--questions`：`norm(引文) ⊂ norm(题面)` 的引文剔出
     分子分母并单列条数；**不给 `--questions` 时在输出里注明"未剔除题面引文"**。
  R2 strict 依据轴旧实现复用 `common_block`，`len(a) >= n` 要求引文 ≥ `--n`(8) 字（标点也算），
     一条 7 字的逐字真引文被记为"不可定位"却又不算"过短"（`MIN_CJK=6`）。文档的 strict 定义
     里**没有长度门槛** ⇒ 现在 strict ＝ 纯逐字包含，`--n` 只作用于 loose。
  R4 见上 ⑤（旧注释声称"已在 README 与本文件写明"，实际两处都没有）。
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

    strict：保留标点、逐字包含——**无长度门槛**（文档 §四 的 strict 定义里没有长度条件；
            issue #45-5 R2：旧实现复用 `--n`，一条 7 字的逐字真引文被记为"不可定位"，
            却又不算"过短"，读数偏低）。过短引文另由 `MIN_CJK` 单列，不在这里卡。
    loose ：只留汉字 ＋ ≥n 字连续公共块（旧实现口径，保留；`--n` 只作用于本口径）。
    """
    a, b = norm(a, mode), norm(b, mode)
    if not a or not b:
        return False
    if mode == 'strict':
        return a in b
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


def load_questions(p: pathlib.Path) -> list[str]:
    """题面文件 → 题面字符串列表。接受 {"q1": "题面", …} 或 ["题面", …]。"""
    try:
        obj = json.loads(read_text_file(p))
    except Exception:  # noqa: BLE001
        return []
    if isinstance(obj, dict):
        return [v for v in obj.values() if isinstance(v, str) and v.strip()]
    if isinstance(obj, list):
        return [v for v in obj if isinstance(v, str) and v.strip()]
    return []


def from_question(quote: str, questions: list[str], mode: str) -> bool:
    """引文是不是**题面自带**的（题面里就有的字串）——issue #45-5 R3。

    文档 C 表／`readings.json` 口径.依据轴 都写明"剔掉题面自带的引文（那些不算检索的功劳）"；
    旧实现没有题面输入，于是题面原句照算命中，定位率虚高。
    """
    nq = norm(quote, mode)
    if not nq:
        return False
    return any(nq in norm(q, mode) for q in questions if q)


def axis_stats(answers: pathlib.Path, paras: list[str], n: int,
               mode: str = 'strict', questions: list[str] | None = None) -> dict:
    """依据轴：答卷引文能否在**单文件单自然段**里定位。过短引文进分母并单列。

    ★ issue #45-5 R3：给了 `questions`（题面）就先剔除"引文是题面子串"的那些，
      与文档 C 表口径一致；不给则全部计入，调用方须在输出里注明未剔除。
    """
    qs: list[str] = []
    for f in sorted(answers.rglob('*')):
        if f.suffix.lower() == '.json':
            try:
                qs.extend(quotes_of(json.loads(read_text_file(f))))
            except Exception:  # noqa: BLE001
                pass
    questions = questions or []
    mask = [from_question(q, questions, mode) for q in qs]
    fq = [q for q, m in zip(qs, mask) if m]
    kept = [q for q, m in zip(qs, mask) if not m]
    short = [q for q in kept if len(norm_loose(q)) < MIN_CJK]
    loc = sum(1 for q in kept if any(common_block(q, para, n, mode) for para in paras))
    return dict(n=len(kept), located=loc, short=len(short),
                from_question=len(fq), total=len(qs))


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

    # —— 第五项 R2：strict 无长度门槛，7 字逐字真引文必须算命中 ——
    d = tmp / 'r2n'; d.mkdir()
    (d / 'ans.json').write_text(json.dumps({'quote': '神像位于摘星崖'}, ensure_ascii=False),
                                encoding='utf-8')
    st = axis_stats(d, paras, 8, 'strict')
    check('R2 7 字逐字真引文 strict 命中', (st['located'], st['n'], st['short']), (1, 1, 0))
    st = axis_stats(d, paras, 8, 'loose')
    check('R2 同一条 loose 也命中', (st['located'],), (1,))

    # —— 第五项 R3：题面自带引文必须能被剔除（文档 C 表口径） ——
    q_text = '题面引文：风神像位于摘星崖之上。'
    (tmp / 'mat' / 'c.txt').write_text(q_text, encoding='utf-8')
    paras3, _f3 = load_material(tmp / 'mat')
    d = tmp / 'r3'; d.mkdir()
    (d / 'ans.json').write_text(json.dumps({'evidence': [
        {'quote': q_text}, {'quote': '甲方曾经反对过所有的权威人士'}]}, ensure_ascii=False),
        encoding='utf-8')
    st = axis_stats(d, paras3, 8, 'strict')
    check('R3 不给题面 ⇒ 题面引文照算', (st['located'], st['n'], st['from_question']), (1, 2, 0))
    st = axis_stats(d, paras3, 8, 'strict', [q_text])
    check('R3 给题面 ⇒ 剔出分母并单列', (st['located'], st['n'], st['from_question'], st['total']),
          (0, 1, 1, 2))

    # —— 第五项 R1：不带 qid ＋ 多个检索文件 ⇒ exit 4（--union 才放行） ——
    import argparse
    import contextlib
    import io
    a1 = '甲方在第一章里明确说过反对一切权威。'
    b1 = '乙方在第九章写着唯有强大的王者才是自由的前提。'
    (tmp / 'mat2').mkdir()
    (tmp / 'mat2' / 'c.txt').write_text(a1 + '\n\n' + b1, encoding='utf-8')
    (tmp / 'ret2').mkdir()
    (tmp / 'ret2' / 'q1.json').write_text(json.dumps({'hits': [{'text': a1}]}, ensure_ascii=False),
                                           encoding='utf-8')
    (tmp / 'ret2' / 'q2.json').write_text(json.dumps({'hits': [{'text': b1}]}, ensure_ascii=False),
                                           encoding='utf-8')
    (tmp / 'p_doc.json').write_text(json.dumps([{'a': a1, 'b': b1}], ensure_ascii=False),
                                    encoding='utf-8')
    (tmp / 'p_qid.json').write_text(json.dumps([{'qid': 'q1', 'a': a1, 'b': b1}],
                                                ensure_ascii=False), encoding='utf-8')
    base = dict(material=str(tmp / 'mat2'), retrieval=str(tmp / 'ret2'), answers='',
                questions='', n=8, mode='strict', allow_missing=False)

    def run_quiet(**kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run_check(argparse.Namespace(**dict(base, **kw)))
        return rc, buf.getvalue()

    rc, out = run_quiet(pairs=str(tmp / 'p_doc.json'), union=False)
    check('R1 不带 qid＋2 个检索文件 ⇒ exit 4', (rc, '并集' in out), (4, True))
    rc, out = run_quiet(pairs=str(tmp / 'p_doc.json'), union=True)
    check('R1 --union 显式放行 ⇒ exit 0', (rc,), (0,))
    rc, out = run_quiet(pairs=str(tmp / 'p_qid.json'), union=False)
    check('R1 带 qid ⇒ exit 0 且只剩一侧 1/1',
          (rc, '两侧齐 0/1' in out, '只剩一侧 1/1' in out), (0, True, True))

    print('')
    print('自检结果：' + ('全部通过 ✅（口径对定点夹具有效）' if ok else '存在失败 ❌'))
    return 0 if ok else 1


def needs_union(pairs: list[dict], retr: dict) -> bool:
    """清单里有不带 qid 的对，而检索目录里有多于一个文件 ⇒ 只能拿并集比（issue #45-5 R1）。

    并集＝"每对都拿到全部题目检索到的东西"，"两侧齐"必然虚高；一个文件时并集＝那一组，无歧义。
    """
    no_qid = any(not str(pr.get('qid') or '') for pr in pairs)
    return bool(no_qid and len(retr) > 1)


def run_check(a) -> int:
    """跑一次完整检查（`main()` 解析参数后调它；`--selftest` 也用它做端到端夹具）。"""

    paras, material = load_material(pathlib.Path(a.material))
    if not material.strip():
        print('材料为空——检查 --material 路径'); return 2
    retr, how = load_retrieval(pathlib.Path(a.retrieval))
    pairs = load_pairs(pathlib.Path(a.pairs))
    print(f'材料 {len(norm(material, a.mode))} 字｜自然段 {len(paras)}｜检索 {len(retr)} 组'
          f'｜矛盾对 {len(pairs)} 对｜公共块阈值 {a.n}｜口径 {a.mode}'
          f'（{"保留标点逐字包含" if a.mode == "strict" else "只留汉字＋连续公共块"}）\n')

    # ★ issue #45-5 R1：不带 qid ＋ 多个检索文件 ⇒ 并集比较会让"两侧齐"虚高，先拦下
    union_used = False
    if needs_union(pairs, retr):
        if not getattr(a, 'union', False):
            print(f'⚠ 清单里有不带 qid 的对，而检索目录里有 {len(retr)} 组片段——'
                  f'不指定 qid 就只能拿"全部检索片段的并集"比较，'
                  f'"两侧齐"会虚高（issue #45-5 R1）。')
            print('   请给每对补 qid（与检索文件名同名），或显式加 --union 表示你确实要并集。')
            return 4
        union_used = True
        print(f'⚠ --union：清单里有不带 qid 的对，检索目录 {len(retr)} 组片段 ⇒ '
              f'这些对拿"全部片段的并集"比较（读数按并集口径读）')

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
        qs_file = getattr(a, 'questions', '') or ''
        qtexts = load_questions(pathlib.Path(qs_file)) if qs_file else []
        st = axis_stats(pathlib.Path(a.answers), paras, a.n, a.mode, qtexts)
        pct = 100.0 * st['located'] / max(st['n'], 1)
        print(f'\n② 依据轴（{a.mode}，单文件单自然段）：答卷引文 {st["n"]} 条，'
              f'能在材料里逐字定位 {st["located"]} 条 = {pct:.1f}%'
              f'（其中过短引文 {st["short"]} 条，已进分母）')
        # ★ issue #45-5 R3：文档 C 表／readings.json 口径是"剔除题面自带引文后"
        if qtexts:
            print(f'   已按 --questions 剔除题面自带引文 {st["from_question"]} 条'
                  f'（原答卷引文 {st["total"]} 条）——与文档 C 表同口径')
        else:
            print(f'   ⚠ 未给 --questions：题面自带的引文未剔除（本行口径与文档 C 表不同，'
                  f'读数会偏高）；给 `--questions {{"q1": "题面", …}}` 即按 C 表口径算')
        print('   （若很低：你家系统交的是改写体——推理可能对，但证据链不可核实）')

    if missing and not a.allow_missing:
        return 3
    _ = union_used
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--material', required=False)
    ap.add_argument('--retrieval', required=False)
    ap.add_argument('--pairs', required=False)
    ap.add_argument('--answers', default='')
    ap.add_argument('--questions', default='',
                    help='题面文件（.json）：{"q1": "题面", …} 或 ["题面", …]；'
                         '给了就剔除"引文是题面子串"的答卷引文（＝文档 C 表口径）')
    ap.add_argument('--n', type=int, default=DEFAULT_N,
                    help='公共块长度阈值（默认 8；**只作用于 loose 口径**）')
    ap.add_argument('--mode', choices=MODES, default='strict',
                    help='strict＝保留标点逐字包含（默认，无长度门槛）；'
                         'loose＝只留汉字＋≥n 连续公共块')
    ap.add_argument('--allow-missing', action='store_true',
                    help='检索文件缺失时不非零退出（默认 exit 3）')
    ap.add_argument('--union', action='store_true',
                    help='显式允许"不带 qid 时拿全部检索片段的并集比较"'
                         '（默认在检索目录多于一个文件时 exit 4）')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.material and a.retrieval and a.pairs):
        ap.error('需要 --material/--retrieval/--pairs（或加 --selftest）')
    return run_check(a)


if __name__ == '__main__':
    sys.exit(main())
