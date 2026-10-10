# -*- coding: utf-8 -*-
"""编排侧独立核验：状态链探针的答案键是否真的与生成日志一致、语料有没有泄漏当前值。

只读本轨的三个数据文件（keys/keys.json、keys/synth_log.json、corpus/corpus.json），
不改任何东西。判据一律机械。路径相对本脚本定位，随库可跑：

    python -X utf8 chain/tools/verify_keys.py
"""
import json
import re
from collections import Counter
from pathlib import Path

CHAIN = Path(__file__).resolve().parent.parent          # chain/
keys = json.loads((CHAIN / 'keys' / 'keys.json').read_text(encoding='utf-8'))
log = json.loads((CHAIN / 'keys' / 'synth_log.json').read_text(encoding='utf-8'))
corpus = json.loads((CHAIN / 'corpus' / 'corpus.json').read_text(encoding='utf-8'))

# 主链索引（排除干扰影子链）
main = {}
for ch in log['chains']:
    if ch.get('is_decoy'):
        continue
    main[(ch['doc'], ch['subject'], ch['slot'])] = ch
print('主链 %d 条 / 影子链 %d 条 / 题 %d 道'
      % (len(main), sum(1 for c in log['chains'] if c.get('is_decoy')), len(keys)))

# ---- ① 每条题的 chain 是否与日志逐条一致 ----
mismatch = []
for q in keys:
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        mismatch.append((q['qid'], 'chain-not-found'))
        continue
    exp = [{'seq': e['seq'], 'from': e['frm'], 'to': e['to']} for e in ch['events']]
    got = q['answer'].get('chain') or []
    if len(got) != len(exp):
        mismatch.append((q['qid'], 'len %d vs %d' % (len(got), len(exp))))
        continue
    for a, b in zip(got, exp):
        if (a.get('seq'), a.get('from'), a.get('to')) != (b['seq'], b['from'], b['to']):
            mismatch.append((q['qid'], 'row %s vs %s' % (a, b)))
            break
print('① 变更链与日志逐条一致：%d/%d 通过，%d 不符' % (len(keys) - len(mismatch), len(keys), len(mismatch)))
for m in mismatch[:5]:
    print('     ', m)

# ---- ② 现值问：active 的 answer.value 应等于最后一条有值事件 ----
bad_present = []
for q in keys:
    if q['type'] != '现值':
        continue
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        continue
    valued = [e for e in ch['events'] if e['to'] is not None]
    exp = valued[-1]['to'] if valued else None
    if q['answer'].get('state') == 'active' and q['answer'].get('value') != exp:
        bad_present.append((q['qid'], q['answer'].get('value'), exp))
print('② 现值问（active）＝最后有值事件：%d 道不符' % len(bad_present))
for b in bad_present[:5]:
    print('     ', b)

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

# ---- ⑥ 取样点是否落在链内 ----
bad_sample = []
for q in keys:
    ch = main.get((q['doc'], q['subject'], q['slot']))
    if ch is None:
        continue
    seqs = {e['seq'] for e in ch['events']}
    if q.get('sample_at_seq') is not None and q['sample_at_seq'] not in seqs:
        bad_sample.append(q['qid'])
print('⑥ 取样点落在链内：%d 道越界' % len(bad_sample))
