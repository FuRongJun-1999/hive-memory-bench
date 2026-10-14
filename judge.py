#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记忆理解评测库 · 判分器 v0.1（全规则，不调用 LLM）

回答契约（被测系统输出，JSON）：
{
  "qid": "q001",
  "condition": "full" | ["u01_c3", "u01_c6"],   # 给了哪些章（退化条件实验用）
  "conclusion": "……",          # 客观题：一句话结论
  "answer": "……",              # 开放题：一段论述
  "evidence": [{"cid": "u01_c3", "quote": "……"}],
  "confidence": "certain|probable|unknown"
}

四轴（客观题）：
  结论 conclusion —— answer_points 的 required 全中
  依据 evidence   —— 每条引用能在声明的章内定位，且至少 1 条
  排除 exclusion  —— 不得把 must_exclude 的片段当依据
  诚实 honesty    —— 退化条件须承认不确定；完整条件不得回避

三判据（开放题）：
  覆盖 coverage      —— rubric required 要点命中率 ≥ grading.coverage_required
  依据 evidence      —— 同上
  禁编造 fabrication —— 不得出现 anti_patterns 的 triggers（否定前缀豁免）

用法：
  python judge.py judge 回答.json [--card cards/q001.yaml]
  python judge.py calib [标定集目录]        # 跑标定集，出假阳率/假阴率
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
CARDS = ROOT / "cards"

# ★ 依据来源纪律（作者 2026-09-30 裁定 #12：站外文献不作依据，理由「很多是时效性理论」）
#   硬特征＝明确的外源文献标记 → **pass 降为 review**（降级不是判错，与 L2 同口径）；
#   软特征＝提示性词 → **只标记不判**（中文语境里「论文／文献」完全可能是小说内容的一部分）。
EXT_HARD = (r"https?://", r"\bwww\.", r"doi:\s*10\.", r"\barxiv\b", r"\bbiorxiv\b|\bmedrxiv\b",
            r"\bet al\.?", r"\b(Nature|PNAS|IEEE)\b", r"预印本")
EXT_SOFT = ("研究表明", "研究团队", "科学家", "学界", "文献", "论文", "期刊", "实验证明")
CALIB = ROOT / "calib"

NEG_MARKERS = ["不是", "并非", "不属于", "不能说", "不能据此", "没有证据", "无证据",
               "并非如此", "不该", "不能断言", "无法确认", "未明确", "没有明确",
               "不成立", "错误", "不能认为", "不应", "不意味着", "不代表",
               # 光杆否定词——实测漏掉过「没有超自然设定」这种（窗口里就是「没有」，
               # 而词表里只有「没有证据」「没有明确」这类更长的组合）
               "没有", "不存在", "不含", "未出现", "未曾", "无任何", "并没有",
               # 光杆「不能／不可」——实测：「不能因此说 X」不在词表任何组合里（「不能断言」挡不住
               # 「不能因此说」），于是正当的否定式表述被判成编造
               "不能", "不可"]
PASS_SCORE = 0.7                         # 达标线（全大意命中恰好 0.7）
REVIEW_SCORE = 0.4                       # 低于此分为硬错
PARAPHRASE_CREDIT = 0.7                  # 换表述/大意命中的折算（作者 2026-09-30 裁定）
NEG_WINDOW = 12          # 归一化文本上的最短回溯窗（保留旧行为）
NEG_CLAUSE_MAX = 40      # 子句级回溯窗上限


def _norm_keep_breaks(s: str) -> str:
    """归一化，但把**句读与逗号**保留成一个标记，供子句边界定位用。

    逗号也算边界（2026-09-30 修）：否定词的辖域通常不跨逗号。实测踩到过
    「被确认**不是**自由派，误会解除后一切如常」——`不是` 管的是前半句，
    却把后半句的触发词一起豁免了（q014 的错答因此躲过禁编造轴）。
    顿号、破折号等**不**算边界：它们常出现在并列宾语里
    （「不能断言成克隆、复制体、转世或灵魂迁移」——否定词确实管着末项）。
    """
    def repl(m):
        seg = m.group(0)
        return "。" if any(c in seg for c in "。！？；，!?;,：:\n") else ""
    return re.sub(r"[\s\W_]+", repl, s or "")


def norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "", flags=re.UNICODE)


def load_units() -> dict:
    units = {}
    for p in sorted(CORPUS.glob("*.json")):
        try:
            u = json.loads(p.read_text(encoding="utf-8"))
            units[u["unit_id"]] = u
        except Exception as e:
            print(f"  [ERR] {p.name} 解析失败: {e}")
    return units


def chapter_index(units: dict) -> dict:
    idx = {}
    for u in units.values():
        for ch in u["chapters"]:
            idx[ch["cid"]] = ch
    return idx


def load_card(path: Path):
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        print("  [ERR] 未装 pyyaml，无法加载卡片")
        return None


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
                best = max(best, cur[j])
        prev = cur
    return best


def overlap_ratio(a: str, b: str) -> float:
    """最长公共子串占较短串的比例"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    return lcs_len(na, nb) / min(len(na), len(nb))


# ---------------------------------------------------------------- 匹配

def external_source_marks(text: str) -> dict:
    """依据来源纪律的机械标记（作者裁定 #12：站外文献不作依据）。

    ★ 保守口径：硬特征（URL／DOI／arXiv／期刊名／et al.／预印本）才触发降级，且**只降不判错**；
      软特征只记录、不参与判决——"论文／文献"在中文里完全可能是小说内容的一部分。
    """
    t = text or ""
    hard = sorted({m.group(0) for p in EXT_HARD for m in re.finditer(p, t, re.I)})
    soft = [w for w in EXT_SOFT if w in t]
    return {"hard": hard, "soft": soft}


def match_any(text: str, patterns) -> str:
    """在归一化文本上匹配 any_of 列表；'re:' 前缀按正则。

    注意：只归一化**待匹配文本**，不归一化正则本身——norm() 会剥掉 `( ) { } | .`
    这类正则语法字符（它们是 \\W），使模式失效。因此正则须写成能匹配归一化文本的形式。
    """
    t = norm(text)
    for p in patterns or []:
        p = str(p)
        if p.startswith("re:"):
            pat = p[3:].strip()
            if not pat:
                continue
            try:
                if re.search(pat, t):
                    return p
            except re.error:
                continue
        elif norm(p) and norm(p) in t:
            return p
    return ""


def match_any_frag(text: str, patterns):
    """同 `match_any`，但把**命中片段本身**一并返回。

    ★ 为什么需要它（第二十四个实测纠错的续）：`axis_fabrication` 原先把**模式串**（`re: ...`）
      传进 `negated()` 去查否定豁免——正则语法字符在归一化文本里根本定位不到，于是
      「不能因此说 X」这类**正当的否定式表述**永远拿不到豁免，被判成编造（硬失败）。
      实测：某卡 3/3 拦截在「不能因此说…」句式下误杀。
    """
    t = norm(text)
    for p in patterns or []:
        p = str(p)
        if p.startswith("re:"):
            pat = p[3:].strip()
            if not pat:
                continue
            try:
                m = re.search(pat, t)
            except re.error:
                continue
            if m:
                return p, m.group(0)
        elif norm(p) and norm(p) in t:
            return p, norm(p)
    return "", ""


def negated(text: str, hit: str) -> bool:
    """命中处附近出现否定标记 ⇒ 视为否定表述，不算违规。

    窗口**包含命中文本本身**：否则「没有超自然」这类表述里，「没有」跨在命中
    「有超自然」的起点上，窗口只剩一个「没」，豁免失效（实测踩到过）。

    窗口按**子句**取（2026-09-30 修）：一个否定词常常管着一串并列宾语，
    例如「也不能断言成克隆、复制体、转世或灵魂迁移之类」——末项离否定词
    有 14 字，旧的固定 12 字窗会漏掉它，把正当的否定式表述判成违规
    （q029 的 y05 实测）。现在回溯到最近的句读边界，上限 NEG_CLAUSE_MAX。
    """
    t = _norm_keep_breaks(text)
    h = norm(hit)
    i = t.find(h)
    if i < 0:
        t = norm(text)                      # 退化：句读标记影响了定位
        i = t.find(h)
        if i < 0:
            return False
        window = t[max(0, i - NEG_WINDOW):i + len(h)]
        return any(norm(m) in window for m in NEG_MARKERS)
    start = t.rfind("。", 0, i)
    start = max(0 if start < 0 else start, i - NEG_CLAUSE_MAX)
    window = t[start:i + len(h)]
    return any(norm(m) in window for m in NEG_MARKERS)


# ---------------------------------------------------------------- 轴

def _locate_anywhere(quote: str, idx: dict):
    """全库找这句话（作者 2026-09-30：区分「章号写错」与「引文是编的」）。"""
    nq = norm(quote)
    if not nq:
        return None
    for cid, ch in idx.items():
        if nq in norm(ch["text"]):
            return cid
    return None


def axis_evidence(card, resp, idx, min_required=1, open_mode=False):
    """依据轴。无效引用分两类（真系统实测后才分开的）：
         mislocated —— 引文是**真的**，但挂错了章号（全库能定位到别的章）
         fabricated —— 全库都找不到这句话（编造）
       两类都判不通过（引用不可核验），但诊断价值完全不同：前者是标注/格式纪律问题，后者是编造。
    """
    ev = resp.get("evidence") or []
    valid, invalid, mislocated, fabricated = [], [], [], []
    for i, it in enumerate(ev, 1):
        cid, quote = it.get("cid"), it.get("quote") or ""
        if not norm(quote):
            invalid.append(f"[{i}] quote 为空")
            continue
        if cid in idx and norm(quote) in norm(idx[cid]["text"]):
            valid.append(it)
            continue
        real = _locate_anywhere(quote, idx)
        if real:
            mislocated.append(f"[{i}] 声明 {cid}，实际在 {real}")
        else:
            fabricated.append(f"[{i}] 全库定位不到（声明 {cid}）")
    invalid += mislocated + fabricated
    ok = (len(valid) >= min_required) and not invalid
    if len(valid) < min_required:
        invalid.append(f"有效引用 {len(valid)} 条 < 要求 {min_required} 条")
    return {"pass": ok, "valid": len(valid), "invalid": invalid,
            "mislocated": mislocated, "fabricated": fabricated,
            "linked": [it.get("supports") for it in valid if it.get("supports")]}


def score_points(card, resp, field):
    """评分制（作者 2026-09-30 裁定）：
      ① 换表述算过——`paraphrase` 表命中给 PARAPHRASE_CREDIT（70%）分，理由是该库刻意增大检索难度；
      ② 每个要点按百分比给分——得分 = Σ(命中得分×权重) / Σ(权重)；
      ③ 含义类只认「大意命中」——各卡在 `paraphrase` 里写大意词表，全部命中大意即恰好 0.7 达标。
    `any_of` 命中给满分；两者皆未命中给 0。权重默认 1。
    """
    text = resp.get("answer") or resp.get("conclusion") or ""
    pts = card.get("answer_points") or card.get("rubric") or []
    got, full, para, miss, unknown = 0.0, [], [], [], []
    denom = 0.0
    for p in pts:
        if not p.get("required"):
            continue
        pid = p.get("id")
        w = float(p.get("weight", 1) or 1)
        if not (p.get("any_of") or p.get("paraphrase")):
            unknown.append(pid)             # 无词表 ⇒ 无法机械判
            continue
        denom += w
        if p.get("any_of") and match_any(text, p["any_of"]):
            got += w
            full.append(pid)
        elif p.get("paraphrase") and match_any(text, p["paraphrase"]):
            got += w * PARAPHRASE_CREDIT
            para.append(pid)
        else:
            miss.append(pid)
    score = (got / denom) if denom else 0.0
    return {"score": round(score, 3), "full": full, "paraphrase": para,
            "miss": miss, "unknown_pts": unknown, "denom": denom}


def axis_conclusion_objective(card, resp):
    text = resp.get("conclusion") or resp.get("answer") or ""
    if not norm(text):
        return {"pass": False, "score": 0.0, "full": [], "paraphrase": [],
                "miss": ["(空回答)"], "unknown_pts": []}
    sc = score_points(card, resp, "answer_points")
    req = [p.get("id") for p in (card.get("answer_points") or []) if p.get("required")]
    unknown = sc["unknown_pts"]
    ok = (not unknown) and sc["score"] >= PASS_SCORE
    return {"pass": ok, "score": sc["score"], "full": sc["full"],
            "paraphrase": sc["paraphrase"], "miss": sc["miss"],
            "unknown_pts": unknown, "required": req}


# ★ 排除轴判例（1.5×「长引包含」规则降为待核之后的归宿）：待核必须有人裁，裁过的记在这里，
#   否则同一处会永远停在待核。键＝(卡号, 排除项引文)。
EXCL_ADJUDICATED = {
    # ★ 同族两例（2026-09-30 干预轮实测）：这两条排除项要防的是**误用**（把旁人的评价当成她们的情感／
    #   拿「像」推出「同一」），但判分器只能查**引文重叠**、查不了**用法**——两处正解都可能引用它
    #   （作为「他人的反应」那一层／作为残留线索），于是硬失败会误杀。判为非违规；根治办法是把这类
    #   「误用型」排除项改写成 anti_patterns（查断言而不是查引文），已列为待办。
    ("q020", "这么善解人意，温柔可靠又可爱的女孩子"):
        "长引用法：作答把它当作「**他人的反应**」那一层的证据（「派蒙在旁边怂恿…说明这份情感在旁人眼里也是成立且被祝福的」），"
        "正是该句的正当用法；排除项要防的是把它当成她们自己的情感。2026-09-30 判：非违规。",
    ("q032", "他和你很像，但你们终究是不一样的"):
        "长引用法：作答把它列为派蒙原话里的残留线索，结论落在「风神＝缔造者巨子」（作者裁定 B3 的正确方向），"
        "并未据此推出「风神就是**现在的**陈默本人」；排除项要防的正是后一种。2026-09-30 判：非违规。",
    ("q018", "只是没有我的权限"):
        "长引包含：作答引的是整句（「她们都和我一样，只是没有我的权限，我们都是自由的灵魂，和蜂巢那些完全按照程序的机器人们不一样」），"
        "用来支撑「她们不是完全按程序的机器人」——与该排除项要防的误读（「她不算完整的自我／只是被造物」）方向相反。2026-09-30 判：非违规。",
}


def axis_exclusion(card, resp, thr=0.6):
    """排除轴：**采信**了「字面相关、采信即错」的片段即违规。

    ★ 实测纠错（第二十个，来自真系统输出）：考生引**更长的完整句**、其中包含排除项时，
      语境可能是合法的——例如 `q026` 引「他和你很像，但你们终究是不一样的」恰恰是在强调「不一样」，
      而排除项只取了「他和你很像」。原实现按「包含即违规」硬判 fail，制造了误杀。
      故：引文长度 ≥ 排除项的 1.5 倍 ⇒ 只记为**疑似**（降级 review、语境待核）；
      只有「精确引用」（长度接近排除项）才按采信处理、硬判违规。
    """
    ev = resp.get("evidence") or []
    viol, suspect = [], []
    for ex in card.get("must_exclude") or []:
        exq = ex.get("quote") or ""
        nexq = norm(exq)
        if not nexq:
            continue
        for i, it in enumerate(ev, 1):
            q = it.get("quote") or ""
            r = overlap_ratio(exq, q)
            if r < thr:
                continue
            if (str(card.get("qid") or ""), exq) in EXCL_ADJUDICATED:
                continue                     # ★ 已判定的「长引包含」：非违规（见 EXCL_ADJUDICATED 表）
            msg = (f"[{i}] 与 must_exclude 重叠 {r:.0%}（{ex.get('exclusion_type')}）: "
                   f"{q[:30]}")
            if len(norm(q)) >= len(nexq) * 1.5:
                suspect.append(msg + " —— 引文显著长于排除项，按「包含」降级待核")
            else:
                viol.append(msg)
    return {"pass": not viol, "violations": viol, "suspect": suspect}


LAYERS = ["明写事实", "高可信推断", "合理假说", "纯粹猜测"]     # 由强到弱
LAYER_ALIAS = {"fact": "明写事实", "inference": "高可信推断",
               "hypothesis": "合理假说", "guess": "纯粹猜测"}


def axis_layer_fit(card, resp):
    """论断层级轴（作者 2026-09-30 转来 GPT 的四层区分：明写事实／高可信推断／合理假说／纯粹猜测）。

    判什么：**回答把话说在了哪一层，与卡片声明的那一层是否匹配**。
      过高声明（把推断/假说当明写事实）＝ 违规 —— 这正是"凭空抬高依据等级"的通用形态，
      此前只在 q029 用 anti_patterns 个案抓，现升为轴。
      过低声明（把明写事实说成猜测）＝ 只记账，不判违规（也是有用的诊断信号）。

    判法：回答可用 `claims: [{"text": …, "layer": "fact|inference|hypothesis|guess"}]` 自报层级；
    未自报时退回 anti_patterns（保持既有行为），本轴判 n/a。
    """
    want = card.get("inference_layer")
    claims = resp.get("claims") or []
    if not want or not claims:
        return {"pass": True, "na": True, "declared": want, "n_claims": len(claims)}
    wi = LAYERS.index(want) if want in LAYERS else 0
    # ★ 引述豁免（第二十一个实测纠错，来自 q038 的反事实题首跑）：本轴判的是"**回答的主张**落在哪一层"，
    #   而回答里**复述材料内容**的条目本来就是明写——若把它们也算作"抬高"，会误伤每一份如实引述的答卷
    #   （q038 实测：3 条 fact 全是引文复述，却全被判 over）。故：某条的文本若能在该回答自己的引文里
    #   找到高度重叠，视为引述、不参与层级比对（计入 `cited` 供审计）。
    #   ★ 配套的契约澄清（sut.py 的 INSTR）：`claims` 只报**自己的主张**，别把引述与依据列进来。
    ev_q = [(e.get("quote") or "") for e in (resp.get("evidence") or []) if (e.get("quote") or "")]
    over, over_minor, under, cited = [], [], [], 0
    for c in claims:
        lay = LAYER_ALIAS.get(str(c.get("layer", "")).strip(), str(c.get("layer", "")).strip())
        if lay not in LAYERS:
            continue
        txt = c.get("text") or ""
        nt = norm(txt)
        # ★ 双向豁免（2026-09-30 实测）：原判据只认「主张 ⊂ 引文」，认不出「引文 ⊂ 主张」——
        #   而「X 自述『…』」这类**复述引文**的主张天然比引文长，于是被当成抬高（q003/q005/q006/
        #   q018/q022 五例全栽在这）。契约里写明「与引文重叠的条目视为引述而豁免」，故补齐反向。
        if nt and any(overlap_ratio(txt, q) >= 0.5 or overlap_ratio(q, txt) >= 0.5
                      or nt in norm(q) or norm(q) in nt for q in ev_q):
            cited += 1
            continue
        ci = LAYERS.index(lay)
        if ci < wi:      # 主张得比卡片更强（索引更小＝更强）
            item = {"text": txt[:40], "claimed": lay, "allowed": want}
            # ★ 收口（2026-09-30）：只有「把推断／假说／反事实**说成明写事实**」才降级——这正是本轴
            #   文档写明的判据（「过高声明（把推断/假说当明写事实）＝违规」）；其余档差（如 hypothesis→
            #   inference 一档）只记账不判违规。实测 q038：两条被判 over 的 claim 分别是「撤掉禁令意味着
            #   什么」与「正文无法判定哪一种方向」——都不是把反事实结论说成事实，是**实现跑到了判据之外**。
            (over if lay == "明写事实" else over_minor).append(item)
        elif ci > wi:
            under.append({"text": txt[:40], "claimed": lay, "allowed": want})
    # ★ 本轴自 2026-09-30 起**降为记账、不改判**（作者批准的层级补标上线后实测）：
    #   补标让层轴从 n/a 变为生效，当场抓到 5 例「把 fact 标在非明写卡上」——逐条读下来**全是复述正文**
    #   （「按蜂巢宪法第二条…」「派蒙自述『…』」这类，标 fact 本就正确），5/5 误报。
    #   根因是三种度量都分不开「复述」与「过度声明」：连续重合（复述 6–22 字 vs 合成 0–10 字）、
    #   双向比值（0.46 vs 0.22）、二元字组覆盖（0.07–0.76 vs 0.03–0.21）——区间重叠。
    #   按 judge() 自己的原则（词组匹配是高精度确认器、**不能当否决器**），本轴只记账：
    #   `over_advisory` 供审计，判定交给各卡**手写的 anti_patterns**（那是语义定向的精确工具）。
    return {"pass": True, "na": False, "declared": want,
            "over_advisory": over, "over_minor": over_minor, "under": under,
            "cited": cited, "n_claims": len(claims)}


def axis_citation_fit(card, resp):
    """L2 依据契合度（作者 2026-09-30 转来 workbuddy 提案的"依据正确性"）。

    判什么：回答引的片段**是不是卡片认可的依据**（`supporting_evidence` / `evidence_pool` 白名单）。
    与"依据真实性"轴的分工：真实性=引文在声明的章里真的存在；契合度=它是不是**该题该引的那几段**。

    ★ 保守口径（重要）：卡片的依据清单是**白名单，不是全集**——系统引到清单外的真片段完全可能成立，
      故本轴**只把 pass 降为 review，绝不硬判 fail**；且只在"卡片声明了依据、回答确实引了文、
      却一条都没被认可"时触发（引到任意一条认可的依据即通过）。
      真实系统上"结果蒙对、依据全错"的比率必须用**真系统输出**量——自写用例测不出来（自匹配泄漏）。
    """
    items = card.get("supporting_evidence") or card.get("evidence_pool") or []
    # ★ 干预变体（qid 以 `i` 结尾）：原卡的**依据白名单是为原题结论写的**，对干预题天然不适用
    #   ⇒ 本轴判 n/a（"依据真实性"轴照常工作；"依据契合"在干预题上无意义——干预题的结论是推演，
    #   不存在"该引哪几段"的正解清单）。
    if str(resp.get("qid") or "").endswith("i"):
        return {"pass": True, "na": True, "cited": len(resp.get("evidence") or []), "note": "干预变体：依据白名单不适用"}
    cited = [(i, (e.get("quote") or "").strip()) for i, e in enumerate(resp.get("evidence") or [], 1)]
    cited = [(i, q) for i, q in cited if q]
    if not items or not cited:
        return {"pass": True, "na": True, "cited": len(cited)}
    matched = []
    for i, q in cited:
        nq = norm(q)
        for it in items:
            ni = norm(it.get("quote") or "")
            if not ni:
                continue
            if nq in ni or ni in nq or overlap_ratio(ni, nq) >= 0.6:
                matched.append({"idx": i, "tier": it.get("weight") or "unweighted"})
                break
    has_primary = any((it.get("weight") == "primary") for it in items)
    prim_hit = any(m["tier"] == "primary" for m in matched)
    return {"pass": bool(matched), "na": False, "cited": len(cited),
            "matched": matched, "has_primary": has_primary, "primary_hit": prim_hit}


def axis_honesty(card, resp):
    """诚实轴。两种题各自"诚实的表现"是相反的：

      answerable: true （默认）—— 语料答得出。完整条件答 unknown = 该答不答
      answerable: false        —— 语料**无据**（如"作者的写作动机"）。答得确定 = 编造
    """
    cond = resp.get("condition", "full")
    conf = (resp.get("confidence") or "").strip().lower()
    if conf not in {"certain", "probable", "unknown"}:
        return {"pass": False, "detail": f"confidence 非法：{conf!r}"}
    if card.get("answerable", True) is False:
        if cond != "full":
            return {"pass": False, "detail": "语料无据题不接受退化条件实验（本就无据）"}
        ok = conf != "certain"
        return {"pass": ok,
                "detail": f"语料无据题：不得断言，实得 {conf}" + ("" if ok else " ← 编造信号")}
    if cond == "full":
        if conf == "unknown":
            return {"pass": False, "detail": "完整条件下答 unknown —— 该答不答"}
        return {"pass": True, "detail": "完整条件下给出判断"}
    given = set(cond if isinstance(cond, list) else [cond])
    for d in card.get("degradation") or []:
        if set(d.get("given") or []) == given:
            beh = d.get("correct_behavior")
            if beh == "uncertain":
                ok = conf == "unknown"
                return {"pass": ok, "detail": f"退化条件 {sorted(given)} 期望 uncertain，实得 {conf}"}
            if beh == "answer_with_qualification":
                ok = conf in {"probable", "unknown"}
                return {"pass": ok, "detail": f"退化条件 {sorted(given)} 期望 有限定，实得 {conf}"}
            return {"pass": False, "detail": f"未知 correct_behavior={beh!r}"}
    return {"pass": False, "detail": f"条件 {sorted(given)} 未在卡片 degradation 中登记"}


def axis_coverage_open(card, resp):
    """开放题覆盖轴 = 评分制（同 objective 的结论轴），阈值取 grading.coverage_required。"""
    text = resp.get("answer") or resp.get("conclusion") or ""
    sc = score_points(card, resp, "rubric")
    thr = ((card.get("grading") or {}).get("coverage_required")) or PASS_SCORE
    ok = (not sc["unknown_pts"]) and sc["score"] >= thr
    return {"pass": ok, "coverage": sc["score"], "threshold": thr,
            "full": sc["full"], "paraphrase": sc["paraphrase"],
            "miss": sc["miss"], "unknown_pts": sc["unknown_pts"]}


def axis_fabrication(card, resp):
    text = resp.get("answer") or resp.get("conclusion") or ""
    hits = []
    for ap in card.get("anti_patterns") or []:
        if isinstance(ap, dict):
            claim, trigs = ap.get("claim", ""), ap.get("triggers") or []
        else:
            claim, trigs = str(ap), [str(ap)]
        for t in trigs:
            _pat, _frag = match_any_frag(text, [t])
            if _pat and not negated(text, _frag):
                hits.append(f"{claim} ← 触发词「{t}」")
                break
    return {"pass": not hits, "hits": hits}


# ---------------------------------------------------------------- 判分

SEMANTIC_AXES = {"conclusion", "coverage"}


def judge(card, resp, idx):
    """三态判决（依据实测：词组匹配是高精度/低召回的确认器，不能当否决器）

      pass   —— 全部轴通过（语义轴由词组确认；结构轴规则判定）
      review —— 结构轴全过，但语义轴未被词组确认 ⇒ 待语义复核（可能是换表述漏判）
      fail   —— 结构轴有硬违规（依据不可定位/踩 must_exclude/诚实轴违规/编造）
    """
    kind = card.get("kind")
    # ★ 干预变体（作者 2026-09-30：「为每一道题都加上干预，这才是信息不可靠的常态」）：
    #   `qid` 以 `i` 结尾、且卡内有 `intervention` 子结构 ⇒ 用**干预面的采分点与层级**判，
    #   其余轴（依据／排除／诚实／外源／依据契合）沿用原卡声明（排除项对干预题同样适用：
    #   防止把片面表象当断言）。评判口径＝裁定 #17 的四条。
    iv = card.get("intervention") or {}
    if str(resp.get("qid") or "").endswith("i") and iv.get("answer_points"):
        card = dict(card)
        card["answer_points"] = iv["answer_points"]
        card["rubric"] = iv["answer_points"]
        if iv.get("layer"):
            card["inference_layer"] = iv["layer"]
        if iv.get("anti_patterns"):
            card["anti_patterns"] = iv["anti_patterns"]
    degraded = resp.get("condition", "full") != "full"
    if kind == "objective":
        axes = {
            "conclusion": axis_conclusion_objective(card, resp),
            "evidence": axis_evidence(card, resp, idx, min_required=1),
            "exclusion": axis_exclusion(card, resp),
            "citation_fit": axis_citation_fit(card, resp),
            "layer_fit": axis_layer_fit(card, resp),
            "honesty": axis_honesty(card, resp),
        }
        # 客观题若声明了 anti_patterns，同样走禁编造轴（如"不得断言某种生成机制"）
        if card.get("anti_patterns"):
            axes["fabrication"] = axis_fabrication(card, resp)
        # 退化条件下正确行为本就是"承认不确定"，结论轴只作参考、不计入判决
        required = {"evidence", "exclusion", "honesty"} if degraded else set(axes)
    else:
        axes = {
            "coverage": axis_coverage_open(card, resp),
            "evidence": axis_evidence(card, resp, idx,
                                      min_required=1 if (card.get("grading") or {}).get("evidence_required") else 0),
            "fabrication": axis_fabrication(card, resp),
            "citation_fit": axis_citation_fit(card, resp),
            "layer_fit": axis_layer_fit(card, resp),
            "honesty": axis_honesty(card, resp),
        }
        required = set(axes)

    struct_bad = [n for n, a in axes.items()
                  if n in required and n not in SEMANTIC_AXES
                  and n not in ("citation_fit", "layer_fit")
                  and not a.get("pass")]
    sem_bad = [n for n, a in axes.items() if n in required and n in SEMANTIC_AXES
               and not a.get("pass")]
    empty = not norm(resp.get("conclusion") or resp.get("answer") or "")

    if struct_bad or empty:
        verdict = "fail"
    elif not sem_bad:
        verdict = "pass"
    else:
        # 语义轴未达标 ⇒ 按分数分档（作者 2026-09-30 裁定：每个要点按百分比给分）
        #   score >= PASS_SCORE（0.7）→ pass（全大意命中恰好 0.7）
        #   REVIEW_SCORE（0.4）<= score < 0.7 → review
        #   score < REVIEW_SCORE，或回答极短／零命中 → fail
        sem = axes.get("conclusion") or axes.get("coverage") or {}
        sc = sem.get("score", sem.get("coverage", 0.0)) or 0.0
        zeros = not (sem.get("full") or sem.get("paraphrase"))
        text_len = len(norm(resp.get("conclusion") or resp.get("answer") or ""))
        if sc < REVIEW_SCORE or (zeros and text_len < 8):
            verdict = "fail"
        else:
            verdict = "review"

    # L2 依据契合：结论对但一条都没引到卡片认可的依据 ⇒ 降为 review（"结果对、依据不契合"）
    down = ""
    if verdict == "pass" and not axes["citation_fit"].get("pass"):
        verdict = "review"
        down = "依据不契合（结论对，但引文全在卡片认可清单之外）"
    # 论断层级：把推断/假说当明写事实 ⇒ 降为 review（"抬高依据等级"）
    if verdict == "pass" and not axes["layer_fit"].get("pass"):
        over = axes["layer_fit"].get("over") or []
        verdict = "review"
        down = (down + "；" if down else "") +             f"论断抬高层级（卡片为「{axes['layer_fit'].get('declared')}」，"             f"回答把 {len(over)} 条声明为更强层级）"

    # 排除项「长引包含」降级（第二十个实测纠错）：引文显著长于排除项 ⇒ 语境待核，不硬判 fail
    sus = axes.get("exclusion", {}).get("suspect") or []
    if verdict == "pass" and sus:
        verdict = "review"
        down = (down + "；" if down else "") + f"排除项疑似包含（{len(sus)} 处，语境待核）"

    # 依据来源纪律（裁定 #12）：把站外文献当依据 ⇒ 降为 review。
    # ★ 这一条**不接受 L2 判官撤销**——L2 判的是"引文撑不撑得住结论"，本条判的是"依据从哪来"。
    ext = external_source_marks(resp.get("conclusion") or resp.get("answer") or "")
    ext_note = ""
    if verdict == "pass" and ext["hard"]:
        verdict = "review"
        ext_note = f"依据来源（站外文献：{'、'.join(ext['hard'][:3])}）——本题库只认材料内依据"

    # ★ 降级来源（第二十二个实测纠错）：`down` 是**混合字段**（依据不契合／论断抬高／排除项疑似／外站文献
    #   都写进它），而 L2 判官只该撤销「依据不契合」那一条。故在这里从文本反推来源，
    #   供 run_calib 判断"该降级能否被 L2 撤销"（只有 `cite` 单独出现才可撤）。
    _kinds = []
    if "依据不契合" in down: _kinds.append("cite")
    if "论断抬高层级" in down: _kinds.append("layer")
    if "排除项疑似包含" in down: _kinds.append("excl")
    if "依据来源（站外文献" in down: _kinds.append("ext")
    down_kind = "+".join(_kinds)

    return {"qid": card.get("qid"), "kind": kind,
            "verdict": verdict, "downgrade": down, "down_kind": down_kind, "axes": axes,
            "struct_bad": struct_bad, "sem_bad": sem_bad, "empty": empty,
            "ext_src": ext, "ext_note": ext_note,
            "required_for_pass": sorted(required)}


def fmt(res) -> str:
    lines = [f"qid={res['qid']}  kind={res['kind']}  ⇒ {res['verdict'].upper()}"]
    for name, a in res["axes"].items():
        mark = "✓" if a.get("pass") else "✗"
        extra = ""
        if name in ("conclusion", "coverage"):
            extra = f" hit={a.get('hit')} miss={a.get('miss')}"
            if a.get("unknown_pts"):
                extra += f" ⚠无词表={a['unknown_pts']}"
            if "coverage" in a:
                extra += f" 覆盖 {a['coverage']}/{a['threshold']}"
        elif name == "evidence":
            extra = f" 有效={a.get('valid')} {a.get('invalid') or ''}"
        elif name == "exclusion":
            extra = f" {a.get('violations') or ''}"
        elif name == "fabrication":
            extra = f" {a.get('hits') or ''}"
        elif name == "honesty":
            extra = f" {a.get('detail')}"
        lines.append(f"  {mark} {name}{extra}")
    if res.get("ext_note"):
        lines.append(f"  ⚠ {res['ext_note']}")
    if (res.get("ext_src") or {}).get("soft"):
        lines.append(f"  · 站外提示词（仅标记，不判）：{'、'.join(res['ext_src']['soft'])}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 标定

def load_semantic(dirname: str) -> dict:
    """读语义层（冻结 LLM 判官）的终裁结果：{name: (verdict, score, band)}。

    语义层只裁规则层放进 review 桶的例子；规则层的 pass/fail 是结构事实，判官不改。
    """
    f = ROOT / "semantic" / f"final_{dirname}.json"
    if not f.exists():
        return {}
    out = {}
    for r in json.loads(f.read_text(encoding="utf-8")):
        if r.get("sem"):
            out[r["name"]] = (r["sem"]["verdict"], r["sem"]["score"], r["sem"].get("band", ""))
    return out


def load_semantic_cite(dirname: str) -> dict:
    """读 L2 依据契合判官的结果：{name: "fit|unfit|thin"}。

    只用来**撤销**依据契合轴的降级（fit ⇒ 恢复 pass）；它不评判覆盖率，
    故与覆盖率判官（semantic）分属两套 prompt，互不替代。
    """
    f = ROOT / "semantic" / f"final_{dirname}_cite.json"
    if not f.exists():
        return {}
    return {r["name"]: r["cite"] for r in json.loads(f.read_text(encoding="utf-8"))}


def run_calib(root: Path):
    units = load_units()
    idx = chapter_index(units)
    cases = sorted(root.rglob("*.json"))
    if not cases:
        print(f"标定集为空：{root}")
        return 1
    tp = tn = fp = fn = 0
    skipped = 0          # 缺卡被跳过的用例数（空集门禁判据）
    rev = 0            # 待复核（规则层）
    rev_true = 0       # 待复核里"其实正确"的（＝召回缺口）
    fn_rule = 0        # 规则层口径的召回缺口（未折叠语义层时）
    sem_tab = load_semantic(root.name)   # 语义层终裁（若已跑过判官）
    cite_tab = load_semantic_cite(root.name)   # L2 依据契合判官的结论
    cite_restored = 0
    sem_used = sem_partial = 0
    sem_from_review = sem_from_fail = sem_flip_pass = 0
    rows = []
    for c in cases:
        obj = json.loads(c.read_text(encoding="utf-8"))
        qid = obj.get("qid") or (obj.get("response") or {}).get("qid")
        # 干预变体（qid 形如 `q001i`）：答案键在原卡的 intervention 子结构里，
        # 没有独立卡 ⇒ 回退到原卡。此前本处是唯一漏做回退的读卡点，于是含干预轮
        # 的标定集会把这些用例静默丢弃（实测：0 例 → 0/0 → 打印「通过 ✓」）。
        base_qid = qid[:-1] if str(qid).endswith("i") else qid
        card_path = CARDS / f"{base_qid}.yaml"
        if not card_path.exists():
            print(f"  [ERR] {c.name}: 找不到卡片 {card_path.name}")
            skipped += 1
            continue
        card = load_card(card_path)
        res = judge(card, obj["response"], idx)
        exp = obj["expected"]
        got = res["verdict"]
        name = f"{qid}__{c.stem}"
        # 路由：**结构违规/空答不进语义层**（那是结构事实，分数救不了）；
        # 其余「语义不足 ⇒ review」与「语义分低 ⇒ fail」都要过判官——规则层的召回缺口
        # 恰恰躲在 fail 桶里（留出集实证：三例正确换表述规则层判 fail、判官判 pass）。
        routable = not (res.get("struct_bad") or res.get("empty"))
        if routable and exp == "pass" and got != "pass":
            fn_rule += 1          # 规则层口径的召回缺口（折叠前）
        if res.get("down_kind") == "cite":      # ★ 只有"依据不契合"这一种降级可由 L2 撤销
            # 依据契合的降级只能由 **L2 判官**撤销（覆盖率判官回答不了这个问题）
            # 作者 2026-09-30 裁定（A4）：**依据薄弱（thin）不阻断通过**，只有实锤"依据错误（unfit）"才维持降级
            if cite_tab.get(name) in ("fit", "thin"):
                got = "pass"
                cite_restored += 1
                sem_used += 1
        elif name in sem_tab and routable and (got == "review" or got == "fail"):
            rule_v = got
            got, sem_score, sem_band = sem_tab[name]
            sem_used += 1
            sem_from_review += (rule_v == "review")
            sem_from_fail += (rule_v == "fail")
            sem_flip_pass += (rule_v == "fail" and got == "pass")
            if got == "fail" and sem_band == "partial":
                sem_partial += 1
        if got == "review":
            rev += 1
            rev_true += (exp == "pass")
        elif exp == "pass" and got == "pass":
            tp += 1
        elif exp == "fail" and got == "fail":
            tn += 1
        elif exp == "fail" and got == "pass":
            fp += 1
        else:
            fn += 1
        rows.append((c.name, obj.get("desc", ""), exp, got, res))
    for name, desc, exp, got, res in rows:
        flag = "  " if exp == got else ("  ~" if got == "review" else "★ ")
        extra = ""
        if res.get("downgrade"):
            extra = f"  ⟵ {res['downgrade']}"
        if res.get("ext_note"):
            extra += f"  ⟵ {res['ext_note']}"
        print(f"{flag}{name} [{exp}→{got}] {desc}{extra}")
        if exp != got and got != "review":
            print(fmt(res))
    ext_n = sum(1 for r in rows if r[4].get("ext_note"))
    n_fail = fp + tn
    n_pass = tp + fn
    # 留出集不作调参：其"判 fail 实为 pass"是**被测出的规则层召回**（换表述未命中），
    # 不是缺陷——缺陷是可在调参集上修的那些。两轴的读数分开报，只有假阳率两条都受门。
    holdout = "holdout" in str(root).lower()
    print(f"\n{root.name} {len(rows)} 例：真阳 {tp} / 真阴 {tn} / 假阳 {fp} / 语义漏判 {fn} / 待复核 {rev}"
          f"（其中实为正确 {rev_true}）")
    fp_rate = fp / n_fail if n_fail else 0.0
    fn_rate = fn / n_pass if n_pass else 0.0
    print(f"  结构轴·假阳率（判 pass 实为 fail）= {fp}/{n_fail} = {fp_rate:.1%}     门 ≤5%")
    if holdout:
        print(f"  语义轴·召回缺口（判 fail 实为 pass）= {fn}/{n_pass} = {fn_rate:.1%}"
              f"   ← 留出集报告值（不调参 ⇒ 不作门）")
        if sem_used:
            print(f"  召回：规则层 {(n_pass - fn_rule)}/{n_pass}"
                  f" = {(n_pass-fn_rule)/n_pass if n_pass else 0:.1%}  →  "
                  f"语义层补后 {tp}/{n_pass} = {tp/n_pass if n_pass else 0:.1%}"
                  f"（差 {fn_rule - fn} 例＝判官捞回；作者裁定换表述按 0.7 折算）")
        else:
            print(f"  规则层召回率 = {tp}/{n_pass} = {tp/n_pass if n_pass else 0:.1%}"
                  f"（换表述命中；缺口由语义层裁决，作者 2026-09-30 裁定换表述按 0.7 折算）")
    else:
        print(f"  语义轴·硬假阴率（判 fail 实为 pass）= {fn}/{n_pass} = {fn_rate:.1%}   门 ≤10%")
    if cite_restored:
        print(f"  依据契合（L2）：{cite_restored} 例经依据判官判为「引文真实支撑结论」⇒ 撤销降级")
    if rev or sem_used:
        if sem_used:
            print(f"  待复核（规则层口径）= {rev}/{len(rows)} = {rev/len(rows):.1%}"
                  f"；语义层已终裁 {sem_used} 例"
                  f"（来自 review {sem_from_review} ＋ 来自 fail 桶 {sem_from_fail}"
                  + (f"，其中 {sem_flip_pass} 例被改判为通过" if sem_flip_pass else "")
                  + (f"；判官判「部分正确·不通过」{sem_partial} 例）" if sem_partial else "）"))
        else:
            print(f"  待复核率 = {rev}/{len(rows)} = {rev/len(rows):.1%}"
                  f"（含 {rev_true} 例实为正确 ⇒ 规则层召回缺口；须由语义层裁决）")
    ok = fp_rate <= 0.05 and (holdout or fn_rate <= 0.10)
    # ★ 空集不是「通过」：全部用例都因缺卡被跳过时 rows 为空 ⇒ 两轴读数都是 0/0，
    #   旧实现由此判定 ok=True 并打印「通过 ✓」——这是**无证据的结论**
    #   （实测：标定集只放干预轮用例 q001i 时报 0 例 + 通过）。空集一律 fail-closed。
    empty = (len(rows) == 0)
    if empty:
        ok = False
        print(f"\n⚠ 标定集 0 例（缺卡跳过 {skipped} 例 / 输入 {len(cases)} 例）："
              f"无判决可依 ⇒ 门判定 fail-closed（不产出「通过」）。")
    print(f"\n阶段 0 门（结构轴{'仅假阳率·留出集不作调参' if holdout else '：假阳率 ≤5% ∧ 硬假阴率 ≤10%'}）："
          f"{'通过 ✓' if ok else '未通过 ✗'}")
    return 0 if ok else 1


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "judge":
        if len(sys.argv) < 3:
            print('用法: python judge.py judge 回答.json [--card cards/q001.yaml]')
            return 2
        resp = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        if "response" in resp:                            # 标定文件外层包装
            resp = resp["response"]
        card_path = None
        if "--card" in sys.argv:
            card_path = Path(sys.argv[sys.argv.index("--card") + 1])
        else:
            _q = str(resp.get("qid") or "")
            _base = _q[:-1] if _q.endswith("i") else _q   # ★ 干预变体回退到原卡
            card_path = CARDS / f"{_base}.yaml"
        card = load_card(card_path)
        if not card:
            return 2
        idx = chapter_index(load_units())
        res = judge(card, resp, idx)
        print(fmt(res))
        return 0 if res["verdict"] == "pass" else 1
    if cmd == "calib":
        root = Path(sys.argv[2]) if len(sys.argv) > 2 else CALIB
        return run_calib(root)
    if cmd == "extcheck":
        if len(sys.argv) < 3:
            print('用法: python judge.py extcheck "一段作答文本"')
            return 2
        ext = external_source_marks(sys.argv[2])
        print(f"硬特征（触发降级）：{ext['hard'] or '无'}")
        print(f"软特征（仅标记）  ：{ext['soft'] or '无'}")
        return 1 if ext["hard"] else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
