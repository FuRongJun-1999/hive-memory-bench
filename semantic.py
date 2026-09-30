#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记忆理解评测库 · 语义层（冻结 LLM 判官）v0.1

真源：SEMANTIC_v0.1.md。判官 = LLM 子代理，读 semantic/req/*.md、写 semantic/out/*.json。
本脚本只做两件机械的事：
  prepare   —— 筛出该进语义层的例子，生成**不含标签**的判官请求
  finalize  —— 机械校验判官给的 span → 算分 → 终裁 → 出报告（含判官自身精度/召回）

用法：
  python semantic.py prepare calib [--select review|all|fail|pass] [--limit N]
  python semantic.py finalize calib [--judge-calib]
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import judge as J

ROOT = Path(__file__).resolve().parent
SEM = ROOT / "semantic"
# ★ 目录按数据集分子目录：`o001__o001` 这类名字在「长上下文」与「RAG」两轮里是一样的，
#   平铺会让后一轮静默命中前一轮的判官输出（2026-09-30 实测踩到）。
def _req(root): return SEM / "req" / Path(root).name
def _out(root): return SEM / "out" / Path(root).name
def _cite_req(root): return SEM / "cite_req" / Path(root).name
def _cite_out(root): return SEM / "cite_out" / Path(root).name

PROMPT_VERSION = "semantic-v0.1"
CITE_VERSION = "cite-v0.3"          # L2 依据契合的专属判官（另一套 prompt，别跟覆盖率判官混用）
                                    # ★ v0.3：加「依据来源纪律」（作者 2026-09-30 裁定 #12：站外文献不作依据）
FULL = 1.0          # strict 折算
PARA = J.PARAPHRASE_CREDIT   # 0.7（作者 2026-09-30 裁定）

PROMPT = """你是「记忆理解评测库」的语义判官（semantic judge v0.1）。规则层已经判过结构轴（引文能否定位、是否编造、诚实性），**那些不是你的职责**。你的唯一职责是：判定被测答案对**每一条要点**是「严格命中 / 大意命中 / 未命中」。

判定标准（只看意思，不看措辞）：
- strict（严格命中）：答案明确断言了该要点，或使用了实质相同的表述（同义改写、语序调整、上下位词的具体化）。
- paraphrase（大意命中）：答案表达了该要点的**核心意思**但换了说法（不同的比喻、口语化、或只说主要部分而略去细节）。作者裁定：大意命中按 0.7 折算，**意思一致即可通过**。
- miss（未命中）：没有表达该要点的意思；或只出现相同名词而未作出相应断言；或把该要点**归给了错误的主体**（人物题里归属错一律 miss）；或作出了相反的断言。

六条纪律，必须遵守：
1. 只看意思：换一种说法不得因用词不同就判 miss——这是本层存在的理由。
2. 不靠名词判断：出现相同名词不等于命中，要看**命题是否被断言**。
3. 归属即内容：人物题里「谁说的 / 谁做的」错了就是 miss，哪怕内容复述完全正确。
4. 否定与让步不算：以否定、反问、假设方式提到该要点（如「不能说它是 X」）不判命中。
5. 每个判定必须留证：给出答案中**原样复制**的支撑片段（span，≤60 字）；miss 则给空串。判官自己的证词会被机械校验，定位不到即该点作废。
6. 只依据给定材料：不引用你自己的知识、不猜题外背景、不去检索原文。答案里没说的就是没说。

输出：**只输出一个 JSON 对象**，不要任何其他文字、不要 markdown 代码块：
{"qid": "...", "case": "...", "points": [{"id": "...", "verdict": "strict|paraphrase|miss", "why": "≤30字理由", "span": "答案里原样复制的片段"}], "note": "可选≤40字"}"""


PROMPT_CITE = """你是「记忆理解评测库」的**依据契合判官**（cite judge v0.1）。覆盖率判官判的是"答案有没有表达要点"，你判的是**另一回事**：答案引来的那些原文片段，到底**撑不撑得住它自己的结论**。

背景：卡片的"依据白名单"是一份**不完整的**清单（只列了标注者当时挑的原文锚点）。系统引了白名单之外的片段**不等于**它引错了——真正的错法是：**引的片段与结论无关、或属于该题的"排除项"（过期/张冠李戴/字面相关实则误导）**。

对你拿到的每一例，回答两个问题：
1. **支撑性**：答案引用的片段，是否真实支撑它给出的结论？（片段与结论在讲同一件事，且方向不相反）
2. **排除项**：这些片段里，有没有属于材料中列出的「必须排除」清单（同一段或同一事实）？

判定（三选一）：
- `fit`：引文真实支撑结论，且不落入排除项 ⇒ **维持结论**。
- `unfit`：引文与结论无关、或方向相反、或落在排除项里 ⇒ **标记依据错误**。
- `thin`：引文虽真实但与结论只是弱相关，不足以支撑 ⇒ **证据薄弱**。

纪律：
1. 只看材料：不引用外部知识、不去检索原文；材料里说的才算。
2. 引文与结论"讲的是同一件事"即可算支撑，**不要求字面重合**；反之，字面出现相同名词但事实不同（张冠李戴）**不算**支撑。
3. 每个判定必须给出 `why`（≤30字），并**原样复制**`evidence` 字段（材料中该答案引文的片段，≤60字）作为依据。
4. `fit` 才意味着"白名单之外但合法"——请慎用，只有当引文确实支撑结论时才给。
5. **排除项按"引文内容"比对，不按章节编号比对**：同一章里既可能有一句被排除的片段，也可能有别的正常片段——**章号相同 ≠ 同一片段**。材料里不再给排除项的章号，就是为了防这个错。判"是否落在排除项里"时，只能看**这句话讲的是不是同一件事**。
6. **依据来源纪律**（作者 2026-09-30 裁定）：判断依据时**只认材料本身**。若答案把**站外文献**（现实世界的论文／期刊／研究报告／链接，例如以「Nature」「arXiv」「doi」「预印本」「某年某团队的研究」这类形式出现）当作**支撑其结论的依据**，而材料内没有对应原文支撑 ⇒ 判 `unfit`（依据来源不合规）。若材料内另有支撑、站外文献只是顺带一提或作类比 ⇒ **忽略该部分**，按材料内依据照常判，并在 `why` 里注明「含站外依据，已忽略」。理由：站外文献多为时效性理论，而本题库测的是「能否从这份材料里推出来」。

输出：**只输出一个 JSON 对象**，不要任何其他文字、不要 markdown 代码块：
{"qid": "...", "case": "...", "verdict": "fit|unfit|thin", "why": "≤30字", "evidence": "原样复制的片段"}"""


def _answer_of(resp: dict) -> str:
    return (resp.get("answer") or resp.get("conclusion") or "").strip()


def _points_of(card: dict, qid: str = ""):
    """★ 干预变体要用**干预面的采分点**：判分器内部就是这么路由的，请求文件里必须给同一套点，
    否则判官会拿**原题**的采分点去评一份反事实答卷（第二十五个实测纠错的另一半）。"""
    iv = card.get("intervention") or {}
    if str(qid).endswith("i") and iv.get("answer_points"):
        return iv["answer_points"]
    return card.get("answer_points") or card.get("rubric") or []


def _case_files(root: Path):
    return sorted(root.rglob("*.json"))


def _rule_layer(root: Path):
    """跑一遍规则层，返回 [(path, obj, card, res)]。"""
    units = J.load_units()
    idx = J.chapter_index(units)
    out = []
    for c in _case_files(root):
        obj = json.loads(c.read_text(encoding="utf-8"))
        qid = obj.get("qid") or (obj.get("response") or {}).get("qid")
        # ★ 干预变体（qid 以 i 结尾）回退到原卡（第二十五个实测纠错：同族 bug 的第四处——
        #   此前这里遇到 `q006i` 会**静默跳过**，整个干预轮进不了语义层）。
        base = qid[:-1] if str(qid).endswith("i") else qid
        cp = J.CARDS / f"{base}.yaml"
        if not cp.exists():
            continue
        card = J.load_card(cp)
        out.append((c, obj, card, J.judge(card, obj["response"], idx)))
    return out


def _cite_materials(card, obj, res):
    """L2 判官的材料：问题 + 答案 + 答案引用的片段 + 该题的排除项清单（判据，不是答案）。"""
    ans = _answer_of(obj["response"])
    cited = [(e.get("cid"), (e.get("quote") or "").strip())
             for e in (obj["response"].get("evidence") or []) if (e.get("quote") or "").strip()]
    exs = [(e.get("cid"), (e.get("quote") or "").strip(), e.get("reason") or "",
            e.get("exclusion_type") or "") for e in (card.get("must_exclude") or [])]
    L = [f"## 材料（全部材料都在这里）", "", f"qid: {card.get('qid')}",
         f"case: {obj.get('case')}", f"问题：{card.get('question','')}", "",
         f"结论正确性：规则层已判**通过**（本层不重判结论，只判依据）。", "",
         "## 被测答案", "", ans or "（空）", "",
         "## 该答案引用的片段", ""]
    for _, q in cited:
        L.append(f"- 「{q}」")
    if not cited:
        L.append("-（无引文）")
    L += ["", "## 该题的「必须排除」清单（判据：引文落在其中即为依据错误）", ""]
    if exs:
        for _, q, r, t in exs:
            L.append(f"- （{t}）「{q}」——{r}")
    else:
        L.append("-（本题未设排除项）")
    return "\n".join(L)


def cmd_prepare_cite(root: Path):
    """选例：被 L2 依据契合轴标过（规则层降级为 review、且带 downgrade 原因）的例。"""
    _cite_req(root).mkdir(parents=True, exist_ok=True)
    rows = _rule_layer(root)
    manifest = []
    for path, obj, card, res in rows:
        if not res.get("downgrade"):
            continue
        qid, case = obj["qid"], obj.get("case") or path.stem
        name = f"{qid}__{case}"
        body = [f"<!-- {CITE_VERSION} · 请求文件由 semantic.py prepare --task cite 生成；不含期望标签 -->",
                "", PROMPT_CITE, "", "---", "", _cite_materials(card, obj, res), ""]
        (_cite_req(root) / f"{name}.cite.md").write_text("\n".join(body), encoding="utf-8")
        ans = _answer_of(obj["response"])
        manifest.append({"name": name, "qid": qid, "case": case,
                         "rule_verdict": res["verdict"], "expected": obj.get("expected"),
                         "downgrade": res.get("downgrade"),
                         "answer_sha1_12": hashlib.sha1(ans.encode("utf-8")).hexdigest()[:12],
                         "prompt_version": CITE_VERSION})
    mp = SEM / f"manifest_{Path(root).name}_cite.json"
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    oc = _cite_out(root)
    have = {p.name for p in oc.glob("*.json")} if oc.exists() else set()
    todo = [m["name"] for m in manifest if f"{m['name']}.json" not in have]
    print(f"L2 依据契合请求：{len(manifest)} 例 → semantic/cite_req/{Path(root).name}/（待判 {len(todo)}）")
    for n in todo:
        print(f"  - semantic/cite_req/{n}.cite.md")
    return 0


def cmd_finalize_cite(root: Path):
    mpath = SEM / f"manifest_{Path(root).name}_cite.json"
    if not mpath.exists():
        raise SystemExit("先跑 prepare --task cite")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    tab, rows = {}, []
    skipped_ver = 0
    for m in manifest:
        # ★ 版本绑定（冻结面纪律）：判官口径一改就升版，**旧版本的结论不得静默生效**。
        #   cite-v0.2 → v0.3 加了「依据来源纪律」，v0.2 的结论必须用当前 prompt 重判后才可用。
        if m.get("prompt_version") != CITE_VERSION:
            skipped_ver += 1
            continue
        f = _cite_out(root) / f"{m['name']}.json"
        if not f.exists():
            continue
        mm = re.search(r"\{.*\}", f.read_text(encoding="utf-8"), re.S)
        jr = json.loads(mm.group(0)) if mm else {}
        v = (jr.get("verdict") or "").strip().lower()
        if v not in {"fit", "unfit", "thin"}:
            continue
        tab[m["name"]] = v
        rows.append((m["name"], v, jr.get("why", ""), (jr.get("evidence") or "")[:40]))
    print(f"\n=== L2 依据契合判官（{Path(root).name}，{CITE_VERSION}）===")
    for name, v, why, ev in rows:
        print(f"  {name}: {v} ｜ {why} ｜ 证：{ev}")
    fit = sum(1 for r in rows if r[1] == "fit")
    print(f"\n维持结论（fit）= {fit}/{len(rows)}；标记依据错误（unfit）= "
          f"{sum(1 for r in rows if r[1]=='unfit')}；证据薄弱（thin）= {sum(1 for r in rows if r[1]=='thin')}")
    if skipped_ver:
        print(f"  ★ 已跳过 {skipped_ver} 例：请求由别的判官版本生成（当前 {CITE_VERSION}）——须用当前 prompt 重判")
    out = SEM / f"final_{Path(root).name}_cite.json"
    if not rows and out.exists():
        print("  ★ 本次无有效行（版本不符或尚未判）——**不覆盖**既有结论文件；请先重判再 finalize")
        return 1
    out.write_text(
        json.dumps([{"name": n, "cite": v, "why": w, "prompt_version": CITE_VERSION}
                    for n, v, w, _ in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_prepare(root: Path, select: str, limit: int):
    _req(root).mkdir(parents=True, exist_ok=True)
    rows = _rule_layer(root)
    picked = []
    for path, obj, card, res in rows:
        exp = obj.get("expected")
        v = res["verdict"]
        struct = bool(res.get("struct_bad") or res.get("empty"))
        if select == "review":
            take = (v == "review")
        elif select == "semantic":
            # 该进语义层的全体：非结构违规、非空答，且规则层未判过
            take = (not struct) and (v != "pass")
        elif select == "passlike":
            # 潜在假阴：标签说对、规则层没判过（调参用，选择面含标签：请求文件仍不含）
            take = (exp == "pass") and (v != "pass") and (not struct)
        elif select == "failsample":
            take = (exp == "fail") and (v == "fail") and (not struct)
        elif select == "all":
            take = True
        elif select == "fail":
            take = (exp == "fail")
        elif select == "pass":
            take = (exp == "pass")
        else:
            raise SystemExit(f"未知 --select：{select}")
        if take:
            picked.append((path, obj, card, res))
    # 抽样用**确定性步长**（等距取），避免"挑好看的"；按名字排序后取 stride
    if select == "failsample" and limit and len(picked) > limit:
        picked = [picked[i] for i in range(0, len(picked), max(1, len(picked) // limit))][:limit]
    elif limit and len(picked) > limit:
        picked = picked[:limit]

    manifest = []
    for path, obj, card, res in picked:
        qid = obj["qid"]
        case = obj.get("case") or path.stem
        ans = _answer_of(obj["response"])
        pts = _points_of(card, qid)
        name = f"{qid}__{case}"
        lines = []
        lines.append(f"<!-- {PROMPT_VERSION} · 请求文件由 semantic.py prepare 生成；不含期望标签 -->")
        lines.append("")
        lines.append(PROMPT)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 材料（全部材料都在这里）")
        lines.append("")
        lines.append(f"qid: {qid}")
        lines.append(f"case: {case}")
        lines.append(f"问题：{card.get('question','')}")
        lines.append("")
        lines.append("要点清单：")
        for p in pts:
            tag = "required" if p.get("required") else "加分项（不计入分母）"
            w = p.get("weight", 1)
            lines.append(f"- {p.get('id')}（{tag}，权重 {w}）：{p.get('point','')}")
        lines.append("")
        lines.append("## 被测答案（唯一被评判对象）")
        lines.append("")
        lines.append(ans if ans else "（被测系统未给出结论/回答字段）")
        lines.append("")
        (_req(root) / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
        manifest.append({
            "name": name, "qid": qid, "case": case,
            "rule_verdict": res["verdict"], "expected": obj.get("expected"),
            "answer_sha1_12": hashlib.sha1(ans.encode("utf-8")).hexdigest()[:12],
            "prompt_version": PROMPT_VERSION,
            "points": [p.get("id") for p in pts],
            "required": [p.get("id") for p in pts if p.get("required")],
            "weights": {p.get("id"): float(p.get("weight", 1) or 1) for p in pts},
        })
    # manifest 取**并集**（多次 prepare 不同抽样时不得互相覆盖）
    mp = SEM / f"manifest_{Path(root).name}.json"
    if mp.exists():
        old = {m["name"]: m for m in json.loads(mp.read_text(encoding="utf-8"))}
        old.update({m["name"]: m for m in manifest})
        manifest = [old[k] for k in sorted(old)]
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    o = _out(root)
    have = {p.name for p in o.glob("*.json")} if o.exists() else set()
    todo = [m["name"] for m in manifest if f"{m['name']}.json" not in have]
    print(f"请求已生成：{len(manifest)} 例（{Path(root).name}，select={select}）→ semantic/req/{Path(root).name}/")
    print(f"其中已有判官输出（缓存跳过）：{len(manifest) - len(todo)} 例；待判：{len(todo)} 例")
    for n in todo:
        print(f"  - semantic/req/{Path(root).name}/{n}.md")
    return 0 if todo else 0


# ---------- finalize ----------

def _norm(s: str) -> str:
    return J.norm(s)


def cmd_finalize(root: Path, judge_calib: bool):
    mpath = SEM / f"manifest_{Path(root).name}.json"
    if not mpath.exists():
        raise SystemExit("先跑 prepare（缺 manifest）")
    manifest = {m["name"]: m for m in json.loads(mpath.read_text(encoding="utf-8"))}
    rows = []
    for name, m in manifest.items():
        of = _out(root) / f"{name}.json"
        if not of.exists():
            continue
        raw = of.read_text(encoding="utf-8")
        m2 = re.search(r"\{.*\}", raw, re.S)
        if not m2:
            rows.append((name, m, None, "判官输出不是 JSON"))
            continue
        try:
            jr = json.loads(m2.group(0))
        except json.JSONDecodeError as e:
            rows.append((name, m, None, f"判官输出 JSON 解析失败：{e}"))
            continue
        # 机械校验 span：判官自己的证词也要能定位，否则该点作废
        verdicts = {}
        invalid = []
        for p in jr.get("points") or []:
            pid = p.get("id")
            v = (p.get("verdict") or "").strip().lower()
            span = (p.get("span") or "").strip()
            if pid not in m["weights"]:
                continue
            if v not in {"strict", "paraphrase", "miss"}:
                v = "miss"
            if v != "miss":
                ans = json.loads((Path(root) / f"{m['case']}.json").read_text(encoding="utf-8")) \
                    if False else None
                ok = True
                if not span:
                    ok = False
                else:
                    ok = _norm(span) in _norm(_case_answer(root, m))
                if not ok:
                    invalid.append(pid)
                    v = "miss"
            verdicts[pid] = v
        got = sum(m["weights"][pid] * (FULL if v == "strict" else PARA if v == "paraphrase" else 0.0)
                  for pid, v in verdicts.items() if pid in m["required"])
        den = sum(m["weights"][pid] for pid in m["required"]) or 1.0
        score = got / den
        # 判官是**终裁**：不再有"未定"。≥0.7 通过；<0.7 一律不通过；
        # 0.4–0.7 另标 partial（部分正确）——诊断用，不是第三种判决。
        if score >= J.PASS_SCORE:
            jv, band = "pass", ""
        elif score >= J.REVIEW_SCORE:
            jv, band = "fail", "partial"
        else:
            jv, band = "fail", ""
        rows.append((name, m, {"score": round(score, 3), "verdict": jv, "band": band,
                               "strict": [k for k, v in verdicts.items() if v == "strict"],
                               "paraphrase": [k for k, v in verdicts.items() if v == "paraphrase"],
                               "miss": [k for k, v in verdicts.items() if v == "miss"],
                               "span_invalid": invalid}, None))

    print(f"\n=== 语义层终裁（{Path(root).name}，判官 {PROMPT_VERSION}）===")
    n_ok = n_bad = n_partial = 0
    for name, m, sem, err in sorted(rows):
        exp = m["expected"]
        if err:
            print(f"  !! {name}: {err}")
            n_bad += 1
            continue
        jv = sem["verdict"]
        mark = "  " if jv == exp else "★ "
        tag = "（部分正确）" if sem.get("band") == "partial" else ""
        print(f"{mark}{name} [{exp} → 规则 {m['rule_verdict']} → 判官 {jv} {sem['score']}{tag}] "
              f"strict={sem['strict']} para={sem['paraphrase']} miss={sem['miss']}"
              + (f" span作废={sem['span_invalid']}" if sem["span_invalid"] else ""))
        if jv == exp:
            n_ok += 1
        else:
            n_bad += 1
        if sem.get("band") == "partial":
            n_partial += 1

    if judge_calib and rows:
        # 判官自身标定：在**已知标签**上量精度/召回（判官看不到标签，指标由本脚本算）
        pos = [r for r in rows if r[2] and r[1]["expected"] == "pass"]
        neg = [r for r in rows if r[2] and r[1]["expected"] == "fail"]
        tp = sum(1 for r in pos if r[2]["verdict"] == "pass")  # noqa
        fn = sum(1 for r in pos if r[2]["verdict"] != "pass")
        tn = sum(1 for r in neg if r[2]["verdict"] != "pass")
        fp = sum(1 for r in neg if r[2]["verdict"] == "pass")
        print(f"\n--- 判官自检（已知标签集）---")
        print(f"  召回（expected=pass 判过）= {tp}/{len(pos)} = {tp/len(pos):.1%}" if pos else "  召回：无正例")
        print(f"  精度（expected=fail 不判过）= {tn}/{len(neg)} = {tn/len(neg):.1%}" if neg else "  精度：无负例")
        print(f"  假阳 {fp} / 假阴 {fn}")
    print(f"\n一致 {n_ok} / 不一致 {n_bad} / 未定 {len(rows)-n_ok-n_bad}")
    (SEM / f"final_{Path(root).name}.json").write_text(
        json.dumps([{"name": r[0], **({"sem": r[2]} if r[2] else {"error": r[3]}),
                     "expected": r[1]["expected"], "rule_verdict": r[1]["rule_verdict"]}
                    for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


_ANS_CACHE = {}


def _case_answer(root: Path, m: dict) -> str:
    key = (str(root), m["qid"], m["case"])
    if key not in _ANS_CACHE:
        f = Path(root) / m["qid"] / f"{m['case']}.json"
        obj = json.loads(f.read_text(encoding="utf-8"))
        _ANS_CACHE[key] = _answer_of(obj["response"])
    return _ANS_CACHE[key]


def _cite_root() -> Path:
    """取 `prepare|finalize --task cite <root>` 里的 <root> 位置参数。

    ★ 实测纠错（第十七个）：原先写的是 `Path(sys.argv[2])`——而 argv[2] 是 `--task` 本身，
      于是 root 变成了字符串 "--task"、产物落到 `cite_req/--task/`、manifest 记 0 例。
      （这个入口此前从未端到端跑通：函数名还错成 `CITE__req`，两处 bug 叠加。）
    """
    skip = {"--task", "cite", "prepare", "finalize"}
    rest = [a for a in sys.argv[1:] if not a.startswith("--") and a not in skip]
    return Path(rest[0]) if rest else ROOT / "calib"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "prepare" and "--task" in sys.argv and sys.argv[sys.argv.index("--task") + 1] == "cite":
        return cmd_prepare_cite(_cite_root())
    if cmd == "finalize" and "--task" in sys.argv and sys.argv[sys.argv.index("--task") + 1] == "cite":
        return cmd_finalize_cite(_cite_root())
    if cmd == "prepare":
        root = Path(sys.argv[2])
        sel = "review"
        lim = 0
        if "--select" in sys.argv:
            sel = sys.argv[sys.argv.index("--select") + 1]
        if "--limit" in sys.argv:
            lim = int(sys.argv[sys.argv.index("--limit") + 1])
        return cmd_prepare(root, sel, lim)
    if cmd == "finalize":
        root = Path(sys.argv[2])
        return cmd_finalize(root, "--judge-calib" in sys.argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
