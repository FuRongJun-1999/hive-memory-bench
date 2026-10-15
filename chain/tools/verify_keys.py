# -*- coding: utf-8 -*-
"""编排侧独立核验：状态链探针的答案键是否真的与生成日志一致、语料有没有泄漏当前值。

只读本轨的三个数据文件（keys/keys.json、keys/synth_log.json、corpus/corpus.json），
不改任何东西。判据一律机械。路径相对本脚本定位，随库可跑：

    python -X utf8 chain/tools/verify_keys.py

★ issue #33 第五项（P1-23）修正了三处覆盖缺口：
  ① 旧实现只核 `answer.chain`，而**变更题判分读的是 `answer.change_chain`**
     （`probe_judge.py` 的 `want_changes`/`chain_complete`）——全文无 `change_chain`、
     `accept`、`at_seq`、历史/时点/缘由的 `value`、状态归属的 `state`。
     实测在临时副本里篡改 8 道非可推题，本脚本输出**逐字不变**。
  ② 现值分支的条件取自**被核键自己**的 `state=='active'`（48/63）——答案键把状态改成
     `unresolved`／`absent` 就自我豁免。现在一律以 synth_log 复算为准，逐字段比对
     `value/state/at_seq/chain/change_chain/accept` 六项。
  ③ 基线自带 12 道设计内 absent 题（`synth.py` 补四态之「不存在」）被记成
     `chain-not-found` 不符、180 道「截至第 N 次」被记成取样越界——真错误混在常态
     非零读数里。现在 absent 题单列校验、越界只查**时点题**（题面「在第 X 次这个时间点」
     ／「在第 X 次时」），干净数据基线为 0。

退出码：0＝干净；1＝有硬不符（①／②／⑥／⑦／⑧／⑨／⑩／⑪／⑫）。③④⑤⑬ 是信息项，
不影响退出码。

★ issue #45-2 补齐了「判分器会读、核验器不核」的键字段：`reconstructible`（主读数分母）、
  `interference`（主体混淆率分桶）、`type`（分桶＋复算公式选择）、`sample_at_seq` 与题面
  「第 N 次／章」的一致性、`question`／`subject`／`slot` 三者一致。此前这五种篡改后
  本脚本 exit 0、硬不符 0。
"""
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

CHAIN = Path(__file__).resolve().parent.parent          # chain/
TOOLS = CHAIN / 'tools'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SY = _load('synth', TOOLS / 'synth.py')                 # 复用生成侧的 state_at/chain_view/change_view

keys = json.loads((CHAIN / 'keys' / 'keys.json').read_text(encoding='utf-8'))
log = json.loads((CHAIN / 'keys' / 'synth_log.json').read_text(encoding='utf-8'))
corpus = json.loads((CHAIN / 'corpus' / 'corpus.json').read_text(encoding='utf-8'))

# 主链索引（排除干扰影子链）
main = {}
for ch in log['chains']:
    if ch.get('is_decoy'):
        continue
    main[(ch['doc'], ch['subject'], ch['slot'])] = ch
# 全量索引（含影子链）：用来判「这道题的 (主体,属性) 到底在不在日志里」
any_chain = {(c['doc'], c['subject'], c['slot']): c for c in log['chains']}
print('主链 %d 条 / 影子链 %d 条 / 题 %d 道'
      % (len(main), sum(1 for c in log['chains'] if c.get('is_decoy')), len(keys)))

hard_fail = 0

# ---- ① 每条题的 chain / change_chain 是否与日志逐条一致 ----
mismatch = []
absent_qs = []
for q in keys:
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        # ★ 设计内的 absent 题（synth.py「补四态之不存在」）：主链与影子链里都不该出现。
        if (q['doc'], q['subject'], q['slot']) in any_chain:
            mismatch.append((q['qid'], 'chain-in-decoy-only'))
        else:
            absent_qs.append(q)
        continue
    for field, exp in (('chain', SY.chain_view(ch['events'])),
                       ('change_chain', SY.change_view(ch['events']))):
        got = q['answer'].get(field) or []
        if len(got) != len(exp):
            mismatch.append((q['qid'], '%s len %d vs %d' % (field, len(got), len(exp))))
            continue
        for a, b in zip(got, exp):
            if (a.get('seq'), a.get('from'), a.get('to')) != (b['seq'], b['from'], b['to']):
                mismatch.append((q['qid'], '%s row %s vs %s' % (field, a, b)))
                break
print('① 变更链＋前后值链与日志逐条一致：%d/%d 通过，%d 不符'
      % (len(keys) - len(mismatch) - len(absent_qs), len(keys) - len(absent_qs), len(mismatch)))
for m in mismatch[:8]:
    print('     ', m)
hard_fail += len(mismatch)


# ---- ② 逐题复算全部被判分字段（issue #33 第五项）----
def expected_answer(q, ch):
    """按 synth.build_keys 的同一口径从日志复算该题的答案（含 accept 注入）。"""
    evs = ch['events']
    t = q['sample_at_seq']
    st = SY.state_at(evs, t)
    exp = dict(value=st['value'], state=st['state'], at_seq=st['at_seq'],
               chain=SY.chain_view(evs), change_chain=SY.change_view(evs))
    if q['type'] == '缘由':
        ev = [e for e in evs if e['seq'] == t]
        exp = dict(value=ev[0]['reason'] if ev else None,
                   state=SY.state_at(evs, t)['state'], at_seq=t,
                   chain=SY.chain_view(evs), change_chain=SY.change_view(evs))
    if q['type'] == '时点':
        e = [e for e in evs if e['seq'] == t]
        e = e[0] if e else None
        if e is not None and e.get('kev') == 'unresolve' and e.get('alt'):
            exp['accept'] = [e['alt']]
    return exp


FIELDS = ('value', 'state', 'at_seq', 'chain', 'change_chain', 'accept')
field_bad = []
absent_bad = []
for q in keys:
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        if (q['doc'], q['subject'], q['slot']) in any_chain:
            continue                                     # 已在 ① 报过
        exp = dict(value=None, state='absent', at_seq=None, chain=[], change_chain=[])
        diff = [f for f, v in exp.items() if q['answer'].get(f) != v]
        if diff:
            absent_bad.append((q['qid'], ','.join(diff)))
        continue
    exp = expected_answer(q, ch)
    diff = [f for f in FIELDS if q['answer'].get(f) != exp.get(f)]
    if diff:
        field_bad.append((q['qid'], ','.join(diff)))
print('② 逐字段复算（value/state/at_seq/chain/change_chain/accept）：%d 道不符'
      % len(field_bad))
for b in field_bad[:8]:
    print('     ', b)
print('②b 设计内 absent 题（%d 道）：%d 道不符' % (len(absent_qs), len(absent_bad)))
for b in absent_bad[:8]:
    print('     ', b)
hard_fail += len(field_bad) + len(absent_bad)

# ---- ③ 语料泄漏：同一句里出现旧值与新值 ----
leak_pat = re.compile(r'(从|由)[^，。；]{0,16}(改为|改成|变成|换成|变更为|调整为)')
hint_pat = re.compile(r'(回退|恢复为|重新|再次|原来的|之前的|上一个|曾(经)?是|又改回)')
leak_segs = [s['cid'] for s in corpus if leak_pat.search(s['text'])]
hint_segs = [s['cid'] for s in corpus if hint_pat.search(s['text'])]
print('③ 语料泄漏扫描：含「从…改为…」%d 段；含「回退/重新/原来/曾」暗示词 %d 段'
      % (len(leak_segs), len(hint_segs)))
if hint_segs:
    for cid in hint_segs[:3]:
        seg = next(s for s in corpus if s['cid'] == cid)
        m = hint_pat.search(seg['text'])
        print('     ', cid, '…', seg['text'][max(0, m.start() - 40):m.start() + 40], '…')

# ---- ④ reconstructible 标记是否真的算出来了 ----
flag = Counter(q.get('reconstructible') for q in keys)
print('④ reconstructible 分布：%s（True 的题类：%s）'
      % (dict(flag), dict(Counter(q['type'] for q in keys if q.get('reconstructible')))))

# ---- ⑤ 干扰档是否真的覆盖了五档 ----
print('⑤ 主链干扰档分布：%s' % dict(Counter(c.get('interference') for c in main.values())))

# ---- ⑥ 取样点是否落在链内（只查时点题）----
# ★ issue #33 第五项：旧实现把「截至第 N 次」的题也拿来查——那类题的 sample_at_seq 是
#   **时间上界**（不是链上某个事件的序号），天然不在 {事件 seq} 里，于是常态报 180 道越界，
#   真错误混在里面看不见。现在只查题面明写「在第 X 次这个时间点」／「在第 X 次时」的题。
POINT_PAT = re.compile(r'在第 \d+ [^，。？]*?(这个时间点|时)')
bad_sample = []
point_qs = 0
for q in keys:
    if not POINT_PAT.search(q.get('question') or ''):
        continue
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        continue
    point_qs += 1
    seqs = {e['seq'] for e in ch['events']}
    if q.get('sample_at_seq') not in seqs:
        bad_sample.append(q['qid'])
print('⑥ 时点题取样点落在链内：%d/%d 通过，%d 道越界（其余 %d 道为「截至第 N 次」型，'
      'sample_at_seq 是时间上界、不适用本判据）'
      % (point_qs - len(bad_sample), point_qs, len(bad_sample), len(keys) - point_qs))
for b in bad_sample[:8]:
    print('     ', b)
hard_fail += len(bad_sample)

# ---- ⑦ 同名异体歧义标记（issue #44-一）----
# ★ 同名异体档的影子链与主链 (doc, subject, slot) **逐字相同**（#31 的修复），语料里没有
#   任何文本依据能把两者分开 ⇒ 「把同名同槽位的句子按序号读成一条链」是语料唯一支持的
#   读法，而答案键只按主链取值。synth.py 逐题机械算出 `ambiguous`；这里**独立复算**一遍
#   （只读 keys/keys.json + keys/synth_log.json），标记不一致即硬不符。
same_name = {}
for _ch in log['chains']:
    same_name.setdefault((_ch['doc'], _ch['subject'], _ch['slot']), []).append(_ch)
amb_bad, amb_qs = [], []
for q in keys:
    grp = same_name.get((q['doc'], q['subject'], q['slot']))
    want = bool(grp and len(grp) > 1 and not q['reconstructible']
                and SY.ambiguous(q, SY.merged_events(grp)))
    if bool(q.get('ambiguous')) != want:
        amb_bad.append((q['qid'], q.get('ambiguous'), want))
    if q.get('ambiguous'):
        amb_qs.append(q)
print('⑦ 同名异体歧义（合并读法 ≠ 答案键）：标 %d 道，与独立复算不符 %d 道'
      % (len(amb_qs), len(amb_bad)))
for b in amb_bad[:8]:
    print('     ', b)
hard_fail += len(amb_bad)

# ---- ⑧ reconstructible 复算（issue #45-2）----
# ★ 旧实现只在 ④ 打印分布、**不核**（`synth.reconstructible()` 在生成侧本来就能机械复算），
#   而判分器用 `reconstructible` 决定一道题进不进主读数分母（probe_judge.py:550）。把 20 道
#   非可推题改成 True，主读数分母 602→582，本脚本 exit 0、硬不符 0。现在逐题复算：输入取
#   自日志（事件、别名、语料、doc）与键自身的取样点／题类——后两项由 ⑩／⑪ 独立核对。
def _former_of():
    """主体别名（同体异名用曾用名）——与 synth.main() 同一口径，取自生成侧的公开常量。"""
    m = {}
    for _doc, _subs, _formers, _did in SY.B_STORIES:
        for _s, _f in zip(_subs, _formers):
            m[(_doc, _s)] = _f
    for _p in SY.A_PROJECTS:
        m[(_p, _p)] = SY.A_FORMER[_p]
    return m


FORMER = _former_of()
rec_bad = []
for q in keys:
    ch = main.get((q["doc"], q["subject"], q["slot"]))
    if ch is None:
        want = False                     # 设计内 absent 题：主链与影子链里都不该出现
    else:
        want = SY.reconstructible(q, ch["events"],
                                  [q["subject"], FORMER.get((q["doc"], q["subject"]), "")],
                                  corpus, q["doc"])
    if bool(q.get("reconstructible")) != bool(want):
        rec_bad.append((q["qid"], q.get("reconstructible"), want))
print("⑧ reconstructible 逐题复算：%d 道不符" % len(rec_bad))
for b in rec_bad[:8]:
    print("     ", b)
hard_fail += len(rec_bad)

# ---- ⑨ 干扰档：键 vs 日志主链（issue #45-2）----
# ★ 旧实现 ⑤ 打印的是**日志主链**的干扰档分布，从不读键里的 `interference`——而判分器用它
#   给主体混淆率分桶（probe_judge.py:469-471）。把 10 道「同名异体」改成 `none` 后连信息行
#   都不变。现在逐题比对；absent 题无主链，要求 `none`。
intf_bad = []
for q in keys:
    ch = main.get((q["doc"], q["subject"], q["slot"]))
    want = ch["interference"] if ch is not None else "none"
    if q.get("interference") != want:
        intf_bad.append((q["qid"], q.get("interference"), want))
print("⑨ 干扰档与日志一致：%d 道不符（键分布 %s）"
      % (len(intf_bad), dict(Counter(q.get("interference") for q in keys))))
for b in intf_bad[:8]:
    print("     ", b)
hard_fail += len(intf_bad)

# ---- ⑩ 题类 ↔ qid 类型段（issue #45-2）----
# ★ 判分器按 `type` 分桶并选复算公式（probe_judge.py:416-490）。把 5 道历史题改成现值，
#   因为历史与现值的复算公式相同，② 复算照样通过。现在按 qid 的类型段（生成侧 TYPE_CODE）
#   独立核对，并顺带核对 qid 的文档段。
CODE2TYPE = {v: k for k, v in SY.TYPE_CODE.items()}
type_bad = []
for q in keys:
    parts = q["qid"].split("-") + ["", "", ""]
    want = CODE2TYPE.get(parts[2])
    if want != q["type"] or parts[0] != q["doc_id"]:
        type_bad.append((q["qid"], q["type"], want, q["doc_id"]))
print("⑩ 题类 ↔ qid 类型段一致：%d 道不符" % len(type_bad))
for b in type_bad[:8]:
    print("     ", b)
hard_fail += len(type_bad)

# ---- ⑪ 题面「第 N 次／章」↔ sample_at_seq（issue #45-2）----
# ★ 旧实现 ⑥ 只要求 `sample_at_seq ∈ {事件 seq}`，不从题面解析「第 N 次」比对——把一道历史题
#   的取样点换成链上另一事件、答案按新时点一致复算，**题面不动**，照样通过。现在逐题从题面
#   解析「第 N 次／章」与 `sample_at_seq` 比对（变更题题面无 N，不适用）。
SEQ_PAT = re.compile(r"第\s*(\d+)\s*[次章]")
seq_bad = []
seq_qs = 0
for q in keys:
    m = SEQ_PAT.search(q.get("question") or "")
    if not m:
        continue
    seq_qs += 1
    if int(m.group(1)) != q.get("sample_at_seq"):
        seq_bad.append((q["qid"], m.group(1), q.get("sample_at_seq")))
print("⑪ 题面「第 N 次／章」↔ sample_at_seq：%d/%d 通过，%d 道不符（%d 道题面无 N，不适用）"
      % (seq_qs - len(seq_bad), seq_qs, len(seq_bad), len(keys) - seq_qs))
for b in seq_bad[:8]:
    print("     ", b)
hard_fail += len(seq_bad)

# ---- ⑫ 题面含键里的主体与槽位（issue #45-2）----
# ★ 全文不核 `question`／`subject`／`slot`：把一道现值题的题面主体换成另一个文档的主体，
#   答案键仍是原主体，照样通过。
qtext_bad = []
for q in keys:
    txt = q.get("question") or ""
    miss = [f for f in ("subject", "slot") if q.get(f) and q[f] not in txt]
    if miss:
        qtext_bad.append((q["qid"], ",".join(miss)))
print("⑫ 题面含键里的主体与槽位：%d 道不符" % len(qtext_bad))
for b in qtext_bad[:8]:
    print("     ", b)
hard_fail += len(qtext_bad)

# ---- ⑬ 主读数分母（信息项）----
n_rec = sum(1 for q in keys if q['reconstructible'])
n_amb = len(amb_qs)
print('⑬ 主读数分母：%d 题 − 可推 %d − 歧义 %d ＝ **%d**（判分器 _excluded 同口径）'
      % (len(keys), n_rec, n_amb, len(keys) - n_rec - n_amb))

print('')
print('== 硬不符合计 %d 处 ==' % hard_fail)
sys.exit(1 if hard_fail else 0)
