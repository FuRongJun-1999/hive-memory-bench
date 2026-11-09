# -*- coding: utf-8 -*-
"""端到端复测（口径 C）：读已发布的检索明细 → 取材料 → 生成单断言任务 → 判分。

**这个脚本不调 LLM。** 它只做三件事，把「被测系统」的接口留给你：

  1. `--task`  按检索明细把每条断言的材料拼好，输出 JSONL（每行一条，含材料与断言）
  2. 你自己拿这些任务去问任何系统（模型/插件/RAG），把「是/否」填回来，格式见下
  3. `--grade` 读你的答卷，算 TPR/TNR/平衡准确率/φ

用法：
    python scripts/reproduce_e2e.py --task  --arm top1 --out tasks_top1.jsonl
    python scripts/reproduce_e2e.py --task  --arm top3 --out tasks_top3.jsonl
    python scripts/reproduce_e2e.py --grade --picks my_answers.jsonl

答卷格式（JSONL，每行一题）：
    {"qid": "o001", "answers": [{"idx": 0, "answer": "是"}, {"idx": 1, "answer": false}]}

**为什么能复测**：灵枢检索需要 md_cg，外部机器上没有；所以仓库发布
`readings/lingshu_retrieval_rubric92.json`（每条的 gold / top-1 / top-3 章号），
你据此取原文即可，不必复现检索。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from bench_common import chapters_text, grade  # noqa: E402

BENCH = os.path.dirname(HERE)
RETRIEVAL = os.path.join(BENCH, 'readings', 'lingshu_retrieval_rubric92.json')
BANK = os.path.join(BENCH, 'mcq', 'reasoning', '题目_多跳六元素_rubric92_平衡掩码.json')


def load_assertions():
    data = json.load(open(BANK, encoding='utf-8'))
    out = {}
    for q in data:
        for j, pt in enumerate(q.get('points') or []):
            out['%s#%d' % (q['qid'], j)] = pt
    return out


def build_tasks(arm, out_path, with_title=True):
    """按 arm（top1/top3）拼材料，输出单断言任务。"""
    chap = chapters_text(BENCH)
    ret = json.load(open(RETRIEVAL, encoding='utf-8'))
    asserts = load_assertions()
    n_written = 0
    n_missing = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for r in ret['rows']:
            aid = r['aid']
            chapters = [r['top1']] if arm == 'top1' else list(r['top3'])
            chapters = [c for c in chapters if c in chap]
            if not chapters:
                n_missing += 1
                continue
            parts = []
            for c in chapters:
                title, body = chap[c]
                head = ('## 第%d章 %s' % (c, title)) if with_title else ('## 第%d章' % c)
                parts.append(head + chr(10) + body)
            material = (chr(10) * 2).join(parts)
            task = {
                'aid': aid,
                'stmt': asserts[aid]['stmt'],
                'material': material,
                'material_chars': len(material),
                'chapters': chapters,
            }
            f.write(json.dumps(task, ensure_ascii=False) + chr(10))
            n_written += 1
    print('写入任务: %d 条 | 无材料跳过: %d | 文件: %s' % (n_written, n_missing, out_path))
    return n_written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', action='store_true', help='生成单断言任务')
    ap.add_argument('--grade', action='store_true', help='判分')
    ap.add_argument('--arm', default='top1', choices=['top1', 'top3'])
    ap.add_argument('--out', help='--task 的输出路径')
    ap.add_argument('--picks', help='--grade 的答卷路径')
    ap.add_argument('--no-title', action='store_true', help='材料不含「## 第N章」标题行')
    a = ap.parse_args()

    if a.task:
        if not a.out:
            ap.error('--task 需要 --out')
        build_tasks(a.arm, a.out, with_title=not a.no_title)
        return 0
    if a.grade:
        if not a.picks:
            ap.error('--grade 需要 --picks')
        print(json.dumps(grade(BENCH, a.picks), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())