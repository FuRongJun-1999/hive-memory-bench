#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""压缩代价检查器：你的记忆系统，保住了"矛盾的另一侧"吗？

用法：
    python 压缩代价.py --material ./corpus --retrieval ./runs/my_system/retrieval \\
                       --pairs pairs.json [--answers ./runs/my_system/answers] [--n 8]

输入：
  · --material   材料全文：目录（递归读 .txt/.md/.json）或单个文件。
                 .json 会收集其中所有 "text"/"content" 字段（章节式语料直接可用）。
  · --retrieval  检索结果：目录，每题一个文件（.json 或 .txt）。
                 .json 接受三种形状：{"hits":[{"text":…}]} / {"results":[…]} / [{…}]。
  · --pairs      矛盾对清单（.json）："同一事物上的两处记载"的逐字引文。两种写法：
                 [{"qid":"q1","a":"……","b":"……"}, …]   或   {"q1":{"a":"…","b":"…"}}
                 （带 qid 时与检索文件同名匹配；不带 qid 时用全部检索片段求并集）
  · --answers    可选：你家系统的答卷目录。会统计答卷里引文的"可定位率"（依据轴）。
  · --n          公共块长度阈值（默认 8；中文短句建议 6–10 之间取一个固定值并保持）。

输出三列：
  ① 两侧存活 —— 检索片段里"甲"和"乙"各在不在（这是本文的核心读数：对立面有没有被带回来）
  ② 依据轴   —— 答卷引文能否在材料里逐字定位（交改写体的系统这一列会很低）
  ③ 明细     —— 逐对结果（只有一侧／两侧皆无）

口径说明：所有比对都在"只留汉字"的归一化下做（标点不计），并要求 ≥n 字连续公共块；
这是**下界**（把改写命中也算漏）。要更严可以把 --n 调大，或对同一批数据跑两个 n 看排序是否稳定。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

CJK = re.compile(r'[^\u4e00-\u9fff]')


def norm(s: str) -> str:
    return CJK.sub('', s or '')


def common_block(a: str, b: str, n: int) -> bool:
    """归一化后是否有 ≥n 字连续公共块（子串即命中）。"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    n = min(n, len(a), len(b))
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


def load_material(p: pathlib.Path) -> str:
    if p.is_file():
        files = [p]
    else:
        files = sorted([q for q in p.rglob('*') if q.suffix.lower() in ('.txt', '.md', '.json')])
    parts = []
    for f in files:
        if f.suffix.lower() == '.json':
            try:
                parts.extend(collect_texts(json.loads(read_text_file(f))))
            except Exception:  # noqa: BLE001
                continue
        else:
            parts.append(read_text_file(f))
    return '\n\n'.join(parts)


def load_retrieval(p: pathlib.Path) -> dict[str, str]:
    """→ {文件名去后缀: 片段并集文本}"""
    out = {}
    files = [p] if p.is_file() else sorted(q for q in p.rglob('*')
                                           if q.suffix.lower() in ('.json', '.txt'))
    for f in files:
        if f.suffix.lower() == '.json':
            try:
                obj = json.loads(read_text_file(f))
            except Exception:  # noqa: BLE001
                out[f.stem] = read_text_file(f)
                continue
            frags = []
            for key in ('hits', 'results', 'items', 'fragments', 'memories'):
                if isinstance(obj, dict) and isinstance(obj.get(key), list):
                    frags = collect_texts(obj[key])
                    break
            if not frags:
                frags = collect_texts(obj)
            out[f.stem] = '\n\n'.join(frags)
        else:
            out[f.stem] = read_text_file(f)
    return out


def load_pairs(p: pathlib.Path) -> list[dict]:
    obj = json.loads(read_text_file(p))
    if isinstance(obj, dict) and not ('a' in obj or 'b' in obj):
        return [dict(v, qid=k) for k, v in obj.items()]
    if isinstance(obj, dict):
        obj = [obj]
    return [x for x in obj if isinstance(x, dict)]


def quotes_of(obj, min_cjk: int = 6, acc=None) -> list[str]:
    acc = [] if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('quote', 'quoteA', 'quoteB', '引文') and isinstance(v, str):
                if len(norm(v)) >= min_cjk:
                    acc.append(v)
            else:
                quotes_of(v, min_cjk, acc)
    elif isinstance(obj, list):
        for v in obj:
            quotes_of(v, min_cjk, acc)
    return acc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--material', required=True)
    ap.add_argument('--retrieval', required=True)
    ap.add_argument('--pairs', required=True)
    ap.add_argument('--answers', default='')
    ap.add_argument('--n', type=int, default=8, help='公共块长度阈值（默认 8）')
    a = ap.parse_args()

    material = load_material(pathlib.Path(a.material))
    if not material.strip():
        print('材料为空——检查 --material 路径'); return 2
    retr = load_retrieval(pathlib.Path(a.retrieval))
    pairs = load_pairs(pathlib.Path(a.pairs))
    print(f'材料 {len(norm(material))} 汉字｜检索 {len(retr)} 组｜矛盾对 {len(pairs)} 对'
          f'｜公共块阈值 {a.n}\n')

    both = one = none = 0
    print(f'{"对":14s} {"甲":>4s} {"乙":>4s}  来源')
    for pr in pairs:
        qid = str(pr.get('qid') or '')
        blob = retr.get(qid, '\n\n'.join(retr.values())) if qid else '\n\n'.join(retr.values())
        ha = common_block(pr.get('a') or '', blob, a.n)
        hb = common_block(pr.get('b') or '', blob, a.n)
        both += ha and hb
        one += (ha ^ hb)
        none += not ha and not hb
        print(f'{qid or "-":14s} {"✓" if ha else "✗":>4s} {"✓" if hb else "✗":>4s}  '
              f'{qid if qid in retr else "全部片段并集"}')

    total = max(len(pairs), 1)
    print(f'\n① 两侧存活：两侧齐 {both}/{total}｜只剩一侧 {one}/{total}｜两侧全无 {none}/{total}')
    print('   （只剩一侧＝"对面那一侧"被检索丢了——这正是压缩式系统最常见的形态）')

    if a.answers:
        qs = []
        for f in sorted(pathlib.Path(a.answers).rglob('*')):
            if f.suffix.lower() == '.json':
                try:
                    qs.extend(quotes_of(json.loads(read_text_file(f))))
                except Exception:  # noqa: BLE001
                    pass
        mn = norm(material)
        loc = sum(1 for q in qs if norm(q) in mn)
        pct = 100.0 * loc / max(len(qs), 1)
        print(f'\n② 依据轴：答卷引文 {len(qs)} 条，能在材料里逐字定位 {loc} 条 = {pct:.1f}%')
        print('   （若很低：你家系统交的是改写体——推理可能对，但证据链不可核实）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
