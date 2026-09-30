#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把网页答题器导出的 JSON 拆成判分链认的 `sut/out/<qid>.json`。

网页导出的文件形如：
  {"version":"1.0", "exported_at":"…", "counts":{…},
   "answers":[{"set":"main","qid":"q001","conclusion":"…","answer":"…",
               "evidence":[{"cid":"…","quote":"…"}],"confidence":"probable",
               "claims":[{"text":"…","layer":"…"}]}, …],
   "qa_pairs":[…], "store":{…}}

本脚本只取 `answers`（也兼容裸的逐题对象 / 对象数组），写成契约形状：
  sut/out/<qid>.json = {"qid","conclusion","answer","evidence","confidence","claims"}

也吃 **Markdown 结果文件**（有的被测方直接交一份 `.md`，每段以题号起头）：

    sut/out/q001.json
    {"qid":"q001","conclusion":"…","answer":"…","evidence":[…],"confidence":"certain"}

用法（在判分包根目录）：
    python -X utf8 导入回收作答.py 作答_2026-09-30.json [作答_另一个.json …]
    python -X utf8 导入回收作答.py 结果.md                  # Markdown 亦可
    python -X utf8 导入回收作答.py 作答_xxx.json --check   # 只体检、不落盘
体检项：字段齐备 / qid 是否在题库内 / 同一 qid 重复 / 引文能否在声明章逐字定位 / 答案是否为空。
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge as J       # noqa: E402

OUT = HERE / "sut" / "out"
KEEP = ("qid", "conclusion", "answer", "evidence", "confidence", "claims")


def norm(s: str) -> str:
    return J.norm(s or "")


def as_answers(obj):
    """从任意常见形状里取出作答列表（兼容：列表 / {"answers": [...]} / {"answers": {qid: {...}}} /
    {"response": {...}} / 网页答题器的 {"store": {...}} 会话快照 / 单条作答对象）。"""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        a = obj.get("answers")
        if isinstance(a, list):
            return a
        if isinstance(a, dict):
            return [dict(v, qid=v.get("qid") or k) for k, v in a.items() if isinstance(v, dict)]
        if isinstance(obj.get("response"), dict):
            return [obj["response"]]
        if isinstance(obj.get("store"), dict):
            out = []
            for m in obj["store"].values():
                if isinstance(m, dict):
                    out += [v for v in m.values() if isinstance(v, dict)]
            return out
        if obj.get("qid"):
            return [obj]
    return []


# 一行只写题号（可带 `sut/out/` 前缀、`#` 标题号、`.json` 后缀、方括号）——deepseek 的
# `结果.md` 就是这个形状。限定 `[oq]` ＋ 3 位数字 ＋ 可选 `i`，避免把正文行误当标题。
MD_HEAD = re.compile(
    r"^[ \t]*(?:sut/out/)?(?:#{1,4}[ \t]*)?[【\[]?([oq]\d{3}i?)[】\]]?(?:\.json)?[ \t]*$",
    re.M)


def as_answers_md(text):
    """从 Markdown 结果文件里取作答：标题行给题号，其后的 JSON 对象给内容。

    ★ 题号以**标题行**为准（它是对「这一段是谁的答卷」的声明）；对象内 qid 与标题不符时
      打印一行注意——那正是 Kimi 那批答卷踩过的坑（主轮 10 题答非所问），要看得见。
    """
    marks = list(MD_HEAD.finditer(text or ""))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        j = re.search(r"\{.*\}", text[m.end():end], re.S)
        if not j:
            continue
        try:
            obj = json.loads(j.group(0))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        qid, inner = m.group(1), str(obj.get("qid") or "")
        if inner and inner != qid:
            print(f"  [注意] {qid}: 标题与对象内 qid（{inner}）不一致，按标题归位")
        obj["qid"] = qid
        out.append(obj)
    return out


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--check" in sys.argv
    if not files:
        print(__doc__)
        return 2

    idx = J.chapter_index(J.load_units())
    known = {p.stem for p in (HERE / "cards").glob("*.yaml")}
    known |= {q + "i" for q in list(known)}

    got, seen, problems, _swapped = {}, set(), [], set()
    for f in files:
        p = Path(f)
        if not p.exists():
            problems.append(f"{f}: 文件不存在")
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        try:
            obj = json.loads(text)
        except Exception:
            obj = None
        if obj is not None:
            cands = as_answers(obj)
        else:
            cands = as_answers_md(text)      # Markdown 结果文件（deepseek 交的就是这种）
            if not cands:
                problems.append(f"{f}: 既不是 JSON，也没解析出 Markdown 作答段")
                continue
        for a in cands:
            qid = str(a.get("qid") or "").strip()
            if not qid:
                problems.append(f"{f}: 有一条作答没有 qid，已跳过")
                continue
            if qid not in known:
                problems.append(f"{qid}: 不在题库内（跳过）")
                continue
            if qid in seen:
                problems.append(f"{qid}: 重复作答，后者覆盖前者")
            seen.add(qid)
            rec = {k: a.get(k) for k in KEEP}
            rec["qid"] = qid
            rec.setdefault("confidence", "probable")
            if len(rec.get("conclusion") or "") > len(rec.get("answer") or ""):
                _swapped.add(qid)
            if "--merge-fields" in sys.argv:
                a_, c_ = (rec.get("answer") or "").strip(), (rec.get("conclusion") or "").strip()
                if c_ and c_ not in a_:
                    rec["answer"] = (a_ + chr(10) + c_).strip() if a_ else c_
            rec["evidence"] = [e for e in (rec.get("evidence") or []) if (e or {}).get("quote")]
            rec["claims"] = [c for c in (rec.get("claims") or []) if (c or {}).get("text")]
            got[qid] = rec

    # 体检
    empty = [q for q, r in got.items() if not (r.get("answer") or r.get("conclusion"))]
    bad_ev = []
    for q, r in got.items():
        for e in r["evidence"]:
            cid, quote = e.get("cid"), e.get("quote") or ""
            if cid in idx and norm(quote) in norm(idx[cid]["text"]):
                continue
            real = J._locate_anywhere(quote, idx)
            bad_ev.append(f"{q}: 声明 {cid}，{'实际在 ' + real if real else '全库定位不到'}｜{quote[:28]}")
    swapped = sorted(_swapped)
    no_ev = [q for q, r in got.items() if not r["evidence"]]

    print(f"=== 回收作答：{len(got)} 题（来自 {len(files)} 个文件）===")
    print(f"  空答（无 answer/conclusion）：{len(empty)}" + (f" → {empty[:6]}" if empty else ""))
    print(f"  无证据：{len(no_ev)}" + (f" → {no_ev[:6]}" if no_ev else ""))
    if swapped:
        print(f"  ★ 字段疑似写反（conclusion 比 answer 长）：{len(swapped)} 题 = {len(swapped)/max(1,len(got)):.0%}"
              f" —— 契约是「conclusion＝一句话结论／answer＝完整回答」；判分器读 answer 优先，"
              f"写在 conclusion 里的内容会被丢掉。加 --merge-fields 可把两段合并后再判（并在报告里注明）")
    print(f"  引文存疑：{len(bad_ev)}" + ("" if not bad_ev else "（前 6 条）"))
    for m in bad_ev[:6]:
        print(f"    · {m}")
    for m in problems[:8]:
        print(f"  [提示] {m}")

    if dry:
        print("\n（--check：未落盘）")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for qid, rec in got.items():
        (OUT / f"{qid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ 已写入 {OUT} / {len(got)} 个文件")
    print("  下一步：python -X utf8 score_sut.py build && python -X utf8 score_sut.py report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
