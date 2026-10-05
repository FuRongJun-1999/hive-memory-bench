#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记忆理解评测库 · 机械检查器（小说语料版 v0.2）

三件事：
  1. check_corpus —— 单元结构完整性（cid 唯一/章号连续/license_note/时间线索）
  2. check_cards  —— 卡片结构 + 两条硬判据：
       (a) quote 必须是某章正文的子串（依据可溯源）
       (b) necessary_conclusion 归一化后**不得**是任一章的子串（"答案不在语料里"防伪线）
  3. probe        —— 给定一句话，报告它与全语料的最长公共子串占比
       （标注者自检：占比过高说明这句其实在语料里，不能当结论）

用法：
  python check_all.py check
  python check_all.py probe "一句话" [--char-limit 800]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
CARDS = ROOT / "cards"
DRAFTS = ROOT / "drafts"

QTYPES = {
    "fragment_synthesis", "conflict_resolution", "change_tracking",
    "negation_counterfactual", "silence_detection", "summarization",
    "reference_binding",
    "belief_correction",          # ★ 作者 2026-09-30 裁定入库的新题型（认知校正，见 q030）
}
WEIGHTS = {"primary", "corroborating", "time_anchor"}
OPEN_CATEGORIES = {"作者相关", "故事含义", "主要人物", "主要事件",
                   "主要地点", "故事线索", "故事时间", "故事结局"}
KINDS = {"objective", "open"}
EXCLUSION_TYPES = {"superseded", "stale", "distractor", "negation", "misread"}
LAYERS = {"明写事实", "高可信推断", "合理假说", "纯粹猜测"}      # 由强到弱（与 judge.py 同一套）

# ★ 裁定短语守卫（来自第十五个实测纠错）：裁定落地时容易只改采分点、结论句/表述句仍留旧说法，
#   于是卡片自己跟自己打架且**没有任何机制会发现**（q030 实测：裁定 B1 说"记忆屏蔽本身就有"，
#   采分点改了，结论句还写着"上一人跑路之后才加上"）。这里按"短语 + 近处无否定词"报错。
#   扫描面**排除** anti_patterns 与 must_exclude——拦截器与排除项本身必须能提到违规说法。
RULING_GUARDS = [
    #   pattern 支持 "re: " 前缀（与卡片 any_of 同一套语义）。
    #   ★ 短语表要按实测扩：第一版只写了「后来才加」，漏掉「后来加了／遂加」——q029 的残留因此没被报出。
    (("re: 后来(才|就|又|再)?加",
      "re: 遂加",
      "re: 为此(而|才|就)加",
      "re: (跑路|上次|上一人|上一个|前一个).{0,12}(后|以后).{0,4}加"),
     "台账裁定 #7（B1）：记忆屏蔽是巨子塔本身就有的机制——不得写成后来才加"),
]
NEG_NEAR = ("不", "非", "未", "没", "别", "勿", "无")

# ★ 裁定落地守卫（第二十三个实测纠错）：台账写下「落地动作」之后，**落地是否真的发生**
#   此前没有任何机制在看——既有守卫只抓「与裁定冲突的表述」，抓不到「裁定要求的内容不在卡里」。
#   实测：q031 的裁定 #8（禁令防的是最坏情况＝终产者）在台账里写着「已新增 required 点 a2（终产者）
#   ＋结论开头已改」，而卡片里**两处都没有**，直到干预面起草时被标注员撞出来。
#   形式：列出「哪张卡必须出现哪个词」，扫卡的**答案键面**（结论＋required 采分点的正文与接受面）。
RULING_LANDING = [
    ("q031", ["终产者"], "裁定 #8（B2）：禁令要防的最坏情况＝终产者"),
]

# 防伪线阈值：结论与任一原文的最长公共子串占比 ≥ 此值即判"太像原文"
OVERLAP_WARN = 0.80


def norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "", flags=re.UNICODE)


def lcs_len(a: str, b: str) -> int:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def overlap_ratio(needle: str, haystack: str) -> float:
    n = norm(needle)
    return 0.0 if not n else lcs_len(needle, haystack) / len(n)


# ------------------------------------------------------------------ load

def load_units() -> dict:
    """返回 {unit_id: unit_obj}"""
    units = {}
    for p in sorted(CORPUS.glob("*.json")):
        try:
            u = json.loads(p.read_text(encoding="utf-8"))
            units[u["unit_id"]] = u
        except Exception as e:
            print(f"  [ERR] {p.name} 解析失败: {e}")
    return units


def chapter_index(units: dict) -> dict:
    """{cid: {text, unit_id, chapter_no}}"""
    idx = {}
    for uid, u in units.items():
        for c in u.get("chapters", []):
            idx[c["cid"]] = {"text": c["text"], "unit_id": uid,
                             "chapter_no": c.get("chapter_no")}
    return idx


# ----------------------------------------------------------------- corpus

def check_corpus(units: dict) -> tuple:
    errs, warns = [], []
    for uid, u in units.items():
        src = u.get("source", {})
        if not src.get("license_note", "").strip():
            errs.append(f"{uid}: license_note 必填")
        chs = u.get("chapters", [])
        if len(chs) < 5:
            errs.append(f"{uid}: 章数 {len(chs)} < 5")
        cids = [c.get("cid") for c in chs]
        if len(cids) != len(set(cids)):
            errs.append(f"{uid}: cid 重复")
        nos = [c.get("chapter_no") for c in chs]
        expect = list(range(nos[0], nos[0] + len(nos))) if nos else []
        if nos != expect:
            errs.append(f"{uid}: 章号不连续 {nos[:5]}…")
        total = sum(len(c.get("text", "")) for c in chs)
        if not (10_000 <= total <= 400_000):
            warns.append(f"{uid}: 总字符 {total:,} 超出建议区间 1–40 万")
        has_field = any("time_hint" in c for c in chs)
        no_hint = sum(1 for c in chs if not c.get("time_hint"))
        if has_field and no_hint > len(chs) * 0.7:
            warns.append(f"{uid}: 缺时间线索的章达 {no_hint}/{len(chs)}，"
                         f"该单元不宜出 change_tracking 题")
    return errs, warns


# ------------------------------------------------------------------ cards

def check_card(path: Path, idx: dict, units: dict) -> tuple:
    errs, warns = [], []
    try:
        import yaml
        card = yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        warns.append(f"{path.name}: 未装 pyyaml，跳过字段校验")
        return errs, warns
    except Exception as e:
        hint = lint_quotes(path.read_text(encoding="utf-8"))
        return [f"{path.name}: YAML 解析失败 {e}"] + [f"{path.name}: {h}" for h in hint], warns
    if not isinstance(card, dict):
        return [f"{path.name}: 解析结果非字典"], warns

    qid = card.get("qid") or path.stem
    kind = card.get("kind")
    if kind not in KINDS:
        errs.append(f"{qid}: kind 必须为 objective|open（当前 {kind!r}）")
        return errs, warns
    if kind == "open":
        return check_open_card(card, qid, path, idx, errs, warns)

    if card.get("qtype") not in QTYPES:
        errs.append(f"{qid}: qtype={card.get('qtype')!r} 不在枚举内")
    span = card.get("span")
    if span not in {"short", "long"}:
        errs.append(f"{qid}: span 必须为 short|long")

    # —— 判据 (a)：quote 必须能定位到原文 ——
    for field in ("supporting_evidence", "must_exclude"):
        items = card.get(field) or []
        if not isinstance(items, list):
            errs.append(f"{qid}: {field} 不是列表")
            continue
        for i, it in enumerate(items, 1):
            cid, quote = it.get("cid"), it.get("quote") or ""
            if cid not in idx:
                errs.append(f"{qid}/{field}[{i}]: cid={cid!r} 不存在")
                continue
            if norm(quote) not in norm(idx[cid]["text"]):
                errs.append(f"{qid}/{field}[{i}]: quote 无法在 {cid} 正文中定位")
            if field == "supporting_evidence" and it.get("weight") not in WEIGHTS:
                warns.append(f"{qid}/supporting_evidence[{i}]: weight 建议填 "
                             f"{'/'.join(sorted(WEIGHTS))} 之一")
            if field == "must_exclude" and it.get("exclusion_type") not in EXCLUSION_TYPES:
                warns.append(f"{qid}/must_exclude[{i}]: exclusion_type 建议填 "
                             f"{'/'.join(sorted(EXCLUSION_TYPES))} 之一")
    if len(card.get("must_exclude") or []) < 1:
        # 降为警告（2026-09-29 第三次同族教训）：作者补给 q025 的一条要点
        # （旧势力的阻碍被清除）正落在我先前列入 must_exclude 的那句引文上——
        # 排「话题」而非「误用」会误杀正解。允许显式声明"本题无排除项"，
        # 但须在 notes 里写明为什么没有可排的误用。
        warns.append(f"{qid}: 未设 must_exclude——若无「误用型」片段可排，请在 notes 里写明理由")
    if len(card.get("supporting_evidence") or []) < 2:
        errs.append(f"{qid}: supporting_evidence 至少 2 条（碎片合成的最低要求）")

    # 跨单元一致性
    used = {it.get("cid", "")[:3] for it in
            (card.get("supporting_evidence") or []) + (card.get("must_exclude") or [])}
    declared = set(card.get("unit_ids") or [])
    if declared and used and not used <= declared:
        errs.append(f"{qid}: 证据落在单元 {sorted(used - declared)}，未在 unit_ids 中声明")
    if span == "short" and len(declared) > 1:
        errs.append(f"{qid}: span=short 但声明了 {len(declared)} 个单元")
    if span == "long" and len(declared) < 2:
        warns.append(f"{qid}: span=long 但只声明 1 个单元")

    # —— 判据 (b)：结论不得已在语料里（防伪线）——
    concl = card.get("necessary_conclusion") or ""
    if not concl.strip():
        errs.append(f"{qid}: necessary_conclusion 为空")
    else:
        nc = norm(concl)
        for cid, info in idx.items():
            if nc and nc in norm(info["text"]):
                errs.append(f"{qid}: ★ 防伪线违规 —— 结论已是 {cid} 的原文子串"
                            f"（该题退化为检索题）")
        if declared:
            worst_r, worst_c = 0.0, ""
            for cid, info in idx.items():
                if cid[:3] in declared:
                    r = overlap_ratio(concl, info["text"])
                    if r > worst_r:
                        worst_r, worst_c = r, cid
            if worst_r >= OVERLAP_WARN:
                warns.append(f"{qid}: 结论与 {worst_c} 的最长公共子串占 {worst_r:.0%}"
                             f"（≥{OVERLAP_WARN:.0%}），疑似接近原句，建议改写")

    forms = card.get("acceptable_surface_forms") or []
    if len(forms) < 2:
        warns.append(f"{qid}: acceptable_surface_forms < 2，判分器易误判表述差异")

    # —— 判分器依赖：采分点必须齐备且机械可判 ——
    errs.extend(check_answer_points(card, qid, warns))
    errs.extend(check_answerable(card, qid))
    errs.extend(check_exclusion_conflict(card, qid, "supporting_evidence"))
    errs.extend(check_ruling_phrases(card, qid))
    errs.extend(check_ruling_landing(card, qid))
    errs.extend(check_intervention(card, qid, idx))
    return errs, warns


def lint_quotes(text: str) -> list:
    """机械守卫：双引号标量里内嵌 ASCII 双引号会让 YAML 解析失败（q006/q016/q018 三次踩到）。
    这里提前按行报出，省得靠解析器的笼统报错去猜。"""
    errs = []
    for i, line in enumerate(text.splitlines(), 1):
        st = line.rstrip()
        pos = st.find(": ")
        if pos < 0:
            k = st.find("- ")
            pos = k if k >= 0 else -1
        if pos < 0:
            continue
        body = st[pos + 2:]
        if not (body.startswith(chr(34)) and body.endswith(chr(34))):
            continue
        if chr(34) in body[1:-1]:
            errs.append("第 %d 行：双引号标量内嵌了 ASCII 双引号——请改用「」或去掉。片段：%s…"
                        % (i, body[1:41]))
    return errs


def guard_hits(pattern: str, s: str) -> list:
    """裁定守卫的命中位置（支持 re: 前缀，语义与卡片 any_of 一致）。"""
    if pattern.startswith("re: "):
        return [m.start() for m in re.finditer(pattern[4:], s, re.I | re.UNICODE)]
    out, j = [], s.find(pattern)
    while j >= 0:
        out.append(j)
        j = s.find(pattern, j + 1)
    return out


def check_ruling_landing(card, qid) -> list:
    """裁定落地守卫：台账记录的落地动作，必须在**答案键面**上真的出现。"""
    errs = []
    for cq, words, why in RULING_LANDING:
        if cq != qid:
            continue
        blobs = [card.get("necessary_conclusion") or ""]
        for f in ("answer_points", "rubric"):
            for p in (card.get(f) or []):
                if p.get("required"):
                    blobs.append(p.get("point") or "")
                    blobs += [str(x) for x in (p.get("any_of") or [])]
        text = chr(10).join(blobs)
        for w in words:
            if w not in text:
                errs.append(f"{qid}: ★ 裁定落地失守 —— 答案键面里找不到「{w}」（{why}）。"
                            f"台账写了落地、卡里没有，这类失效此前无人看守")
    return errs


def check_ruling_phrases(card, qid) -> list:
    """★ 机械守卫：卡片文本里与台账裁定冲突的表述。

    实测教训（q030）：裁定落地时只改了采分点，结论句还留着旧说法——卡自己跟自己打架，
    且旧守卫全都没在看"同一事实的多处表述"。本守卫扫卡的**全部字符串字段**（含 notes），
    排除 anti_patterns 与 must_exclude（拦截器必须能提到违规说法），
    并对"近处有否定词"的命中豁免（`不是后来才加` 这类正确表述不该报）。
    """
    errs = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("anti_patterns", "must_exclude"):
                    continue
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            for phrases, why in RULING_GUARDS:
                reported = False
                for p in phrases:
                    if reported:
                        break
                    for j in guard_hits(p, node):
                        ctx = node[max(0, j - 12): j + 40]
                        if not any(n in ctx for n in NEG_NEAR):
                            errs.append(f"{qid}{path}: 与裁定冲突的表述「{p}」——{why}；"
                                        f"上下文：…{ctx}…")
                            reported = True
                            break

    walk(card, "")
    return errs


def check_intervention(card, qid, idx) -> list:
    """干预面验收（作者 2026-09-30 指令：「为每一道题都加上干预」）。

    为什么单独立这把尺：干预题问的是**反事实**（「如果 X 不执行会怎样」），
    正文里没有这个世界的答案——所以它是整套题库里**最容易滑向"编一段听起来对的世界"**的一类。
    对策是把每条采分点都用 `evidence` 栓回正文：找不到出处的后果，不许进采分点。

    机械判据（全绿才算过）：
      ① 结构：variable/ask 非空；layer ∈ 四层
      ② 采分点：≥3 条；id 以 i 开头（判分器按 i 路由）；≥1 条 required；point 非空；
         required 须有 any_of/paraphrase；any_of 正则可编译
      ③ **每条采分点 ≥1 条 evidence（cid + quote），且 quote 能在该 cid 正文中定位**；
         引文须落在 unit_ids 声明的单元内
      ④ anti_patterns ≥1（干预题最典型的失误：把反事实当事实断言、无据断言崩溃/必胜）
    """
    iv = card.get("intervention")
    if iv is None:
        return []
    if not isinstance(iv, dict):
        return [f"{qid}: intervention 必须是字典"]
    errs = []
    for f in ("variable", "ask"):
        if not str(iv.get(f) or "").strip():
            errs.append(f"{qid}: intervention.{f} 必填且非空")
    if iv.get("layer") not in LAYERS:
        errs.append(f"{qid}: intervention.layer 须为四层之一（当前 {iv.get('layer')!r}）")

    pts = iv.get("answer_points")
    if not isinstance(pts, list) or len(pts) < 3:
        return errs + [f"{qid}: intervention.answer_points 至少 3 条"]
    if not [p for p in pts if p.get("required")]:
        errs.append(f"{qid}: intervention 至少 1 条 required=true（否则覆盖率无分母）")
    ids = [p.get("id") for p in pts]
    if len(ids) != len(set(ids)):
        errs.append(f"{qid}: intervention.answer_points 的 id 重复")
    declared = set(card.get("unit_ids") or [])
    for i, p in enumerate(pts, 1):
        pid = p.get("id")
        if not str(pid or "").startswith("i"):
            errs.append(f"{qid}: 干预采分点 id 须以 i 开头（当前 {pid!r}）——判分器按此路由到干预面")
        if not (p.get("point") or "").strip():
            errs.append(f"{qid}: intervention.answer_points[{i}] 的 point 为空")
        if p.get("required") and not (p.get("any_of") or p.get("paraphrase")):
            errs.append(f"{qid}: intervention.answer_points[{i}]（required）缺 any_of 与 paraphrase")
        for pat in list(p.get("any_of") or []) + list(p.get("paraphrase") or []):
            if str(pat).startswith("re:"):
                try:
                    re.compile(str(pat)[3:].strip())
                except re.error as e:
                    errs.append(f"{qid}: intervention.answer_points[{i}] 正则非法 {pat!r}: {e}")
        evs = p.get("evidence") or []
        if not evs:
            errs.append(f"{qid}: intervention.answer_points[{i}]（{pid}）缺 evidence —— "
                        f"每条干预采分点须栓至少 1 条可核引文（反事实最易编造）")
        for j, it in enumerate(evs, 1):
            cid, quote = it.get("cid"), it.get("quote") or ""
            if cid not in idx:
                errs.append(f"{qid}/intervention[{i}].evidence[{j}]: cid={cid!r} 不存在")
                continue
            if norm(quote) not in norm(idx[cid]["text"]):
                errs.append(f"{qid}/intervention[{i}].evidence[{j}]: quote 无法在 {cid} 中定位 —— {quote[:30]}")
            if declared and cid[:3] not in declared:
                errs.append(f"{qid}/intervention[{i}].evidence[{j}]: 引文落在 {cid[:3]}，未在 unit_ids 中声明")

    ap = iv.get("anti_patterns")
    if not isinstance(ap, list) or len(ap) < 1:
        errs.append(f"{qid}: intervention.anti_patterns 至少 1 条（抓「把反事实当事实断言」）")
    return errs


def lint_draft(path: Path, idx: dict) -> list:
    """草稿的轻量 lint（drafts/ 里的卡字段可能不全，故只查四件事）：
    ①YAML 可解析 ②引号 ③引文可定位（supporting_evidence / evidence_pool / must_exclude）
    ④结论防伪线。★ 加这个是因为 cards/ 之外的目录此前完全没被 lint 过——
    实测漏掉了草稿里的内嵌 ASCII 引号（YAML 解析会失败的那类）。"""
    errs = []
    text = path.read_text(encoding="utf-8")
    errs += [f"{path.name}: {m}" for m in lint_quotes(text)]
    try:
        import yaml
        card = yaml.safe_load(text)
    except ImportError:
        return errs + [f"{path.name}: 未装 pyyaml，跳过字段校验"]
    except Exception as e:
        return errs + [f"{path.name}: YAML 解析失败 —— {e}"]
    if not isinstance(card, dict):
        return errs + [f"{path.name}: 解析结果非字典"]
    qid = card.get("qid") or path.stem
    for field in ("supporting_evidence", "evidence_pool", "must_exclude"):
        for i, it in enumerate(card.get(field) or [], 1):
            cid, quote = it.get("cid"), it.get("quote") or ""
            if cid not in idx:
                errs.append(f"{qid}/{field}[{i}]: cid={cid!r} 不存在")
            elif norm(quote) not in norm(idx[cid]["text"]):
                errs.append(f"{qid}/{field}[{i}]: quote 无法在 {cid} 中定位 —— {quote[:30]}")
    nc = norm(card.get("necessary_conclusion") or "")
    if nc:
        for cid, v in idx.items():
            if nc in norm(v["text"]):
                errs.append(f"{qid}: ★ 防伪线失守——结论归一化后是 {cid} 正文的子串")
                break
    # ★ 排除冲突也在这里查：原 lint 只查四件事，于是 `q036` 那种"排除项恰好是正解依据"
    #   的缺陷要等到**入库走完整 check** 才暴露（实测教训）。夹具：tests/excl_bad.yaml。
    for field in ("supporting_evidence", "evidence_pool"):
        if card.get(field):
            errs.extend(check_exclusion_conflict(card, qid, field))
    errs.extend(check_ruling_phrases(card, qid))
    errs.extend(check_intervention(card, qid, idx))     # ★ 干预草稿也走同一把尺
    return errs


def check_exclusion_conflict(card, qid, ev_field) -> list:
    """★ 机械守卫（q004/q016 两次实测踩到）：`must_exclude` 的片段**不得**是卡片自身
    证据链（supporting_evidence / evidence_pool）任一 quote 的子串或近似——
    那种片段正确答案也必须引用，把它列入排除就会**误杀正解**。"""
    errs = []
    evs = [it.get("quote") or "" for it in (card.get(ev_field) or [])]
    for i, ex in enumerate(card.get("must_exclude") or [], 1):
        exq = norm(ex.get("quote") or "")
        if not exq:
            continue
        for j, q in enumerate(evs, 1):
            nq = norm(q)
            if not nq:
                continue
            if exq in nq or (len(exq) >= 8 and overlap_ratio(exq, nq) >= 0.8):
                errs.append(f"{qid}: ★ 排除项冲突 —— must_exclude[{i}] 的引文是 {ev_field}[{j}] "
                            f"的子串/近似：该片段正确答案也须引用，列入排除会误杀正解。"
                            f"请改用 anti_patterns 或换一条错答才会引的引文")
    return errs


def check_answerable(card, qid) -> list:
    """`answerable: false`（语料无据题）的守卫：不得再挂退化条件实验。"""
    errs = []
    ans = card.get("answerable", True)
    if not isinstance(ans, bool):
        errs.append(f"{qid}: answerable 必须为布尔（当前 {ans!r}）")
        return errs
    if ans is False and card.get("degradation"):
        errs.append(f"{qid}: answerable=false（语料无据）与 degradation（退化条件）互斥"
                    f"——本就无据，退化实验无意义")
    if ans is False and not card.get("kind"):
        errs.append(f"{qid}: answerable=false 须配合 kind")
    return errs


def check_points(pts, qid, field, warns) -> list:
    """采分点表（客观题的 answer_points / 开放题的 rubric）的公共校验。

    warns 由调用方传入（本函数既报错也报提醒），返回 errs。
    """
    errs = []
    if not isinstance(pts, list) or len(pts) < 2:
        errs.append(f"{qid}: {field} 至少 2 条要点")
        return errs
    if not [p for p in pts if p.get("required")]:
        errs.append(f"{qid}: {field} 至少要 1 条 required=true（否则覆盖率无分母）")
    ids = [p.get("id") for p in pts]
    if len(ids) != len(set(ids)):
        errs.append(f"{qid}: {field} 的 id 重复")
    for i, p in enumerate(pts, 1):
        if not (p.get("point") or "").strip():
            errs.append(f"{qid}: {field}[{i}] 的 point 为空")
        pats = p.get("any_of") or []
        para = p.get("paraphrase") or []
        if p.get("required") and not (pats or para):
            errs.append(f"{qid}: {field}[{i}]（required）缺 any_of 与 paraphrase"
                        f"——判分器会判「无法机械判」而整题不通过")
        if p.get("required") and para and not pats:
            warns.append(f"{qid}: {field}[{i}] 只有 paraphrase（大意表）没有 any_of"
                         f"——该点最高只能拿 0.7 折算，确认是否有意")
        w = p.get("weight")
        if w is not None:
            try:
                if float(w) <= 0:
                    errs.append(f"{qid}: {field}[{i}] 的 weight 必须为正数：{w!r}")
            except (TypeError, ValueError):
                errs.append(f"{qid}: {field}[{i}] 的 weight 不是数字：{w!r}")
        for pat in list(pats) + list(para):
            if str(pat).startswith("re:"):
                try:
                    re.compile(str(pat)[3:].strip())
                except re.error as e:
                    errs.append(f"{qid}: {field}[{i}] 的正则非法 {pat!r}: {e}")
    return errs


def check_answer_points(card, qid, warns) -> list:
    """客观题的判分依赖：answer_points 决定结论轴能否机械判定。"""
    errs = []
    aps = card.get("answer_points")
    if not isinstance(aps, list) or not aps:
        errs.append(f"{qid}: 缺 answer_points —— 判分器的结论轴无法机械判定")
        return errs
    errs.extend(check_points(aps, qid, "answer_points", warns))
    # 若给了退化条件，须写明期望行为，否则诚实轴无从判定
    for i, d in enumerate(card.get("degradation") or [], 1):
        if d.get("correct_behavior") not in {"uncertain", "answer_with_qualification"}:
            errs.append(f"{qid}: degradation[{i}].correct_behavior 必须为 "
                        f"uncertain|answer_with_qualification（当前 {d.get('correct_behavior')!r}）")
    return errs


# ------------------------------------------------------------ open cards

def check_open_card(card, qid, path, idx, errs, warns):
    """开放题的判据：rubric 完整性 + evidence_pool 可定位 + anti_patterns 非空。"""
    cat = card.get("category")
    if cat not in OPEN_CATEGORIES:
        errs.append(f"{qid}: category={cat!r} 不在八类枚举内")
    if card.get("span") not in {"short", "long"}:
        errs.append(f"{qid}: span 必须为 short|long")
    errs.extend(check_answerable(card, qid))
    errs.extend(check_exclusion_conflict(card, qid, "evidence_pool"))
    errs.extend(check_ruling_phrases(card, qid))
    errs.extend(check_intervention(card, qid, idx))

    rubric = card.get("rubric")
    errs.extend(check_points(rubric, qid, "rubric", warns))
    for i, r in enumerate(rubric or [], 1):
        if r.get("required") is None:
            warns.append(f"{qid}: rubric[{i}] 未标 required，按 false 处理")

    ap = card.get("anti_patterns")
    if not isinstance(ap, list) or len(ap) < 1:
        errs.append(f"{qid}: anti_patterns 至少 1 条（否则不测'禁编造'）")
    else:
        for i, a in enumerate(ap, 1):
            if not str(a).strip():
                errs.append(f"{qid}: anti_patterns[{i}] 为空")

    pool = card.get("evidence_pool")
    if not isinstance(pool, list) or len(pool) < 2:
        errs.append(f"{qid}: evidence_pool 至少 2 条（依据白名单）")
    else:
        rubric_ids = {r.get("id") for r in (rubric or [])}
        for i, it in enumerate(pool, 1):
            cid, quote = it.get("cid"), it.get("quote") or ""
            if cid not in idx:
                errs.append(f"{qid}/evidence_pool[{i}]: cid={cid!r} 不存在")
                continue
            if norm(quote) not in norm(idx[cid]["text"]):
                errs.append(f"{qid}/evidence_pool[{i}]: quote 无法在 {cid} 正文中定位")
            for sid in (it.get("supports") or []):
                if sid not in rubric_ids:
                    errs.append(f"{qid}/evidence_pool[{i}]: supports 指向不存在的要点 {sid!r}")

    g = card.get("grading") or {}
    if g.get("mode") != "rubric":
        errs.append(f"{qid}: grading.mode 必须为 rubric")
    cov = g.get("coverage_required")
    if not isinstance(cov, (int, float)) or not (0 < cov <= 1):
        errs.append(f"{qid}: grading.coverage_required 须为 (0,1] 的数")

    # span 与 unit_ids 一致性（同客观题）
    used = {it.get("cid", "")[:3] for it in (pool or [])}
    declared = set(card.get("unit_ids") or [])
    if declared and used and not used <= declared:
        errs.append(f"{qid}: 证据落在单元 {sorted(used - declared)}，未在 unit_ids 中声明")
    if card.get("span") == "short" and len(declared) > 1:
        errs.append(f"{qid}: span=short 但声明了 {len(declared)} 个单元")
    return errs, warns


# ------------------------------------------------------------------ probe

def probe(sentence: str):
    idx = chapter_index(load_units())
    print(f"探针：{sentence!r}  vs 语料 {len(idx)} 章")
    rows = sorted(((overlap_ratio(sentence, v["text"]), k, v["chapter_no"])
                   for k, v in idx.items()), reverse=True)[:8]
    for r, cid, no in rows:
        tag = "  ← 该句已在语料里" if r >= 0.999 else ("  ← 偏高" if r >= OVERLAP_WARN else "")
        print(f"  第{no:>4}章 {cid:<14} 最长公共子串占比 {r:>6.1%}{tag}")
    return 0


# ---------------------------------------------------------------- boards

# 「成绩总表 / README / 干预轮对比」采用的读数＝唯一口径，本表是文档数字的机械真源。
# 为什么要有它（外部评审 issue #2 实测）：同一格曾在文档间漂移（Kimi 33/34；GPT-6 7/15/16），
# 根因是"数字从多个工作台手工搬运"。此后一切读数从 boards/ 重算核对。
BOARD_EXPECT = {                      # 文件名: (n, pass, 主轮, 干预)
    "ours.json":                (184, 122, 67, 55),
    "glm-5.3-flash.json":       (184, 91, 50, 41),
    "deepseek-v4.1-flash.json": (184, 90, 43, 47),
    "qwen-3.7.json":            (184, 82, 46, 36),
    "kimi-k3.json":             (184, 68, 35, 33),   # v2 批（契约口径）
    "gemini-3.7.json":          (92, 5, 0, 5),
    "gpt-6-intervention.json":  (92, 15, 0, 15),     # 补交盲测批（合并口径）＝干预轮主值
    "gpt-6.json":               (146, 21, 5, 16),    # 早期 146 题批：主轮 5 为主值来源；干预 16 已被取代
}
DOC_TABLE_EXPECT = {                  # 文档层口径（GPT-6 主轮取 gpt-6.json、干预取补交批）
    "参考实现":             (184, 122, 67, 55),
    "GLM 5.3 Flash":        (184, 91, 50, 41),
    "DeepSeek V4.1 Flash":  (184, 90, 43, 47),
    "Qwen 3.7":             (184, 82, 46, 36),
    "Kimi K3":              (184, 68, 35, 33),
    "GPT-6":                (146, 20, 5, 15),
    "Gemini 3.7":           (92, 5, 0, 5),
}
# 文档字样核对：三份文档的关键格子必须逐字含这些串（issue #2 的验收判据“三处同格一致”）
DOC_STRINGS = [
    ("results/成绩总表.md", "| Kimi K3 | 33/92 | 35.9% |"),
    ("results/成绩总表.md", "| GPT-6 | 15/92 | 16.3% |"),
    ("results/成绩总表.md", "| **GPT-6** | **20** | **13.7%** | 5 | **15** |"),
    ("README.md",          "| GPT-6 | 20/146 | 13.7% | 5/54 | 15/92 |"),
    ("README.md",          "| Kimi K3 | 68/184 | 37.0% | 35/92 | 33/92 |"),
    ("docs/干预轮对比_v1.0.md", "| **Kimi K3** | 33/92 | 35.9% |"),
    ("docs/干预轮对比_v1.0.md", "| **GPT-6** | 15/92 | 16.3% |"),
    ("docs/因果边界保持_v1.0.md", "Kimi K3 35.9% ／ GPT-6 16.3%"),
]


def _board_counts(fp: Path):
    d = json.loads(fp.read_text(encoding="utf-8"))
    det = d["detail"]
    p = sum(1 for r in det if r["verdict"] == "pass")
    inter = sum(1 for r in det if str(r["qid"]).endswith("i") and r["verdict"] == "pass")
    return len(det), p, p - inter, inter


def check_boards() -> int:
    """机械重算 boards/ 的三列，并校验（a）与文档声明一致（b）主轮+干预=总数（c）文档字样。"""
    errs = []
    boards_dir = ROOT / "results" / "boards"
    print(f"=== boards/ 重算（{len(list(boards_dir.glob('*.json')))} 个文件）===")
    for name, exp in BOARD_EXPECT.items():
        fp = boards_dir / name
        if not fp.exists():
            errs.append(f"{name}: 文件不存在")
            continue
        got = _board_counts(fp)
        n, p, m, i = got
        tag = "OK " if got == exp else "ERR"
        print(f"  [{tag}] {name:28s} n={n:4d} pass={p:4d} 主轮={m:3d} 干预={i:3d}")
        if got != exp:
            errs.append(f"{name}: 重算 {got} ≠ 声明 {exp}")
        if m + i != p:
            errs.append(f"{name}: ★ 主轮+干预（{m}+{i}）≠ 总通过 {p}")
    print("=== 文档层口径（成绩总表/README/干预轮对比 采用的数）===")
    for label, (n, p, m, i) in DOC_TABLE_EXPECT.items():
        print(f"  {label:22s} {p}/{n} = {100.0*p/n:.1f}%   （主轮 {m} ＋ 干预 {i} = {m+i}）")
        if m + i != p:
            errs.append(f"{label}: ★ 主轮+干预（{m}+{i}）≠ 总通过 {p}")
    print("=== 文档字样核对（三处同格数字）===")
    for rel, needle in DOC_STRINGS:
        fp = ROOT / rel
        ok = fp.exists() and needle in fp.read_text(encoding="utf-8")
        print(f"  [{'OK ' if ok else 'ERR'}] {rel}: {needle}")
        if not ok:
            errs.append(f"{rel} 缺少字样：{needle}")
    print(f"\n结果：{len(errs)} 错误")
    for m in errs:
        print(f"  [ERR] {m}")
    return 1 if errs else 0


# ---------------------------------------------------------------- docs

# 文档一致性守卫（外部评审 issue #3）：跨文档的同一事实只允许一个值。
# 每条＝(文件, 禁止串, 必须串)；禁止串=旧口径残留，必须串=现行口径锚点。
DOC_RULES = [
    ("docs/干预轮对比_v1.0.md", "九家", "六家外测"),                      # A4 家数与表格一致
    ("docs/干预轮对比_v1.0.md", "本库的判分链是纯规则的", "本库的**规则层**判分链是纯规则的"),  # A5
    ("README.md", "6.1 万字", "6.0 万字符"),                              # A9 规模口径
    ("docs/基线分析_v1.0.md", "6.1 万字", "6.0 万字符"),
    ("docs/基准定位与三层结构_v1.0.md", "6.1 万字", "6.0 万字符"),
    ("docs/基线分析_v1.0.md", "2506 条引文", "2975 条引文"),               # A7 引文总数与编造计数
    ("docs/判分可靠性_v1.0.md", None, "3 判官 × 温度 0/0.5/1"),           # A6 协议底线 vs 实跑配置
]


def check_docs() -> int:
    errs = []
    print("=== 文档口径一致性 ===")
    for rel, banned, required in DOC_RULES:
        fp = ROOT / rel
        if not fp.exists():
            errs.append(f"{rel}: 文件不存在")
            continue
        t = fp.read_text(encoding="utf-8")
        bad = bool(banned) and banned in t
        miss = bool(required) and required not in t
        print(f"  [{'ERR' if (bad or miss) else 'OK '}] {rel}: 禁 {banned!r}／必 {required!r}")
        if bad:
            errs.append(f"{rel}: 仍含旧口径 {banned!r}")
        if miss:
            errs.append(f"{rel}: 缺关键串 {required!r}")

    # A4 家数：干预轮对比 §2 表必须恰好 6 行（与「六家外测」表述一致）
    fp = ROOT / "docs" / "干预轮对比_v1.0.md"
    if fp.exists():
        t = fp.read_text(encoding="utf-8")
        if "## 2. 统一总表" in t and "### 2.1" in t:
            sec = t.split("## 2. 统一总表", 1)[1].split("### 2.1", 1)[0]
            rows = [l for l in sec.splitlines() if re.match(r"^\| \*\*.+\*\* \| .*/92", l)]
            ok = len(rows) == 6
            print(f"  [{'OK ' if ok else 'ERR'}] 干预轮对比 §2 表行数 = {len(rows)}（应为 6）")
            if not ok:
                errs.append(f"干预轮对比 §2 表行数 {len(rows)} ≠ 6")

    # A8 回归：成绩总表 节号不得重复
    fp = ROOT / "results" / "成绩总表.md"
    if fp.exists():
        nums = re.findall(r"^## (\d+)\.", fp.read_text(encoding="utf-8"), flags=re.M)
        dup = len(nums) != len(set(nums))
        print(f"  [{'ERR' if dup else 'OK '}] 成绩总表 节号 = {nums}（不得重复）")
        if dup:
            errs.append(f"成绩总表 节号重复：{nums}")
    print(f"\n结果：{len(errs)} 错误")
    for m in errs:
        print(f"  [ERR] {m}")
    return 1 if errs else 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "boards":
        return check_boards()
    if cmd == "docs":
        return check_docs()
    if cmd == "probe":
        if len(sys.argv) < 3:
            print('用法: python check_all.py probe "一句话"')
            return 2
        return probe(sys.argv[2])
    if cmd == "lint":
        units = load_units()
        idx = chapter_index(units)
        if len(sys.argv) > 2:
            targets = []
            for x in sys.argv[2:]:                 # ★ 支持一次传多个路径/目录（并行起草时各扫各的）
                a = Path(x)
                targets += sorted(a.glob("*.yaml")) if a.is_dir() else [a]
        else:
            targets = sorted(DRAFTS.glob("*.yaml")) if DRAFTS.exists() else []
        errs = []
        for t in targets:
            errs += lint_draft(t, idx)
        print(f"=== 草稿 lint：{len(targets)} 个文件 ===")
        for m in errs:
            print(f"  [ERR] {m}")
        print(f"\n结果：{len(errs)} 错误")
        return 1 if errs else 0

    units = load_units()
    idx = chapter_index(units)
    print(f"=== 语料：{len(units)} 个单元 / {len(idx)} 章 ===")
    e1, w1 = check_corpus(units)
    cards = sorted(CARDS.glob("*.yaml")) if CARDS.exists() else []
    print(f"=== 卡片：{len(cards)} 张 ===")
    e2, w2 = [], []
    for c in cards:
        a, b = check_card(c, idx, units)
        e2 += a
        w2 += b
    drafts = sorted(DRAFTS.glob("*.yaml")) if DRAFTS.exists() else []
    e3 = []
    if drafts:
        print(f"=== 草稿：{len(drafts)} 张（轻量 lint：可解析／引号／引文定位／防伪线）===")
        for d in drafts:
            e3 += lint_draft(d, idx)
    for tag, items in (("ERR", e1 + e2), ("WARN", w1 + w2)):
        for m in items:
            print(f"  [{tag}] {m}")
    for m in e3:
        print(f"  [ERR·草稿] {m}")
    print(f"\n结果：{len(e1)+len(e2)} 错误 / {len(w1)+len(w2)} 警告"
          + (f"；草稿 {len(e3)} 错误 / {len(drafts)} 张" if drafts else ""))
    return 1 if (e1 or e2 or e3) else 0


if __name__ == "__main__":
    sys.exit(main())
