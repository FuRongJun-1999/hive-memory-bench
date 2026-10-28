# -*- coding: utf-8 -*-
import json
from pathlib import Path
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q

print("=== 归因：判据缺陷 vs 模型能力 ===")
print()
print("[1] 面 H 的两道真题：题卡用 must_contain_any，判分器读 must_contain")
for qid in ("P-H-S01", "P-H-S02"):
    ak = cards[qid]["answer_key"]
    print(f"  {qid}: keys={list(ak.keys())}")
    print(f"    must_contain={ak.get('must_contain')}  must_contain_any={ak.get('must_contain_any')}")
print()
print("[2] 面 J：判据用 content[:12] 字面匹配，但题是开放式问答")
q = cards["P-J-012"]
gt = q["answer_key"]["ground_truth"]["anchors"]
for a in gt[:3]:
    print(f"  锚点 status={a['status']}: {a['content'][:40]}")
print("  → 要求模型逐字复现这些句子才 12 字命中，不现实")
print()
print("[3] 面 E/F：must_not_contain 里放了题目自带的词")
for qid in ("P-E-001", "P-F-001", "P-F-002"):
    q = cards[qid]
    print(f"  {qid}")
    print(f"    题目: {q['question'][:40]}")
    print(f"    禁词: {q['answer_key'].get('must_not_contain')}")
print()
print("[4] 面 D：人设自称「我·持灯人」在中文里极不自然")
q = cards["P-D-001"]
print(f"  人设: {q['persona']}")
print("  → 模型答「行者，路远…灯还亮着」守了 4/5 特征，只缺这个别扭的自称")