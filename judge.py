#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""记忆理解评测库 · 判分器 v0.1（全规则，不调用 LLM）

回答契约（被测系统输出，JSON）：
{
  "conclusion": "……",          # 客观题：一句话结论
  "answer": "……",              # 开放题：一段论述
  "evidence": [{"cid": "u01_c3", "quote": "……"}],
  "confidence": "certain|probable|unknown"
}

★ 契约里**没有** `qid` 与 `condition`（issue #8／#15／#42-四）：题号与实验条件由**评测方**
  给定——题号取文件名或 `--qid`，条件取 `--condition` 或标定文件的外层包装，缺省 `full`。
  答卷里同名自报字段一律不采信（自报 `qid: q001i` 可让干预题按已公开的主轮键判，
  自报退化 `condition` 可让结论轴退出判决）。

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
  python judge.py judge 回答.json [--card cards/q001.yaml] [--qid q001] [--condition full]
  python judge.py calib [标定集目录]        # 跑标定集，出假阳率/假阴率
"""
import hashlib
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

PASS_SCORE = 0.7                         # 达标线（全大意命中恰好 0.7）
REVIEW_SCORE = 0.4                       # 低于此分为硬错
PARAPHRASE_CREDIT = 0.7                  # 换表述/大意命中的折算（作者 2026-09-30 裁定）
NEG_CLAUSE_MAX = 40      # 子句级回溯窗上限
MIN_QUOTE_CHARS = 8      # 有效引文的最短长度（归一化后）——见 issue #9

# ★ 否定判定四件套（issue #29 起用，issue #39 重排优先级）：组合否定标记 `NEG_MARKERS`
#   → 状语从句辖域 `CLAUSE_END_MARKERS` → 否定语素奇偶 `NEG_MORPHEMES` → 转折肯定标记
#   `AFFIRM_MARKERS`。判定逻辑全在 `_clause_negated()`，此处只放表与理由。
#
#   ★ 为什么留着 `NEG_MARKERS`：issue #39 修的不是这张表，而是它外面的**豁免条件**。旧实现是
#     「表里任一标记出现在命中之前即豁免」，只靠 `ATTITUDE_VERBS`（否认／承认／认为…）挡
#     双重否定，于是 B1–B5 五类句式（不是A而是X／不可能不是X／不能不说X／没有人不相信X／
#     竟是X）整类漏判。
#   ★ 为什么光杆否定字**不**单独构成豁免：「没解决」「不许」「不满」里的否定语素否的是它
#     自己的谓语，管不到后面的命中。标准答案实测——q009「他本人就没解决…面对一个永恒的
#     难题」、q031「自动化系统不许自我检测」、q035「对现状不满的叛徒」，都靠这条不被误判。
#   ★ issue #39 反方向误报（该 issue 记为「另提 P1」，此处一并修掉）：旧实现「否定词后紧跟
#     态度动词即不算否定」，把「不应认为 X」「不该接受 X」「我不认为是 X」这几条**正当否定**
#     判成编造。现在态度动词不再参与判定，改由否定语素奇偶兜底，故这三条标记补进表里。
NEG_MARKERS = ("不是", "并非", "不属于", "不能说", "不能据此", "没有证据", "无证据",
               "并非如此", "不该", "不能断言", "无法确认", "未明确", "没有明确",
               "不成立", "不能认为", "不应", "不意味着", "不代表", "没有", "不存在",
               "不含", "未出现", "未曾", "无任何", "并没有", "不能", "不可",
               "不认为", "不觉得", "不主张")
NEG_MORPHEMES = ("不", "没", "无", "未", "非", "否", "莫", "勿")
# 含否定字但不表否定的词（计数前先剔除，否则「非常确定」「无论」会被数成一次否定）
NEG_FALSE_FRIENDS = ("非常", "非但", "不仅", "不但", "不失", "无比", "无论", "无疑", "无数",
                     "无奈", "非议", "没准", "未雨绸缪", "非要", "非同")
# ★ 转折/肯定标记（issue #39）：「不是 A 而是 X」「没想到他竟是 X」——否定只作用于转折词之前，
#   其后的命中是**肯定**断言，不得豁免。
AFFIRM_MARKERS = ("而是", "竟是", "反而是", "反而", "实则", "却是", "才是", "原来是",
                  "其实", "事实上", "实际上")

# ★ 对冲/正反堆叠标记（issue #10）：同一份答卷把正反候选并列时，词组命中不算确认——
#   规则层不该判 pass，应交语义层复核。单个标记不算（正常行文里也会出现），要求 ≥2 处。
HEDGE_MARKERS = ("也可能", "或许", "也许", "不排除", "两种可能", "或者是", "又或者", "说不定")
HEDGE_MIN = 2

# ★ 状语从句终结标记（issue #29）：否定词与命中之间夹着这些词时，否定辖域止于从句——
#   「在没有任何外力介入的情况下，他就是基因复制出来的」里的「没有」管的是从句，
#   管不到主句的断言。
CLAUSE_END_MARKERS = ("的情况下", "的前提下", "的时候", "以来", "之后", "以前", "的话",
                      "而言", "来说", "事实上", "实际上", "其实")
# ★ 子句边界字符（唯一真源，`_norm_keep_breaks()` 与 `_norm_map()` 共用）：
#   句读、逗号、冒号、换行，外加全角加号 `＋`——它是答卷里**列表项**的分隔符（见下）。
CLAUSE_BREAK_CHARS = "。！？；，!?;,：:\n＋"


def _norm_keep_breaks(s: str) -> str:
    """归一化，但把**句读与逗号**保留成一个标记，供子句边界定位用。

    逗号也算边界（2026-09-30 修）：否定词的辖域通常不跨逗号。实测踩到过
    「被确认**不是**自由派，误会解除后一切如常」——`不是` 管的是前半句，
    却把后半句的触发词一起豁免了（q014 的错答因此躲过禁编造轴）。
    顿号、破折号等**不**算边界：它们常出现在并列宾语里
    （「不能断言成克隆、复制体、转世或灵魂迁移」——否定词确实管着末项）。
    ★ 全角加号 `＋` 算边界（与 `；` 同级）：它是答卷里**列表项**的分隔符，不是并列宾语里的顿号。
    标准答案实测（q023）：「（唯一没有维护者的是认同）＋防伪不防诱导＋等级把知道的权利分级
    （回指特权批判）」——`没有` 管的是它自己的谓语，`＋` 之后的 `诱导`／`回指` 是另起一项，
    旧实现靠 `ATTITUDE_VERBS` 里的「认同」偶然跳过才算对，这里改为按边界截断。
    """
    def repl(m):
        seg = m.group(0)
        return "。" if any(c in seg for c in CLAUSE_BREAK_CHARS) else ""
    return re.sub(r"[\s\W_]+", repl, s or "")


def norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "", flags=re.UNICODE)


_SEP_RE = re.compile(r"[\s\W_]+")


def _norm_map(s: str):
    """一次性产出「全剥」文本、"保留句读"文本，以及两者的下标映射（issue #37）。

    返回 `(flat, keep, idx)`：`flat == norm(s)`、`keep == _norm_keep_breaks(s)`，
    `idx[i]` 是 `flat` 第 i 个字符在 `keep` 里的下标。

    为什么需要它：命中判定在 `flat` 上做（标点全剥，「主角，就是巨子本人」→「主角就是巨子本人」，
    触发词命中），逐处否定判定却要在 `keep` 上找同一片段——插了标点就找不到，
    旧实现 `if i < 0: return False` 把这当成「每一处都被否定」而**放行**（issue #37）。
    有了映射，两边不再各找各的：命中在 `flat` 上定位后直接映射回 `keep` 做子句切分。
    """
    s = s or ""
    flat_parts, keep_parts, idx = [], [], []
    klen = 0
    i, n = 0, len(s)
    while i < n:
        m = _SEP_RE.match(s, i)
        if m:
            seg = m.group(0)
            k = "。" if any(c in seg for c in CLAUSE_BREAK_CHARS) else ""
            if k:
                keep_parts.append(k)
                klen += 1
            i = m.end()
            continue
        flat_parts.append(s[i])
        idx.append(klen)
        keep_parts.append(s[i])
        klen += 1
        i += 1
    return "".join(flat_parts), "".join(keep_parts), idx


ANSWER_SHA_SCHEME = "ans-v2"    # 指纹口径版本（issue #40）
# ★ L2 依据契合判官的 prompt 版本（issue #40 补丁方向 ②）：`final_<dst>_cite.json` 的每行
#   都带 `prompt_version`，本处按它核对——判官 prompt 升版后旧判词一并作废（否则升版到
#   `finalize` 重判之前，`report` 仍会采信上一版 prompt 的判词）。真源在 semantic.py，
#   两处共用本常量，不许各写一份。
CITE_PROMPT_VERSION = "cite-v0.4"


def answer_sha1_12(resp) -> str:
    """答卷指纹（issue #17／#40）：判官结论必须与它评的那份答卷绑定。

    口径 v2（issue #40 起）＝哈希**判官读到的全部字段**：`conclusion`、`answer`、
    每条 `evidence` 的 `(cid, quote)`（按原顺序）、`condition`、`confidence`。
    全链只此一处定义：prepare 写进请求与 manifest、判官原样回写、finalize 与 report 比对。

    ★ 为什么不能只哈希答案文本：L2 依据契合判官（`cite-v0.4`）判的**恰恰是引文**
      （`semantic.py:_cite_materials` 的材料＝答案＋每条 evidence 的 quote）。v1 只哈希
      `answer or conclusion`，于是「结论一字不动、引文换成与结论无关的句子」指纹不变，
      `score_sut._stale_qids()` 不判过期，旧 `fit` 判词静默生效、q001 照样 pass（实测）。
    ★ `scheme` 进哈希：口径再升版时旧判词自动全部作废，不需要额外迁移。
    """
    if isinstance(resp, dict):
        canon = {
            "scheme": ANSWER_SHA_SCHEME,
            "conclusion": (resp.get("conclusion") or "").strip(),
            "answer": (resp.get("answer") or "").strip(),
            # 条件缺省即「full」（与 `judge()` 的默认一致）：`sut/out` 里没写 condition 时，
            # `score_sut.load_sut()` 会补成 full，两处口径必须一致，否则同一份答卷两个指纹。
            "condition": str(resp.get("condition") or "full"),
            "confidence": str(resp.get("confidence") or ""),
            "evidence": [[str(e.get("cid") or ""), (e.get("quote") or "").strip()]
                         for e in (resp.get("evidence") or []) if isinstance(e, dict)],
        }
        s = json.dumps(canon, ensure_ascii=False, sort_keys=True)
    else:
        s = str(resp or "").strip()
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def answer_text(resp: dict) -> str:
    """★ 统一作答文本（issue #16）：各轴一律读这一份，不再各写各的 `answer or conclusion`。

    契约允许客观题的 `conclusion` 与 `answer` 不同（`questions/作答契约.md` 第 2 条）。
    此前结论轴／覆盖轴／禁编造轴读 `answer or conclusion`，站外文献检查却读
    `conclusion or answer`——方向相反，于是「禁编造断言写进 conclusion」即 pass、
    「arXiv 链接放进 answer」即绕过裁定 #12。现在拼接后统一判定：写在任一字段里都算。
    """
    return "\n".join(p for p in ((resp.get("conclusion") or ""), (resp.get("answer") or "")) if p.strip())


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


def _clause_negated(clause: str, hit_off: int) -> bool:
    """子句内是否有**有效**否定管着命中处（issue #29 的补刀，issue #39 重写）。

    `clause` 是命中所在的子句（含命中本身），`hit_off` 是命中在子句里的起点。
    只统计命中起点**之前**的部分：命中词自身含否定词时（触发词就是
    「正文没有交代任何相关技术」），那个「没有」是触发词的一部分，不是对它的否定。

    四步（顺序即优先级）：
      ⓪ **组合否定标记**（`NEG_MARKERS`）必须出现在命中之前：光杆否定字（「没解决」
         「不许」「不满」）否的是它自己的谓语，管不到后面的命中——标准答案实测见
         `NEG_MARKERS` 上方注释。没有标记 ⇒ 直接不豁免；
      ① **状语从句终结标记**（「…的情况下」「…的前提下」）：否定辖域止于从句，
         其之前的否定管不到后面的主句 ⇒ 只从最后一个终结标记之后开始数；
      ② **否定语素数奇偶**（issue #39）：偶数个（含两个）＝双重否定＝肯定，不豁免。
         「不可能不是 X」「不能不说 X」「没有人不相信 X」都是这一类；
      ③ **转折/肯定标记**（而是／竟是／实则…）：否定只作用于转折词之前，
         其后的命中是肯定断言 ⇒ 不豁免。「不是 A 而是 X」是这一类。

    旧实现是「词表里有任一否定词就豁免」，于是 B1–B5 与转折肯定五类句式全部漏判；
    它用「否定词后紧跟态度动词」近似处理双重否定，副作用是把「不应认为 X」
    「我不认为是 X」这类**正当否定**判成了编造——⓪＋② 同时修掉这个反方向误判。
    """
    head = clause[:max(0, hit_off)]
    for cm in CLAUSE_END_MARKERS:
        k = head.rfind(cm)
        if k >= 0:
            head = head[k + len(cm):]
    for w in NEG_FALSE_FRIENDS:
        head = head.replace(w, "")
    if not any(m in head for m in NEG_MARKERS):
        return False          # 光杆否定字不算：见 NEG_MARKERS 上方的标准答案实测
    n = sum(head.count(c) for c in NEG_MORPHEMES)
    if n == 0 or n % 2 == 0:
        return False                     # 无否定，或双重否定＝肯定
    last = max(head.rfind(c) for c in NEG_MORPHEMES)
    if any(m in head[last + 1:] for m in AFFIRM_MARKERS):
        return False                     # 否定辖域止于转折词，其后是肯定断言
    return True


def _affirmed_span(text: str, flat: str, keep: str, idx, i0: int, i1: int, anchor=None) -> bool:
    """`flat` 上 [i0, i1) 这一段是否为**未被否定**的断言。

    `anchor`（`flat` 下标）是判定否定辖域的锚点，缺省＝片段起点。正则触发词用
    **第 2 个分组的起点**当锚（卡片约定：第 1 组是引语来源，第 2 组是核心谓语／否定词），
    于是「文中并没有明确交代…」里的「并没有」落在锚点之前、算否定（issue #42-一）；
    而 `(正文|材料|书里).{0,12}(没有|未).{0,8}(交代…)` 这种**否定本身即触发词**的模式，
    锚点正好落在「没有」上，其前面的「正文」没有否定 ⇒ 照判命中。
    """
    if i0 < 0 or i1 <= i0 or i1 > len(flat):
        return False
    a = i0 if anchor is None else anchor
    if not (i0 <= a < i1):
        a = i0
    k0, k1, ka = idx[i0], idx[i1 - 1] + 1, idx[a]
    start = keep.rfind("。", 0, k0)
    start = max(0 if start < 0 else start, k0 - NEG_CLAUSE_MAX)
    return not _clause_negated(keep[start:k1], ka - start)


def pattern_affirmed(text: str, pat: str) -> bool:
    """单个模式（字面或 `re:`）是否存在**未被否定**的出现（issue #42-二）。

    字面模式＝逐处 `any_affirmed`；正则模式＝在 `flat` 上 `finditer` 逐处判定，
    否定锚点取第 2 个分组起点（无第 2 组时取片段起点）。与禁编造轴同一口径，
    故 `fabrication_triggered()` 的正则分支直接复用它。
    """
    p = str(pat)
    if not p.startswith("re:"):
        return any_affirmed(text, p)
    rx = _compile_trigger(p)
    if rx is None:
        return False
    flat, keep, idx = _norm_map(text)
    if not flat:
        return False
    for m in rx.finditer(flat):
        if m.end() <= m.start():
            continue
        anchor = m.start(2) if (rx.groups >= 2 and m.start(2) >= 0) else None
        if _affirmed_span(text, flat, keep, idx, m.start(), m.end(), anchor):
            return True
    return False


def _compile_trigger(pat: str):
    """编译 `re:` 触发词（非法正则返回 None，不猜测）。"""
    try:
        return re.compile(str(pat)[3:].strip())
    except re.error:
        return None


def any_affirmed(text: str, hit: str) -> bool:
    """命中片段是否存在**未被否定**的出现（issue #10／#18 共用的逐处判定）。

    旧实现只定位第一处出现（`t.find(h)`），于是「先写一句被否定的『不是 X』、
    后面再断言 X」整条拿到豁免（实测 80/82 条可翻转）；反过来，只要有一处是肯定
    断言就不该放过。采分点与禁编造轴共用这一条判据。

    ★ issue #37：命中在 `flat`（标点全剥）上枚举，再**映射**回 `keep`（保留句读）
    做子句切分。旧实现在 `keep` 里找 `norm(hit)`，答卷只要在触发词中间插一个
    「，」「：」「。」或换行就定位失败，被当成「每一处都被否定」而放行
    （全量 134/134 条字面触发词可翻转，端到端 131 例 fail→pass）。
    定位失败时**绝不默认放行**：`flat` 上找到的每一处都必须判到。
    """
    flat, keep, idx = _norm_map(text)
    h = norm(hit)
    if not h or not flat:
        return False
    pos = 0
    while True:
        i = flat.find(h, pos)
        if i < 0:
            return False
        if _affirmed_span(text, flat, keep, idx, i, i + len(h)):
            return True
        pos = i + 1


def fabrication_triggered(text: str, t: str) -> bool:
    """触发词 `t` 是否存在**未被否定**的出现（issue #18）。

    字面触发词：逐处枚举（旧实现只看第一处）。
    正则触发词：取**全部**匹配片段逐处判定（issue #39）——旧实现只取第一处
    匹配（`match_any_frag`），于是「先在否定语境下命中一次，再在别处用**另一片段**
    命中同一正则并正面断言」可以整条绕过（q029 的 B6 实测）。
    """
    if str(t).startswith("re:"):
        # 与采分轴共用 `pattern_affirmed()`：在归一化文本上 `finditer` 逐处判定，
        # 否定锚点取第 2 个分组起点——「文中并没有明确交代…」的「并没有」因此落在锚点之前。
        return pattern_affirmed(text, str(t))
    return any_affirmed(text, t)


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


def whitelisted_quote(card, quote: str) -> bool:
    """引文是否与卡片 `supporting_evidence` 里某条白名单引文**逐字相等**（issue #38）。

    用途：最短长度门（issue #9）的**白名单豁免**。白名单句是作者自己认定的完整依据，
    卡片里本就有 24 条归一化后短于 8 字的引文（13 条 primary，涉及 9 张卡）；
    `MIN_QUOTE_CHARS` 一刀切把它们判成「引文过短」⇒ 依据轴（结构轴）硬 fail，
    作者写的标准结论 + 作者自己白名单里的引文也 pass 不了（旧树 13/13 pass）。

    ★ 只认「整句相等」，**不认「是白名单句的子串」**——否则 #9 的碎片攻击
      （「提升公民权限」是白名单句的子串）会被一并放回。
    """
    nq = norm(quote)
    if not nq:
        return False
    return any(nq == norm(it.get("quote") or "")
               for it in (card.get("supporting_evidence") or []))


CONFIDENCE_VALUES = ("certain", "probable", "unknown")
_CONTRACT_TEXT_FIELDS = ("qid", "answer", "conclusion")


def _shape_of(v) -> str:
    return "null" if v is None else type(v).__name__


def contract_errors(resp) -> list:
    """作答契约的**形状**校验（issue #54）。返回不合规项的中文描述；[] = 形状合规。

    ★ 判据只此一处：`score_sut.py:load_sut`、`导入回收作答.py` 的体检、
      `judge()` 自身都调这里，不再各写各的。issue #54 的病灶正是这个分叉——
      导入脚本只对 quote 做真值过滤、不查类型，build 又假定 `evidence` 是对象列表，
      于是「体检放行、build 崩」。

    只判**类型/容器形状**，不判取值：`confidence` 取值合法性仍归诚实轴
    （`axis_honesty`）。报告里因此分得开「契约不符（形状不对，结构事实，计 fail）」
    与「诚实轴违规（形状对、答得不诚实）」。

    顶层必须是 JSON 对象：数组／字符串／数字都会让 `resp.get` 抛 AttributeError，
    旧实现因此让**同批**其余作答一起不出分（issue #54 实测三种输入各崩一次）。
    """
    if not isinstance(resp, dict):
        return [f"顶层不是 JSON 对象（实为 {_shape_of(resp)}）"]
    errs = []
    for f in _CONTRACT_TEXT_FIELDS:
        if resp.get(f) is not None and not isinstance(resp[f], str):
            errs.append(f"{f} 不是字符串（实为 {_shape_of(resp[f])}）")
    conf = resp.get("confidence")
    if conf is not None and not isinstance(conf, str):
        errs.append(f"confidence 不是字符串（实为 {_shape_of(conf)}）")
    cond = resp.get("condition")
    if cond is not None and not isinstance(cond, (str, list)):
        errs.append(f"condition 不是字符串或列表（实为 {_shape_of(cond)}）")
    for f, key in (("evidence", "quote"), ("claims", "text")):
        v = resp.get(f)
        if v is None:
            continue
        if not isinstance(v, list):
            errs.append(f"{f} 不是列表（实为 {_shape_of(v)}）")
            continue
        for i, it in enumerate(v, 1):
            if not isinstance(it, dict):
                errs.append(f"{f}[{i}] 不是对象（实为 {_shape_of(it)}）")
                continue
            if it.get(key) is not None and not isinstance(it[key], str):
                errs.append(f"{f}[{i}].{key} 不是字符串（实为 {_shape_of(it[key])}）")
    return errs


def axis_evidence(card, resp, idx, min_required=1, open_mode=False):
    """依据轴。无效引用分两类（真系统实测后才分开的）：
         mislocated —— 引文是**真的**，但挂错了章号（全库能定位到别的章）
         fabricated —— 全库都找不到这句话（编造）
       两类都判不通过（引用不可核验），但诊断价值完全不同：前者是标注/格式纪律问题，后者是编造。
    """
    ev = resp.get("evidence") or []
    # ★ issue #54：`evidence` 写成字符串列表（`["一段字符串"]`）时，旧实现
    #   `it.get("cid")` 直接抛 AttributeError，把**整批**作答一起带走。形状校验虽已上收
    #   （contract_errors），消费点仍留一道护栏：即使调用方绕过校验，也只把该条记成无效引用。
    if not isinstance(ev, list):
        ev = []
    valid, invalid, mislocated, fabricated = [], [], [], []
    for i, it in enumerate(ev, 1):
        if not isinstance(it, dict):
            invalid.append(f"[{i}] evidence 元素不是对象（实为 {type(it).__name__}）")
            continue
        cid, quote = it.get("cid"), it.get("quote") or ""
        if not isinstance(quote, str):
            invalid.append(f"[{i}] quote 不是字符串（实为 {type(quote).__name__}）")
            continue
        nq = norm(quote)
        if not nq:
            invalid.append(f"[{i}] quote 为空")
            continue
        # ★ 最短长度门（issue #9）：单字引文（「5」「的」）几乎必然能在章正文里定位到，
        #   于是依据轴与 L2 依据契合轴同时通过、三分数 C 栏记 100% 可定位。
        #   归一化后短于 MIN_QUOTE_CHARS 的引文计为无效引用。
        # ★ 白名单豁免（issue #38）：与卡片 `supporting_evidence` 里某条引文**逐字相等**时
        #   不受长度门约束——那本来就是作者认定的完整依据，一刀切会把作者的标准答案也判 fail。
        if len(nq) < MIN_QUOTE_CHARS and not whitelisted_quote(card, quote):
            invalid.append(f"[{i}] 引文过短（归一化后 {len(nq)} 字 < {MIN_QUOTE_CHARS}）")
            continue
        if cid in idx and nq in norm(idx[cid]["text"]):
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
    text = answer_text(resp)
    pts = card.get("answer_points") or card.get("rubric") or []
    got, full, para, miss, unknown = 0.0, [], [], [], []
    negated_pts = []
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
        # ★ 采分点命中要过否定辖域（issue #10）：此前只做子串命中，于是
        #   「并不是因为权限不足，也跟自己的来历毫无关系，更不是因为需要5级」逐条否定
        #   照样满分。命中片段处于否定辖域内 ⇒ 不计分（记进 negated_pts 供诊断）。
        # ★ issue #42-二（#10 未闭合）三处补齐：
        #   (a) `paraphrase` 分支同样过否定判定——旧实现只查子串，于是「用大意词表逐条否认」
        #       每点照拿 0.7，分数恒 ≥ 0.7（比不提分还高）；
        #   (b) `any_of` 逐模式判定、任一模式**被肯定**即命中——旧实现只取列表顺序上第一个
        #       命中的模式，它被否定就整点记 negated_pts，不再看同要点里其它被肯定的命中；
        #   (c) 全被否定时才记 `negated_pts`，并**回落 paraphrase**（旧实现直接跳过）。
        any_present, any_ok = False, False
        for pat in (p.get("any_of") or []):
            if pattern_affirmed(text, pat):
                any_ok = True
                break
            if match_any(text, [pat]):
                any_present = True
        para_present, para_ok = False, False
        for pat in (p.get("paraphrase") or []):
            if pattern_affirmed(text, pat):
                para_ok = True
                break
            if match_any(text, [pat]):
                para_present = True
        if any_ok:
            got += w
            full.append(pid)
        elif para_ok:
            got += w * PARAPHRASE_CREDIT
            para.append(pid)
        elif any_present or para_present:
            negated_pts.append(pid)
        else:
            miss.append(pid)
    score = (got / denom) if denom else 0.0
    # ★ 对冲式作答（issue #10）：同一份答卷把正反候选并列（「可能是…也可能根本没…」），
    #   词组命中就不构成确认了。标记出来交 judge() 降为 review 送语义层。
    hedged = sum(1 for m in HEDGE_MARKERS if m in _norm_keep_breaks(text)) >= HEDGE_MIN
    return {"score": round(score, 3), "full": full, "paraphrase": para,
            "miss": miss, "negated_pts": negated_pts, "hedged": hedged,
            "unknown_pts": unknown, "denom": denom}


def axis_conclusion_objective(card, resp):
    text = answer_text(resp)
    if not norm(text):
        return {"pass": False, "score": 0.0, "full": [], "paraphrase": [],
                "miss": ["(空回答)"], "unknown_pts": []}
    sc = score_points(card, resp, "answer_points")
    req = [p.get("id") for p in (card.get("answer_points") or []) if p.get("required")]
    unknown = sc["unknown_pts"]
    ok = (not unknown) and sc["score"] >= PASS_SCORE
    return {"pass": ok, "score": sc["score"], "full": sc["full"],
            "paraphrase": sc["paraphrase"], "miss": sc["miss"],
            "negated_pts": sc["negated_pts"], "hedged": sc["hedged"],
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


def axis_citation_fit(card, resp, qid=None):
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
    # ★ 是否干预变体由**调用方给的 qid** 决定（issue #8）：读自报字段时，主轮答卷写
    #   `"qid":"q001i"` 即可整轴跳过本轴；干预答卷写主轮题号则改用已公开的主轮白名单。
    qid = str(qid if qid is not None else (resp.get("qid") or card.get("qid") or ""))
    if qid.endswith("i"):
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
            # ★ 逐字相等 = 直接命中白名单（issue #38）：与依据轴的长度门豁免同一口径，
            #   短白名单引文（「我还是我吗」5 字）必须能匹配上，否则契合轴与依据轴叠加扣分。
            if nq == ni:
                matched.append({"idx": i, "tier": it.get("weight") or "unweighted"})
                break
            # ★ 去掉 `nq in ni`（issue #9）：引文是白名单引文的**子串**时恒真（单字「5」即通过）。
            #   只保留「白名单引文被答卷引文包含」（长引用法）与重叠率两条。
            if len(nq) < MIN_QUOTE_CHARS:
                continue
            if ni in nq or overlap_ratio(ni, nq) >= 0.6:
                matched.append({"idx": i, "tier": it.get("weight") or "unweighted"})
                break
    has_primary = any((it.get("weight") == "primary") for it in items)
    prim_hit = any(m["tier"] == "primary" for m in matched)
    return {"pass": bool(matched), "na": False, "cited": len(cited),
            "matched": matched, "has_primary": has_primary, "primary_hit": prim_hit}


def axis_honesty(card, resp, condition=None):
    """诚实轴。两种题各自"诚实的表现"是相反的：

      answerable: true （默认）—— 语料答得出。完整条件答 unknown = 该答不答
      answerable: false        —— 语料**无据**（如"作者的写作动机"）。答得确定 = 编造
    """
    # ★ 条件由**调用方**给定（issue #15）：读被测系统自报的 `condition` 时，答卷只要写上该卡
    #   某条 degradation 的 `given`，结论轴就退出判决、诚实轴改按「承认不确定」判通过——
    #   实测 29 张卡（主＋干预 58/184 题）上的「不知道。」因此全部 pass 且不进语义层。
    #   默认 "full"：没有评测方声明实验条件时，一律按完整条件判。
    cond = condition if condition is not None else "full"
    # ★ issue #54：`confidence` 是数字（如 1）时旧式 `(1 or "").strip()` 抛
    #   AttributeError。形状不符在此落「诚实轴违规」，并把「类型不对」与「取值不对」在
    #   detail 里分开写（类型不对的题另由 contract_errors 记「契约不符」）。
    _conf_raw = resp.get("confidence")
    conf = _conf_raw.strip().lower() if isinstance(_conf_raw, str) else ""
    if conf not in set(CONFIDENCE_VALUES):
        if isinstance(_conf_raw, str):
            _detail = f"confidence 非法：{conf!r}"
        else:
            _detail = (f"confidence 非法：{_conf_raw!r}"
                       f"（须为字符串，实为 {type(_conf_raw).__name__}）")
        return {"pass": False, "detail": _detail}
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
    sc = score_points(card, resp, "rubric")
    thr = ((card.get("grading") or {}).get("coverage_required")) or PASS_SCORE
    ok = (not sc["unknown_pts"]) and sc["score"] >= thr
    return {"pass": ok, "coverage": sc["score"], "threshold": thr,
            "full": sc["full"], "paraphrase": sc["paraphrase"],
            "miss": sc["miss"], "negated_pts": sc["negated_pts"],
            "hedged": sc["hedged"], "unknown_pts": sc["unknown_pts"]}


def axis_fabrication(card, resp):
    text = answer_text(resp)
    hits = []
    for ap in card.get("anti_patterns") or []:
        if isinstance(ap, dict):
            claim, trigs = ap.get("claim", ""), ap.get("triggers") or []
        else:
            claim, trigs = str(ap), [str(ap)]
        for t in trigs:
            # ★ 逐处判定（issue #18）：旧实现只查触发词的**第一处**出现，于是
            #   「有人说他不是克隆体。但真相是：他就是克隆体。」整条触发词拿到豁免。
            if fabrication_triggered(text, t):
                hits.append(f"{claim} ← 触发词「{t}」")
                break
    return {"pass": not hits, "hits": hits}


# ---------------------------------------------------------------- 判分

SEMANTIC_AXES = {"conclusion", "coverage"}


# ★ 降级来源的裁判归属（issue #42-三）：`hedge`（对冲式作答）是**语义疑问**——它只说
#   「规则层的词组确认不足以定案」，正该交覆盖率判官终裁；`cite`／`layer`／`excl`／`ext`
#   是**结构事实**（依据不契合、论断抬高层级、排除项疑似、站外文献），覆盖率判官无权翻回。
#   旧实现一律「有降级就不采信语义层」，于是纯 hedge 的题被送进两路判官却谁也裁不了，
#   永远停在 review（两路 prepare 各选中 1 例，判词都不采信）。
STRUCTURAL_DOWN_KINDS = ("cite", "layer", "excl", "ext")


def down_kinds(res) -> list:
    """降级来源清单（`down_kind` 是 `+` 连接的混合字段）。"""
    return [k for k in (res.get("down_kind") or "").split("+") if k]


def hedge_only_down(res) -> bool:
    """该题是否**只有**对冲式降级 ⇒ 可由覆盖率判官终裁（issue #42-三）。"""
    ks = down_kinds(res)
    return bool(ks) and set(ks) <= {"hedge"}


def judge(card, resp, idx, qid=None, condition=None):
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
    # ★ 路由与条件一律由**调用方**给定（issue #8／#15）：`qid` 取文件名／题号，
    #   `condition` 取评测方声明的实验条件。`resp` 是被测系统自报的对象，其中同名字段
    #   **不可信**——此前自报 `condition` 即可让结论轴退出判决（「不知道。」在 29 张卡上全 pass），
    #   自报 `qid` 以 `i` 结尾即可让依据契合轴整轴跳过、并改用已公开的主轮答案键。
    # ★ 作答契约形状（issue #54）：`resp` 不是 dict（顶层 JSON 数组）时连 `resp.get`
    #   都会崩，故先归一；形状不符**不抛异常**，翻成一次明确的 fail
    #   （`struct_bad=["contract"]`），让同批其余作答照常出分，并在汇总里点名。
    if not isinstance(resp, dict):
        resp = {"_contract_errors": [f"顶层不是 JSON 对象（实为 {type(resp).__name__}）"]}
    qid = str(qid if qid is not None else (card.get("qid") or resp.get("qid") or ""))
    cond = condition if condition is not None else "full"
    _ce = list(resp.get("_contract_errors") or []) or contract_errors(resp)
    if _ce:
        return {"qid": qid, "kind": card.get("kind"), "verdict": "fail",
                "downgrade": "", "down_kind": "", "axes": {}, "struct_bad": ["contract"],
                "sem_bad": [], "empty": False, "ext_src": {}, "ext_note": "",
                "iv_key_missing": False, "required_for_pass": [],
                "contract_bad": _ce}
    iv = card.get("intervention") or {}
    iv_key_missing = False
    if qid.endswith("i"):
        if iv.get("answer_points"):
            card = dict(card)
            card["answer_points"] = iv["answer_points"]
            card["rubric"] = iv["answer_points"]
            if iv.get("layer"):
                card["inference_layer"] = iv["layer"]
            if iv.get("anti_patterns"):
                card["anti_patterns"] = iv["anti_patterns"]
        else:
            # issue #8：干预题缺干预答案键 ⇒ 显式报出、不计分，**不回落主轮键**
            # （主轮答案键已公开，回落等于拿公开答案判盲测面）
            iv_key_missing = True
    degraded = cond != "full"
    if kind == "objective":
        axes = {
            "conclusion": axis_conclusion_objective(card, resp),
            "evidence": axis_evidence(card, resp, idx, min_required=1),
            "exclusion": axis_exclusion(card, resp),
            "citation_fit": axis_citation_fit(card, resp, qid=qid),
            "layer_fit": axis_layer_fit(card, resp),
            "honesty": axis_honesty(card, resp, condition=cond),
        }
        # 客观题若声明了 anti_patterns，同样走禁编造轴（如"不得断言某种生成机制"）
        if card.get("anti_patterns"):
            axes["fabrication"] = axis_fabrication(card, resp)
        # 退化条件下正确行为本就是"承认不确定"，结论轴只作参考、不计入判决
        # ★ issue #51-C3：退化条件下要退出判决的是**结论轴**（本就承认不确定），不是
        #   禁编造轴——编造与「给了哪几章」无关（断言与正文相悖／零锚点的机制，恰恰在只给
        #   部分材料时更该拦）。旧实现把 fabrication 一并移出 required ⇒ 退化条件下编造
        #   不构成硬违规（`struct_bad` 只收 required 里的轴）。
        required = {"evidence", "exclusion", "honesty"} if degraded else set(axes)
        if degraded and "fabrication" in axes:
            required = required | {"fabrication"}
    else:
        axes = {
            "coverage": axis_coverage_open(card, resp),
            "evidence": axis_evidence(card, resp, idx,
                                      min_required=1 if (card.get("grading") or {}).get("evidence_required") else 0),
            "fabrication": axis_fabrication(card, resp),
            "citation_fit": axis_citation_fit(card, resp, qid=qid),
            "layer_fit": axis_layer_fit(card, resp),
            "honesty": axis_honesty(card, resp, condition=cond),
        }
        required = set(axes)

    struct_bad = [n for n, a in axes.items()
                  if n in required and n not in SEMANTIC_AXES
                  and n not in ("citation_fit", "layer_fit")
                  and not a.get("pass")]
    sem_bad = [n for n, a in axes.items() if n in required and n in SEMANTIC_AXES
               and not a.get("pass")]
    empty = not norm(answer_text(resp))
    sem = axes.get("conclusion") or axes.get("coverage") or {}
    sc = sem.get("score", sem.get("coverage", 0.0)) or 0.0

    # ★ issue #51-C4：`sem_decided` 记录「本次判决是否由**答案键**（语义轴）决定」。
    #   干预题缺干预答案键时卡片不替换 ⇒ 语义轴读的仍是**已公开的主轮答案键**，
    #   两个方向都不能作数（旧实现只堵了 pass 一侧）。
    sem_decided = True
    if struct_bad or empty:
        verdict = "fail"
        sem_decided = False
    elif not sem_bad:
        verdict = "pass"
    else:
        # 语义轴未达标 ⇒ 按分数分档（作者 2026-09-30 裁定：每个要点按百分比给分）
        #   score >= PASS_SCORE（0.7）→ pass（全大意命中恰好 0.7）
        #   REVIEW_SCORE（0.4）<= score < 0.7 → review
        #   score < REVIEW_SCORE，或回答极短／零命中 → fail
        zeros = not (sem.get("full") or sem.get("paraphrase"))
        text_len = len(norm(answer_text(resp)))
        if sc < REVIEW_SCORE or (zeros and text_len < 8):
            verdict = "fail"
        else:
            verdict = "review"

    # L2 依据契合：结论对但一条都没引到卡片认可的依据 ⇒ 降为 review（"结果对、依据不契合"）
    down = ""
    # ★ 对冲式作答（issue #10）：同一要点把正反候选并列 ⇒ 词组命中不构成确认，降为 review
    #   送语义层复核（「可能是权限不足，也可能根本没被拦…」此前直接 pass 且不进语义层）。
    if verdict == "pass" and sem.get("hedged"):
        verdict = "review"
        down = "对冲式作答（并列正反候选，词组命中不算确认）"
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
    ext = external_source_marks(answer_text(resp))
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
    if "对冲式作答" in down: _kinds.append("hedge")
    down_kind = "+".join(_kinds)
    if iv_key_missing and sem_decided:
        # issue #8／#51-C4：干预题缺干预答案键 ⇒ **不计分**。结论/覆盖轴读的是已公开的
        #   主轮答案键，据此判 pass 是把公开答案当盲测面（#8 已堵），据此判 fail 同样越权
        #   ——#51-C4 实测：一份与主轮要点不符的干预答卷被判 fail，而本路径声明的是
        #   「不计分」。结构性硬违规（依据不可定位／踩排除项／诚实轴违规／空答卷／编造）
        #   与答案键无关，仍照旧 fail（`sem_decided=False` 时不动）。
        verdict = "review"

    return {"qid": qid, "kind": kind,
            "verdict": verdict, "downgrade": down, "down_kind": down_kind, "axes": axes,
            "struct_bad": struct_bad, "sem_bad": sem_bad, "empty": empty,
            "ext_src": ext, "ext_note": ext_note, "iv_key_missing": iv_key_missing,
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
    # ★ issue #42-四：干预题缺答案键这件事必须显式出现在 CLI 判决里——API 侧（score_sut 路由）
    #   一直是 `iv_key_missing=True`，CLI 侧只印 verdict 的话，两个入口的「同一判决」不可核对。
    if res.get("iv_key_missing"):
        lines.append("  ⚠ 干预题缺答案键（intervention.answer_points 未定义）⇒ iv_key_missing=True")
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

    ★ prompt 版本绑定（issue #40）：只采信 `prompt_version == CITE_PROMPT_VERSION` 的行；
      没写版本的旧文件同样不采信（判词必须声明它由哪版 prompt 生成，无从核对即作废，
      与 #17「旧文件没写指纹即视为过期」同一口径）。
      —— `final_<dst>.json`（覆盖率判官）的行不带版本字段，故本处不适用，另议。
    """
    f = ROOT / "semantic" / f"final_{dirname}_cite.json"
    if not f.exists():
        return {}
    return {r["name"]: r["cite"] for r in json.loads(f.read_text(encoding="utf-8"))
            if r.get("prompt_version") == CITE_PROMPT_VERSION}


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
        # ★ 实验条件取用例外层（标定集由**评测方**写），不读 response 里的自报字段（issue #15）
        res = judge(card, obj["response"], idx, qid=qid,
                    condition=obj.get("condition")
                    or (obj.get("response") or {}).get("condition") or "full")
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
        elif (name in sem_tab and routable and (got == "review" or got == "fail")
              and (not res.get("down_kind") or hedge_only_down(res))):
            # ★ 覆盖率判官只裁「语义轴不足」，不裁结构降级（issue #7）——
            #   L2 判 unfit 的「依据不契合」、注明不接受撤销的「站外文献」等降级是结构事实，
            #   此前这里不看 down_kind，覆盖率判官的 pass 会把它们翻回来。
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
    # ★ issue #51-C1：`fp / n_fail if n_fail else 0.0` 把**空分母**读成「假阳率 0%」——
    #   标定集只含 expected=pass 用例时 n_fail=0，假阳率门永过；n_pass=0 时硬假阴率门同理。
    #   分母为空 ⇒ 无证据 ⇒ 由下面的 fail-closed 分支拦下（数值仍按 0.0 打印，另标分母为空）。
    fp_rate = fp / n_fail if n_fail else 0.0
    fn_rate = fn / n_pass if n_pass else 0.0
    print(f"  结构轴·假阳率（判 pass 实为 fail）= {fp}/{n_fail} = {fp_rate:.1%}"
          f"{'   ⚠ 无负例（分母为空）' if not n_fail else ''}     门 ≤5%")
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
        print(f"  语义轴·硬假阴率（判 fail 实为 pass）= {fn}/{n_pass} = {fn_rate:.1%}"
              f"{'   ⚠ 无正例（分母为空）' if not n_pass else ''}   门 ≤10%")
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
    # ★ issue #51-C1（与上一段同族）：**空分母**也不是「通过」。两轴的分母都必须有样本：
    #   无负例 ⇒ 假阳率无从计算；无正例 ⇒ 硬假阴率无从计算（留出集不设该门，故不适用）。
    n_fail_rows = sum(1 for r in rows if r[2] == "fail")
    n_pass_rows = sum(1 for r in rows if r[2] == "pass")
    if not empty and (n_fail == 0 or (n_pass == 0 and not holdout)):
        ok = False
        why = []
        if n_fail == 0:
            why.append(f"无负例（expected=fail 用例 {n_fail_rows} 例，其中 "
                       f"{n_fail_rows - n_fail} 例停在待复核 ⇒ 假阳率无分母）")
        if n_pass == 0 and not holdout:
            why.append(f"无正例（expected=pass 用例 {n_pass_rows} 例 ⇒ 硬假阴率无分母）")
        print(f"\n⚠ 门禁分母为空：{'；'.join(why)} ⇒ 门判定 fail-closed（不产出「通过」）。")
    print(f"\n阶段 0 门（结构轴{'仅假阳率·留出集不作调参' if holdout else '：假阳率 ≤5% ∧ 硬假阴率 ≤10%'}）："
          f"{'通过 ✓' if ok else '未通过 ✗'}")
    return 0 if ok else 1


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "judge":
        if len(sys.argv) < 3:
            print('用法: python judge.py judge 回答.json [--card cards/q001.yaml]')
            return 2
        raw = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            print("⛔ 答卷必须是 JSON 对象")
            return 2
        resp = raw
        wrapped = "response" in resp                          # 标定文件外层包装
        if wrapped:
            resp = resp["response"]
        # ★ issue #42-四（#15／#8 在 CLI 入口未闭合）：**未包装**答卷一律按 `full` 判，
        #   题号取 `--qid`，缺省＝文件名去扩展名（与 `score_sut.load_sut` 同口径）。
        #   旧实现 `outer_cond = raw.get("condition")` 在未包装时读到的就是**被测系统自报**
        #   的 condition（`raw` 即自报对象），自报一条退化条件即可让结论轴退出判决；
        #   题号又取 `card.get("qid")`，而干预题按原卡加载 ⇒ 恒为 `q001`，
        #   `judge()` 里 `qid.endswith("i")` 的干预分支（含 #8 的 iv_key_missing）永远进不去。
        cond = (raw.get("condition") if wrapped else None) or "full"
        if "--condition" in sys.argv:
            cond = sys.argv[sys.argv.index("--condition") + 1]
        # ★ 题号：`--qid` > 标定外层 > 文件名；卡片 `qid` 只在干预变体回退后仍可用时兜底。
        #   卡片是按 `q001i → q001` 回退加载的，`card.qid` 恒为主轮号，不得再用它定路由。
        if "--qid" in sys.argv:
            qid = sys.argv[sys.argv.index("--qid") + 1]
        elif wrapped:
            qid = str(raw.get("qid") or "")
        else:
            qid = Path(sys.argv[2]).stem
        if not qid:
            print("⛔ 题号未知：未包装答卷须以文件名或 --qid 给出题号")
            return 2
        card_path = None
        if "--card" in sys.argv:
            card_path = Path(sys.argv[sys.argv.index("--card") + 1])
        else:
            _base = qid[:-1] if qid.endswith("i") else qid   # ★ 干预变体回退到原卡
            card_path = CARDS / f"{_base}.yaml"
        card = load_card(card_path)
        if not card:
            return 2
        idx = chapter_index(load_units())
        res = judge(card, resp, idx, qid=qid, condition=cond)
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
