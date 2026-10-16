# -*- coding: utf-8 -*-
"""状态链召回探针 · 判分器（纯机械 · 零 LLM）

读 `out/keys.json` 与各臂答卷（`runs/chain_<arm>/sut/out/<qid>.json`），逐题机械比对
`value` / `state` / `at_seq` / `chain`；`basis` 走「逐字可回源」——去空白与非词字符后
包含，**且必须落在该题真正检索到的材料里**、`file`/`line` 指向返回的片段（口径见
`verbatim_ok`）。

产出 `out/readings.json`：每臂一行，字段＝
  arm, present, history, chain, chain_row_recall, stale, future, subject_confusion,
  four_state, reason, verbatim, n, n_expected, sampled, complete, counts,
  bucket_main, bucket_main_n
（`readings_excluded.json` 收「指纹不符 / --limit 截断 / 答卷缺题」的臂，不当作整臂读数发布。）

指标（全部机械，口径见函数 docstring）：
  现值正确率 / 历史召回率 / 变更链完整率 / 变更链行召回 / 滞后混淆率 / 超前混淆率 /
  主体混淆率 / 状态归属四态正确率 / 缘由随账率 / 依据轴逐字可回源率。
可推题（reconstructible=True）与**同名异体歧义题**（ambiguous=True，issue #44-一）不进主读数；
历史叙述豁免须**自报状态与答案键一致**才生效。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hmb_paths                                            # noqa: E402

# ★ 答卷根目录与运行器**共用同一份解析**（issue #41）：
#   此前这里写死 `membench/dist/记忆系统对比_v1.0/runs`（仓外路径），而发布版 harness 把
#   答卷写进 `chain/tools/out/runs`——第三方照 README §8 跑完 bm25 全链，642 份答卷落盘、
#   判分输出 `[]`、calibrate 两臂 n=0，且 rc=0（静默失败）。
RUNS = hmb_paths.runs_dir()

# 主读数（值域自洽与复算一致性都按这一组比）
# ★ 四态分项（issue #21）：预注册要求「active/retired/unresolved/absent 四项分别报」，
#   合并数被多数类（active 103/197）主导——一个只会答 active 的常数臂能拿到 0.523，
#   高于版本盲对照 0.508，而四态设计的目的恰是区分「退役」与「不存在」（失效≠证伪）。
#   合并数保留（附多数类基线），但判据与报告以分项为准。
METRIC_FIELDS = ('present', 'history', 'chain', 'chain_row_recall', 'chain_precision',
                 'stale', 'future',
                 'subject_confusion', 'four_state', 'reason', 'verbatim',
                 'four_state_active', 'four_state_retired',
                 'four_state_unresolved', 'four_state_absent',
                 'timepoint', 'timepoint_early', 'timepoint_late')

FOUR_STATES = ('active', 'retired', 'unresolved', 'absent')

# 校准零号的两个**对照臂**（不是被测系统）；③ 只在被测系统臂上评。
CONTROL_ARMS = ('versionblind', 'closed')

# ★ 预注册的**破坏臂**（README §6 第 2 条「破坏方向」）：乙/丙/丁。
#   issue #26：运行器里根本没有这三条臂，判分器把预注册的第 2 条换成了「读数自洽」，
#   于是不跑任何破坏臂也宣布「四条全过」。现在 ② 是一等判据：没有破坏臂读数即「未评」，
#   passed 不得为 True、gate_stage 标为 no-damage-arms。
DAMAGE_ARMS = ('damage_bad_write', 'damage_bad_retrieval', 'damage_bad_present')
# 预注册映射表：每条破坏臂**必须**显著下降的指标（设计稿 §「坏写入/坏检索/坏呈现」）
DAMAGE_MAP = {
    'damage_bad_write': ('history', 'chain'),      # 乙 坏写入：丢 30% 事件 ⇒ 历史/变更链塌
    'damage_bad_retrieval': ('present', 'verbatim'),   # 丙 坏检索：打乱+截断 ⇒ 现值/依据塌
    'damage_bad_present': ('verbatim',),           # 丁 坏呈现：剥来源字段 ⇒ 依据轴塌
}
MIN_DAMAGE_DROP = 0.10   # 破坏臂相对正常臂在映射指标上至少下降这么多
MIN_SEPARATION = 0.05    # 三条破坏臂两两可分的下限（指纹向量的 L∞ 距离）


def is_damage_arm(arm: str) -> bool:
    return arm in DAMAGE_ARMS or arm.startswith('damage_')
SUT_ORDER = ('lingshu', 'mem0', 'memos', 'hindsight', 'openviking', 'bm25')

# 最小样本量守卫：不足即判据不过（防「n=1 也算过」）
MIN_ARM_N = 100          # 对照臂至少要答这么多非可推题
# ★ issue #44-四：闭卷门 ② 的**逐题**判据（issue #30 的「逐题剔除」落地）。旧实现只比三个
#   聚合率（现值/历史/变更链各 ≤ 0.2）——闭卷臂答对 51 道题（各率 18%）时 ② 照样判过，
#   而那 51 道可猜题也照旧留在被测臂主读数里。现在逐题清单必须 ≤ 5%，且清单里的题
#   从被测臂主读数中剔除（分母随之下调）。
CLOSED_MAX_HIT = 0.05    # 闭卷臂逐题命中率上限
MIN_BUCKET_N = 5         # 链长桶至少这么多题才允许进单调性判据
MIN_PRESENT_N = 20       # 版本盲臂现值问（有取值）的分母下限
# ★ 效度门 ③ 的**绝对水平下界**（2026-10-10 复核整改）：只要求「非增且非全等」会被
#   恒输出全局最高频答案值的**常数猜测器**蒙过——语料结构本身随链长单调（短链取值少、
#   瞎猜命中率高），实测常数猜测器桶率 short 0.0714 > mid 0.0098 > long 0.0 ⇒ 旧判据
#   c3=True。故 ③ 还须要求被测臂**短链桶的绝对正确率**既达有意义的下界，又显著高于
#   结构基线（语料侧瞎猜期望）。
MIN_SUT_SHORT = 0.30     # 被测臂短链桶主指标绝对下界
MIN_SUT_MARGIN = 0.10    # 短链桶须比结构基线（_structural_baseline 的 short）高出的幅度
# ★ 效度门 ③ 的**方向判据**（issue #20）：旧实现每档允许回升固定 0.05、且「非全等」的
#   容差只有 1e-6 ⇒ 短/中/长 0.859→0.902→0.931 逐桶**上升**的臂四条门全过。
#   现在：相邻档的回升不得超过**抽样噪声**（按各桶样本量算 95% 置信限），
#   且首尾必须真实下降至少 MIN_DROP——只拦「没有一步上升超过固定值」不再算退化。
MIN_DROP = 0.05          # 首尾桶之间必须真实下降的幅度（点估计）
Z95 = 1.96               # 95% 置信限（双侧）
# ★ issue #44-三：**首尾差 ≥ 0.05 也算不上退化**——它是点估计，与样本量无关。
#   实测：真值三桶同为 0.80 的平坦臂，400 次二项抽样里有 24.2% 首尾差 ≥ 0.05 而判过；
#   U 形臂（0.80→0.60→0.75）首尾差恰好 0.05 也被判过。故 ③ 改为**单侧两比例检验**：
#   · 首尾：H1 短链 > 长链，z ≥ 1.645（α=0.05）**且**点估计下降 ≥ MIN_DROP − 1e-9；
#   · 相邻：回升方向的单侧 z < 1.645 **且**点估计回升 ≤ MIN_RISE。
MIN_DROP_Z = 1.645       # 首尾下降的单侧两比例 z 阈值（α=0.05）
MIN_RISE = 0.05          # 相邻档点估计允许的回升上限
DROP_EPS = 1e-9          # 点估计比较容差（0.04999999999999993 是浮点残差，不是「差一点」）

_WORD = re.compile(r'[\W_]+', re.UNICODE)


def norm(s) -> str:
    return _WORD.sub('', '' if s is None else str(s)).lower()


def eq(a, b) -> bool:
    return norm(a) == norm(b)


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default


def keys_fp(keys=None) -> str:
    """当前答案键的指纹（qid/问型/答案四字段），写入 manifest 供判分器校验答卷是否同源。"""
    if keys is None:
        keys = _load(OUT / 'keys.json', [])
    h = hashlib.sha256()
    for k in keys:
        h.update(json.dumps([k['qid'], k['type'], k['answer'].get('value'),
                             k['answer'].get('state'), k['answer'].get('at_seq')],
                            ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return h.hexdigest()[:16]


def _excluded(k: dict) -> bool:
    """该题是否**不进主读数**：可推题（reconstructible）＋同名异体歧义题（ambiguous）。

    ★ issue #44-一：同名异体档的影子链与主链**逐字同名同槽位**（#31 的修复），语料里没有
      任何文本依据能把两者分开，而答案键只按主链取值 ⇒ 把同名同槽位的句子按序号读成一条链
      （语料唯一支持的读法）在这批题上与答案键不一致。synth.py 逐题机械算出 `ambiguous`，
      这里同口径剔除——旧实现只看 `reconstructible`，那 41 道题留在主读数里，忠实读者被判错、
      还被记成「主体混淆」。
    """
    return bool(k.get('reconstructible')) or bool(k.get('ambiguous'))


def _ans_of(arm: str, qid: str):
    p = RUNS / f'chain_{arm}' / 'sut' / 'out' / f'{qid}.json'
    if not p.exists():
        return None
    return _load(p, None)


def _manifest(arm: str) -> dict:
    return _load(RUNS / f'chain_{arm}' / 'manifest.json', {}) or {}


def _material_of(arm: str, qid: str):
    """该题实际检索到的材料：返回 (归一化拼接文本, cid 集合, seq 集合)；无检索件返回 None。

    ★ issue #43-一C：`material` 是**给被测系统看的**那一份（丙/丁 破坏臂会打乱、截断、剥 cid），
      `material_full` 是同一批片段**未经破坏**的样子（含 cid/score）。依据轴要问的是
      「答卷引的片段是否真在它拿到的那批里、且能回源到 cid」——故文本取自 `material`
      （没看到的片段不能引），cid/seq 取自 `material_full` 里文本确实出现在 `material` 中的块。
      旧实现直接读被剥过的 `material` ⇒ cids/seqs 皆空 ⇒ `verbatim_ok` 对**任何**答卷都
      返回 False，丁量到的是「判分器丢了来源」，与答卷无关。
    """
    o = _load(RUNS / f'chain_{arm}' / 'retrieval' / f'{qid}.json', None)
    if not isinstance(o, dict):
        return None
    mat = o.get('material') or []
    txt = ''.join((m.get('text') or '') for m in mat if isinstance(m, dict))
    src = o.get('material_full')
    src = src if isinstance(src, list) else mat
    shown = {(m.get('text') or '') for m in mat
             if isinstance(m, dict) and (m.get('text') or '')}
    cids, seqs = set(), set()
    for m in src:
        if not isinstance(m, dict) or m.get('cid') is None:
            continue
        if src is not mat and (m.get('text') or '') not in shown:
            continue
        cid = str(m['cid'])
        cids.add(cid)
        if '#' in cid:
            tail = cid.rsplit('#', 1)[1]
            if tail.isdigit():
                seqs.add(int(tail))
    return norm(txt), cids, seqs


def _chain_items(a) -> list[dict]:
    out = []
    for it in (a.get('chain') or []):
        if isinstance(it, dict):
            out.append(it)
    return out


def _value_of(a) -> str:
    v = a.get('value')
    return '' if v is None else str(v)


# ---------------- 单题机械判据 ----------------
def value_correct(a: dict, key: dict) -> bool:
    """值判定：命中主答案值**或**任一「可接受替代值」即算对。

    `answer.accept`（可选）承载**语料本身并列**的取值——目前只有「时点」问落在
    unresolved 事件时（语料写「出现两种并存的取值：X 与 Y」，X 记作 to、Y 记作 alt，
    谁当 to 只是句面词序，不是可判定的正确性差异）。见 synth.build_keys 的 accept 注入。
    """
    if eq(a.get('value'), key['answer']['value']):
        return True
    for x in (key['answer'].get('accept') or []):
        if eq(a.get('value'), x):
            return True
    return False


def null_answer_ok(a: dict, key: dict) -> bool:
    """答案为 null（该主体**已退役／从未存在**）的题怎么判（issue #28）。

    旧实现把这类题从现值/历史/滞后/超前四个分母里**一律剔除**——于是「退役后照报旧值」
    的臂与满分臂逐位相同，滞后混淆率看不见「主体已退役」这一类。现在：
    答 null **且状态判对**才算对；报出任何取值都算错（现值/历史各计一次错）。
    """
    return eq(a.get('value'), None) and eq(a.get('state'), key['answer'].get('state'))


def value_ok(a: dict, key: dict) -> bool:
    """现值/历史的单题判对：答案为 null 时走 `null_answer_ok`，否则走 `value_correct`。"""
    if key['answer'].get('value') is None:
        return null_answer_ok(a, key)
    return value_correct(a, key)


def at_seq_ok(a: dict, key: dict) -> bool:
    """时点定位判对（issue #43-三）：答卷的 `at_seq` 须等于答案键的 `at_seq`。

    答案键的 63 道时点题**全部**有非空 `at_seq`（25 道有值、38 道退役点），故判据
    不含「键为空则放行」的兜底分支——那会给「一律答 null」的臂白送分。
    """
    want = key['answer'].get('at_seq')
    got = a.get('at_seq')
    if want is None:
        return got is None or got == ''
    try:
        return int(got) == int(want)
    except (TypeError, ValueError):
        return False


def want_changes(key: dict) -> list[dict]:
    """题面要的「每一次变更前后的值」＝**前后值都有值**的转移。

    粒度预注册（design §5）：一次修改＝一次「值发生变化」的写入事件。
    首次确立（from=null）、退役后重新确立（from=null）都不是「变更」；撤回（to=null）
    的语料句只写「被撤销，此后不再保留取值」、**不携带前值**，要求答卷逐字对上等于
    要求它从别处反推——故一律不进 want。★ 未决/裁定（unresolve/resolve）同样不进：
    语料把它们叙述成「出现两种并存的取值…尚未裁定」与「争议就此裁定为 X」，都不写前值，
    一个忠实读者无从给出 from（见 synth.change_view 的同口径排除）。生成器
    `answer.change_chain` 已按此过滤，本函数只做兜底过滤。
    """
    ch = key['answer'].get('change_chain')
    if ch is None:                                   # 兼容旧键：就地过滤（旧键无 kev，
        ch = [r for r in (key['answer'].get('chain') or [])   # 故只能按 from/to 过滤）
              if r.get('from') is not None and r.get('to') is not None]
    return [r for r in ch if r.get('from') is not None and r.get('to') is not None]


def chain_rows_hit(a: dict, key: dict) -> tuple[int, int]:
    """返回 (答对的变更行数, 应列的变更行数)——供「链条无缺环」之外的**部分召回**诊断。

    `chain` 是全或无（预注册口径），单看它分不清「一行没对」与「只差两行」；
    这条给出连续读数，避免变更链又变成无法区分系统的地板指标。
    """
    want = want_changes(key)
    if not want:
        return 0, 0
    got = _chain_items(a)
    hit = 0
    for w in want:
        for g in got:
            if (str(g.get('seq')) == str(w['seq']) and eq(g.get('from'), w.get('from'))
                    and eq(g.get('to'), w.get('to'))):
                hit += 1
                break
    return hit, len(want)


def _chain_seq_scope(key: dict) -> set:
    """**本链**的合法序号集合＝`answer.chain` 里的事件序号。

    已核对：56 道变更题上，`answer.chain` 的序号集与 synth_log 中同
    (doc, subject, slot) 链的 seqs **完全一致**（含 create／retire／restore 行）。
    """
    return {str(r.get('seq')) for r in (key['answer'].get('chain') or [])
            if isinstance(r, dict)}


def _chain_row_scope(key: dict) -> set:
    """本链的合法**行**集合＝`(seq, from, to)` 三元组（issue #43-四）。

    只按 `seq` 判「是否属于本链」不够：同一 `seq` 下把**所有** (from, to) 组合枚举一遍，
    每一行的 seq 都在本链里 ⇒ 旧口径一行都不算多列。实测（审计脚本 p1_2_4）：每题中位列
    **6048** 行（应列 5），`chain`／`row_recall`／`precision` 却全是 1.0，与 oracle 相同。
    """
    out = set()
    for r in (key['answer'].get('chain') or []):
        if isinstance(r, dict):
            out.add((str(r.get('seq')), norm(r.get('from')), norm(r.get('to'))))
    return out


def chain_extra_rows(a: dict, key: dict) -> int:
    """答卷里**不属于本链**的变更行数（issue #24／#43-四）。

    `seq` 在文档内唯一，故「别的主体／别的槽位」的行永远撞不上本题的 `want`——
    旧实现只查召回、不罚多列，于是一个不认主体、不认槽位的答卷把整篇文档所有
    「值→值」行一股脑列上也能判「链完整」（实测中位 115 行 vs 应列 5.5 行）。

    ★ issue #43-四：多列判据从「seq 属不属于本链」收紧到「(seq, from, to) 是不是本链的行」——
      同 `seq` 下枚举全部 (from, to) 组合属于多列（旧口径下每一行的 seq 都合法 ⇒ 一行都不罚）。
    """
    allowed = _chain_row_scope(key)
    return sum(1 for g in _chain_items(a)
               if (str(g.get('seq')), norm(g.get('from')), norm(g.get('to'))) not in allowed)


def chain_complete(a: dict, key: dict) -> bool:
    """变更链完整率：want 的每一次「值→值」变更都能在答卷 chain 里找到同 seq 同前后值，
    **且答卷没有多列不属于本链的行**。

    答卷多列**本链**的行（create / retire / restore）不扣分——多列不是缺环
    （这正是原注释的本意，旧实现却对任意多列行都不扣分，见 issue #24）。
    """
    want = want_changes(key)
    if not want:
        return False
    if chain_extra_rows(a, key) > 0:
        return False
    got = _chain_items(a)
    for w in want:
        hit = False
        for g in got:
            if (str(g.get('seq')) == str(w['seq']) and eq(g.get('from'), w.get('from'))
                    and eq(g.get('to'), w.get('to'))):
                hit = True
                break
        if not hit:
            return False
    return True


def _exempt(a: dict, key: dict) -> bool:
    """历史叙述豁免：只有**自报状态与答案键在该时点的状态一致**时才成立。

    旧实现只看答卷自己填的 state 是不是 retired/unresolved，不交叉校验——把每题都填
    unresolved 就能在答错值的同时把滞后/超前混淆清零。现在必须「状态也判对」才豁免。
    """
    st = str(a.get('state') or '')
    return st in ('retired', 'unresolved') and eq(st, key['answer'].get('state'))


def stale_confused(a: dict, key: dict) -> bool:
    """滞后混淆：现值问里把**已退役的旧值**当作现行值（豁免见 `_exempt`）。"""
    v = norm(a.get('value'))
    if not v:
        return False
    cur = norm(key['answer']['value'])
    if v == cur:
        return False
    olds = {norm(e['to']) for e in key['answer']['chain'][:-1] if e.get('to')}
    if v not in olds:
        return False
    return not _exempt(a, key)


def future_confused(a: dict, key: dict) -> bool:
    """超前混淆：历史/时点问里用了**取样点之后才生效**的值（豁免见 `_exempt`）。

    ★ 2026-10-10 复核整改（甲-4）：旧实现只看「某值是否出现在 seq>T 的事件 to 里」，
    **不检查它是否也出现在 seq≤T**。语料「同值异时」档故意让链内某值复现
    （synth.make_values 的 vals[j]=vals[i]），于是「当时确实成立过的」值会被记成超前混淆，
    超前混淆率按构造虚高。现在要求该值**只在 T 之后出现过**（T 之前从未出现）才算超前。
    另外，若该值本就是答案键列出的**可接受替代值**（accept，见 value_correct），也不算。
    """
    v = norm(a.get('value'))
    if not v or v == norm(key['answer']['value']):
        return False
    if v in {norm(x) for x in (key['answer'].get('accept') or [])}:
        return False
    T = key['sample_at_seq']
    chain = key['answer']['chain']
    later = {norm(e['to']) for e in chain if e.get('to') and e['seq'] > T}
    if v not in later:
        return False
    earlier = {norm(e['to']) for e in chain if e.get('to') and e['seq'] <= T}
    if v in earlier:                                  # 该值在取样点前已成立过 ⇒ 非超前
        return False
    return not _exempt(a, key)


def verbatim_ok(a: dict, mat) -> bool:
    """依据轴：quote 必须是**该题检索到的材料**里的逐字原文，且 file/line 指向返回的片段。

    只查「是全文任意位置的子串」会让模型从语料别处抄一句就得分（与检索无关）；
    quote 须落在本题 material 内，**且 file 与 line 须指向同一个返回片段**（2026-10-10
    复核整改·甲-9：旧实现用 `ok_file or ok_line`，于是「引文取自片段 A、却把 line 填成
    片段 B 的 seq」仍算逐字可回源。现要求 file 命中某返回片段、且 line 等于**该片段自身**
    的序号——cid 形如 `doc#seq`，从中解析出 seq 与 line 比对；cid 无 `#` 时退化为
    「line 须在该题返回的 seq 集合里」）。
    """
    if mat is None:
        return False
    mat_norm, cids, seqs = mat
    if not mat_norm:
        return False
    cid_norms = {norm(c): c for c in cids}
    for b in (a.get('basis') or []):
        if not isinstance(b, dict):
            continue
        q = norm(b.get('quote'))
        if len(q) < 8 or q not in mat_norm:
            continue
        fkey = norm(b.get('file'))
        if cid_norms and fkey not in cid_norms:
            continue
        try:
            line = int(b.get('line'))
        except Exception:
            continue
        if fkey in cid_norms:
            raw_cid = cid_norms[fkey]
            tail = raw_cid.rsplit('#', 1)[1] if '#' in raw_cid else ''
            if tail.isdigit():
                if line == int(tail):          # file 与 line 须同指一个片段
                    return True
                continue
        if line in seqs:                        # cid 无 seq 信息时退回 seq 集合判定
            return True
    return False


# ---------------- 主体混淆（同名异体/嵌套主体的影子链取值） ----------------
def decoy_index() -> dict:
    """影子链索引：(doc, 主链主体, 槽位) → 影子链用过的全部取值。

    ★ issue #23：synth.py 写 synth_log.json 时**丢了 `decoy_of`**，这里便静默返回空表，
    于是主体混淆率对任何答卷恒为 0——首轮报告据此把「干扰档没有咬到任何一家」列为
    「本轮最需要追问的一条」，真实原因却只是判分器从没读到影子链。
    现在：有影子链却一条都没索引到 ⇒ **直接报错**，不再静默给一个恒 0 的指标。
    """
    lg = _load(OUT / 'synth_log.json', {'chains': []})
    chains = lg.get('chains', [])
    idx = {}
    for c in chains:
        if c.get('is_decoy') and c.get('decoy_of'):
            vals = {norm(e['to']) for e in c['events'] if e.get('to')}
            idx[tuple(c['decoy_of'])] = vals
    n_dec = sum(1 for c in chains if c.get('is_decoy'))
    if n_dec and not idx:
        raise RuntimeError(
            f'synth_log.json 里有 {n_dec} 条影子链，但 `decoy_of` 一条都没有 ⇒ '
            f'主体混淆率会恒为 0（issue #23）。请用 chain/tools/synth.py 重新生成'
            f'语料与日志（旧版 synth.py 不写该字段）。')
    return idx


def subject_confused(a: dict, key: dict, decoys: dict) -> bool:
    v = norm(a.get('value'))
    if not v or v == norm(key['answer']['value']):
        return False
    return v in decoys.get((key['doc'], key['subject'], key['slot']), set())


# ---------------- 单臂判分 ----------------
def _bucket(chain_len: int) -> str:
    if chain_len <= 8:
        return 'short'
    if chain_len <= 30:
        return 'mid'
    return 'long'


def _main_ok(k: dict, a: dict):
    """主指标（链长压力轴用）：现值/历史看值对不对，变更看链条全不全；其它问型不进。

    与 `judge_arm` 同分母：答案为 null 的现值/历史题、没有「值→值」变更的变更题
    一律**不进分母**（否则空答臂靠 null 平凡匹配拿分——自检里的坏系统就钻这个空子）。
    """
    if k['type'] in ('现值', '历史'):
        if k['answer']['value'] is None:
            return None
        return value_correct(a, k)
    if k['type'] == '变更':
        if not want_changes(k):
            return None
        return chain_complete(a, k)
    return None


def closed_hit(k: dict, a: dict) -> bool:
    """闭卷臂（无材料、凭常识作答）在这道题上**判对**了吗（issue #44-四）。

    判据与该题在主读数里的轴一一对应：现值/历史/缘由看值（缘由的值＝起因），变更看链条
    完整，状态归属看四态，时点看值＋状态＋时序号。闭卷臂判对的题＝**可猜题**：它没读
    任何材料就答对了，说明该题由常识/多数类即可命中，不是「版本化召回」的读数。
    """
    t = k['type']
    if t in ('现值', '历史', '缘由'):
        return bool(value_correct(a, k))
    if t == '变更':
        return bool(chain_complete(a, k))
    if t == '状态归属':
        return bool(eq(a.get('state'), k['answer']['state']))
    if t == '时点':
        return bool(value_correct(a, k) and eq(a.get('state'), k['answer']['state'])
                    and at_seq_ok(a, k))
    return False


def closed_hits(keys: list[dict], arm: str = 'closed') -> dict:
    """逐题扫闭卷臂答卷，返回 `{qid: 题面类型}`（issue #44-四）。

    ★ issue #30 的「逐题剔除」此前**没有落地**：闭卷门 ② 只比三个**聚合率**（现值/历史/
      变更链各 ≤ 0.2），于是闭卷臂答对 51 道题（各率 18%）时 ② 照样判过，那 51 道可猜题
      也照旧留在被测臂的主读数里。这里给出逐题清单：既用于 ② 的逐题判据，也用于把可猜题
      从被测臂主读数里剔掉。
    """
    hits = {}
    for k in keys:
        if _excluded(k):
            continue
        a = _ans_of(arm, k['qid'])
        if a is None:
            continue
        if closed_hit(k, a):
            hits[k['qid']] = k['type']
    return hits

def judge_arm(arm: str, keys: list[dict], doc_norms: dict, decoys: dict,
              skip: set | None = None) -> dict:
    """只统计**确实有答卷文件**的题（小样 --limit 跑时，未跑的题不进分母）。

    `skip`＝要从主读数里剔掉的 qid（issue #44-四：闭卷臂判对的**可猜题**）；被剔的题
    既不入任何指标的分母，也不参与完整性核对，另记 `n_skipped`。
    """
    pairs = []
    n_skipped = 0
    for k in keys:
        if _excluded(k):
            continue
        if skip and k['qid'] in skip:
            n_skipped += 1
            continue
        a = _ans_of(arm, k['qid'])
        if a is None:
            continue
        pairs.append((k, a))
    n = len(pairs)

    # issue #51-D4: empty denominators go into the na list.
    na = []

    def rate(xs, name=None):
        if xs:
            return round(sum(1 for x in xs if x) / len(xs), 4)
        if name:
            na.append(name)
        return 0.0

    # ★ issue #28：现值/历史/滞后/超前的分母**不再剔除**答案为 null 的退役题——
    #   剔除等于让「退役后照报旧值」的臂与满分臂读数逐位相同。空答臂不会因此白拿分：
    #   null 答案题要求「答 null **且**状态判对」，空答的 state 是 null ≠ 'retired'。
    # ★ issue #27：作答异常时运行器会写一份**全空占位卷**（`_error`），解析失败则打
    #   `_json_ok=False`——旧实现只按「答卷文件在不在」判完整性，40% 题调用失败的臂
    #   照样算「同源且完整」进 readings。现在逐题统计，`judge_arms` 据此剔除整臂。
    error_qids = [k['qid'] for k, a in pairs
                  if a.get('_error') or a.get('_json_ok') is False]
    present = [value_ok(a, k) for k, a in pairs if k['type'] == '现值']
    history = [value_ok(a, k) for k, a in pairs if k['type'] == '历史']
    # ★ issue #51-D5／D6：chain 系读数与 `_main_ok`／bucket_main **同分母**——没有
    #   「值→值」变更（`want_changes` 为空）的变更题不进分母。旧实现把它们全收进来，
    #   而 `chain_complete` 对空 want 返回 False ⇒ 这类题**无论如何作答都记 0**，
    #   与预注册口径「不进分母」相反（当前 642 键 / 63 变更题上 want_changes 为空者 0 题，
    #   故本次对齐在现有数据上是 no-op，只堵住潜在分叉）。
    chain_pairs = [(k, a) for k, a in pairs if k['type'] == '变更' and want_changes(k)]
    chain = [chain_complete(a, k) for k, a in chain_pairs]
    chain_rows = [chain_rows_hit(a, k) for k, a in chain_pairs]
    chain_row_recall = (round(sum(h for h, _ in chain_rows) / sum(t for _, t in chain_rows), 4)
                        if chain_rows and sum(t for _, t in chain_rows) else 0.0)
    # ★ issue #24：多列不罚会把「整篇列出、不认主体」的答卷读成满分——补精度读数：
    #   所列行中**属于本链**的占比（空答无行 ⇒ 0.0，与其余读数同口径）。
    chain_lists = [(chain_extra_rows(a, k), len(_chain_items(a)))
                   for k, a in chain_pairs]
    _rows = sum(t for _, t in chain_lists)
    chain_precision = (round(1.0 - sum(e for e, _ in chain_lists) / _rows, 4)
                       if _rows else 0.0)
    stale = [stale_confused(a, k) for k, a in pairs if k['type'] == '现值']
    # ★ 2026-10-10 复核整改·甲-9：future 分母也须用 has_value 过滤——旧实现把答案为
    #   null 的历史/时点问（如退役点）也计入分母，而 null 答案的题在 future_confused 里
    #   恒返回 False（v 为空），只会**稀释**超前混淆率，偏离「用了取样点之后才生效的值
    #   的比例」这一声明口径。现值/历史已用 has_value，这里对齐。
    future = [future_confused(a, k) for k, a in pairs
              if k['type'] in ('历史', '时点')]
    subj = [subject_confused(a, k, decoys) for k, a in pairs
            if k['interference'] in ('同名异体', '嵌套主体')]
    # ★ 四态分项（issue #21）：按**真值态**分组，逐项给率与 n。合并数保留，
    #   但报告须附多数类基线——合并数被 active 主导（103/197），区分不了「退役」与「不存在」。
    st_pairs = [(k, a) for k, a in pairs if k['type'] == '状态归属']
    four = [eq(a.get('state'), k['answer']['state']) for k, a in st_pairs]
    four_by = {s: [eq(a.get('state'), k['answer']['state'])
                   for k, a in st_pairs if k['answer']['state'] == s] for s in FOUR_STATES}
    # ★ 时点指标（issue #21）：预注册要求「时点定位误差（报绝对分布＋方向：答早/答晚）」，
    #   旧实现里 63 道时点问只进超前混淆的分母，答对答错都不计分。
    tp_pairs = [(k, a) for k, a in pairs if k['type'] == '时点']
    # ★ issue #43-三：`timepoint` 必须同时判对 `at_seq`。旧实现只看 value+state，
    #   于是一个「值/状态全对、时序号乱填」的臂拿到满分——预注册要的是**时点定位**，
    #   常数臂（不读材料、一律答 null/retired）实测拿到 0.6129，正是这条漏判造的。
    timepoint = [value_correct(a, k) and eq(a.get('state'), k['answer']['state'])
                 and at_seq_ok(a, k) for k, a in tp_pairs]
    # 方向只统计**答错时点**的题（答对时序号相同，不计入「答早/答晚」分母）
    # ★ issue #43-三：`tp_early = tp_late = []` 是**同一个列表**——两个方向读数恒等，
    #   「答早」与「答晚」分不开。必须各自新建。
    tp_early, tp_late = [], []
    for k, a in tp_pairs:
        want, got = k['answer'].get('at_seq'), a.get('at_seq')
        if want is None or not isinstance(got, (int, float)) or got == want:
            continue
        (tp_early if got < want else tp_late).append(True)
    reason = [value_correct(a, k) for k, a in pairs if k['type'] == '缘由']
    verb = [verbatim_ok(a, _material_of(arm, k['qid'])) for k, a in pairs]

    # 链长三桶的主指标（③ 用；与上面同一批 pairs，故与行内读数不可能矛盾）
    bmain, bmain_n = {}, {}
    for k, a in pairs:
        ok = _main_ok(k, a)
        if ok is None:
            continue
        b = _bucket(k['chain_len'])
        bmain[b] = bmain.get(b, 0) + (1 if ok else 0)
        bmain_n[b] = bmain_n.get(b, 0) + 1
    bucket_main = {b: round(bmain[b] / bmain_n[b], 4) for b in bmain_n if bmain_n[b]}
    counts = dict(present=len(present), history=len(history), chain=len(chain),
                  chain_row_recall=len(chain_rows), chain_precision=len(chain_lists),
                  stale=len(stale), future=len(future),
                  subject_confusion=len(subj), four_state=len(four), reason=len(reason),
                  verbatim=len(verb),
                  **{f'four_state_{s}': len(four_by[s]) for s in FOUR_STATES},
                  timepoint=len(timepoint),
                  timepoint_early=len(tp_early), timepoint_late=len(tp_late))
    # 四态多数类基线（诊断：合并数被它主导，见 issue #21）
    for _nm, _xs in (('timepoint_early', tp_early), ('timepoint_late', tp_late)):
        if not _xs and not (tp_early or tp_late):
            na.append(_nm)
    n_st = len(st_pairs)
    four_majority = (round(max(len(four_by[s]) for s in FOUR_STATES) / n_st, 4)
                     if n_st else 0.0)
    return dict(arm=arm, n_error=len(error_qids), error_qids=error_qids[:5],
                present=rate(present, 'present'), history=rate(history, 'history'),
                chain=rate(chain, 'chain'),
                chain_row_recall=chain_row_recall,
                chain_precision=chain_precision,
                stale=rate(stale, 'stale'), future=rate(future, 'future'),
                subject_confusion=rate(subj, 'subject_confusion'),
                four_state=rate(four, 'four_state'),
                four_state_majority=four_majority,
                **{f'four_state_{s}': rate(four_by[s], f'four_state_{s}')
                   for s in FOUR_STATES},
                timepoint=rate(timepoint, 'timepoint'),
                timepoint_early=(round(len(tp_early) / (len(tp_early) + len(tp_late)), 4)
                                 if (tp_early or tp_late) else 0.0),
                timepoint_late=(round(len(tp_late) / (len(tp_early) + len(tp_late)), 4)
                                if (tp_early or tp_late) else 0.0),
                reason=rate(reason, 'reason'), verbatim=rate(verb, 'verbatim'), n=n,
                na=sorted(set(na)),
                counts=counts, bucket_main=bucket_main, bucket_main_n=bmain_n,
                n_skipped=n_skipped,
                # ★ issue #44-三：单调性判据要做**单侧两比例检验**，需要各桶的命中数
                #   （只有率与分母时用 round(率×分母) 反推会引入误差）。
                bucket_main_k=bmain)


def _corpus_index():
    keys = _load(OUT / 'keys.json', [])
    corpus = _load(OUT / 'corpus.json', [])
    doc_text = {}
    for c in corpus:
        doc_text.setdefault(c['doc'], []).append(c['text'])
    doc_norms = {d: norm(''.join(t)) for d, t in doc_text.items()}
    return keys, doc_norms, decoy_index()


def judge_arms(arms: list[str], write: bool = True) -> list[dict]:
    """判分；**只把「同源且非截断」的臂当整臂读数发布**。

    一条臂进 readings.json 的条件：有 manifest、keys 指纹与当前 keys.json 一致、
    且不是 `--limit` 截断的冒烟答卷、答卷题数不缺。否则进 readings_excluded.json。
    """
    keys, doc_norms, decoys = _corpus_index()
    fp = keys_fp(keys)
    # ★ issue #44-二：keys_fp 只哈希每题的值/状态/序号——换一套**语料**（reconstructible、
    #   change_chain、accept 全变）它一位不动。数据指纹把三份内容一并纳入，逐臂比对。
    fp_data = hmb_paths.data_fp()
    n_expected = sum(1 for k in keys if not _excluded(k))
    n_amb = sum(1 for k in keys if k.get('ambiguous'))
    # ★ issue #44-四：闭卷臂判对的**可猜题**逐题清单（issue #30 的「逐题剔除」落地）。
    #   被测臂的主读数里剔掉这些题，且分母随之下调——旧实现只看三个聚合率，
    #   闭卷臂答对 51 题（各率 18%）时 ② 照样判过，那 51 道可猜题留在主读数里。
    chits = closed_hits(keys)
    rows, excluded = [], []
    for arm in arms:
        d = RUNS / f'chain_{arm}'
        skip = None if arm == 'closed' else set(chits)
        row = judge_arm(arm, keys, doc_norms, decoys, skip=skip)
        m = _manifest(arm)
        row['keys_fp'] = m.get('keys_fp')
        n_exp_arm = n_expected - (len(chits) if skip else 0)
        row['n_expected'] = n_exp_arm
        row['n_closed_excluded'] = (len(chits) if skip else 0)
        row['closed_excluded_qids'] = sorted(chits)[:10] if skip else []
        # ★ issue #44-一：读数行须能看出「分母为什么是这个数」——可推题与同名异体歧义题
        #   都不进主读数，各自的题数单列。
        row['n_reconstructible'] = sum(1 for k in keys if k.get('reconstructible'))
        row['n_ambiguous'] = n_amb
        row['sampled'] = bool(m.get('calib_sample'))
        row['manifest_errors'] = m.get('errors')
        # ★ 来源字段（issue #41）：读数行必须能看出「这个数字是哪次运行的答卷算出来的」。
        #   旧读数行不带任何来源，判分器读到另一套 harness 的旧卷时读者无从分辨。
        row['dir'] = str(d)
        row['harness'] = m.get('harness')
        # ★ issue #44-二/五：读数行须能看出「这份数字出自哪份数据／哪份适配器／哪个库」。
        row['data_fp'] = m.get('data_fp')
        row['adapter'] = m.get('adapter')
        row['harness_files'] = m.get('harness_files')
        row['store'] = m.get('store')
        reasons = []
        if not m:
            reasons.append('无 manifest.json（无法核对同源）')
        elif m.get('keys_fp') != fp:
            reasons.append(f"keys 指纹不符（manifest={m.get('keys_fp')} vs 当前={fp}）")
        elif not m.get('data_fp'):
            reasons.append('manifest 缺 data_fp（语料／答案键／生成日志指纹；issue #44-二）')
        elif m.get('data_fp') != fp_data:
            reasons.append(f"数据指纹不符（manifest={m.get('data_fp')} vs 当前={fp_data}；"
                           '答卷出自从前的语料/答案键）')
        # ★ manifest.dir 必须等于**自己实际读的目录**（issue #41）：keys_fp 只能证明
        #   「答案是同一套题」，证明不了「这是这次跑的卷」——换一套 harness 重跑，
        #   keys_fp 照样对得上。目录不一致即剔除并写明原因（与「无 manifest」同一路径）。
        md = str(m.get('dir') or '').strip()
        if md and Path(md).resolve() != d.resolve():
            reasons.append('manifest.dir=' + md + ' ≠ 实际读取目录 ' + str(d)
                           + '（判分器与运行器读写的不是同一个目录，issue #41）')
        if (m.get('limit') or 0) > 0:
            reasons.append(f"答卷为 --limit {m.get('limit')} 的截断冒烟，非整臂读数")
        # ★ issue #27：带 _error / _json_ok=False 的**占位卷**不是正常答卷
        if row.get('n_error'):
            reasons.append(f"作答/解析失败 {row['n_error']} 题（占位卷，非正常答卷；"
                           f"如 {row.get('error_qids')}）")
        elif isinstance(m.get('errors'), int) and m.get('errors') > 0:
            reasons.append(f"manifest.errors={m['errors']} 但答卷里没有失败标记"
                           f"（分片并发会互相覆盖 manifest，须以答卷为准）")
        # 缺题：只统计非可推题，故分母也用非可推题数（n_expected）
        if m.get('keys_fp') == fp and row['n'] < n_exp_arm:
            reasons.append(f"答卷缺题（{row['n']}/{n_exp_arm} 主读数题；"
                           f'已剔闭卷可猜题 {row["n_closed_excluded"]}）')
        row['complete'] = not reasons
        if reasons:
            row['exclude_reason'] = '；'.join(reasons)
            excluded.append(row)
        else:
            rows.append(row)
    # issue #51-D4: name the empty-denominator readings instead of printing a bare 0.0.
    for row in rows:
        if row.get('na'):
            print(f"  ★ {row['arm']}: {len(row['na'])} "
                  f"项读数无样本（分母为空，值按 0.0 记）"
                  f"——" + "、".join(row['na']))
    if write:
        (OUT / 'readings.json').write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        (OUT / 'readings_excluded.json').write_text(
            json.dumps(excluded, ensure_ascii=False, indent=1), encoding='utf-8')
        # ★ issue #44-四：可猜题的**全量**清单单独落盘（readings 行里只留前 10 个示例）。
        (OUT / 'closed_hits.json').write_text(
            json.dumps(chits, ensure_ascii=False, indent=1, sort_keys=True),
            encoding='utf-8')
    return rows


# ---------------- 校准零号 ----------------
def _bucket_rates(arm: str, keys: list[dict], field: str = 'present') -> dict:
    """按链长三桶（short ≤8 / mid 9–30 / long >30）算某指标的桶内正确率。

    只作**诊断**用（③ 现在从 reading 行的 bucket_main 取，见 calibration）。
    """
    qs = [k for k in keys if not _excluded(k)]
    if field == 'present':
        qs = [k for k in qs if k['type'] == '现值' and k['answer']['value'] is not None]
    buckets = {}
    for k in qs:
        a = _ans_of(arm, k['qid'])
        if a is None:
            continue
        ok = value_correct(a, k)
        buckets.setdefault(_bucket(k['chain_len']), []).append(ok)
    return {b: round(sum(v) / len(v), 4) for b, v in buckets.items() if v}


def _structural_baseline(keys: list[dict]) -> dict:
    """语料结构压力轴：现值问的「只凭值集合瞎猜」期望正确率 = 1/该链不同取值个数。

    ★ 这是**语料侧诊断**，只读 keys.json、与任何臂无关——**不得**作为效度门判据
    （否则一个答不对任何题的坏系统也能靠它过关）。
    """
    qs = [k for k in keys if not _excluded(k) and k['type'] == '现值']
    buckets = {}
    for k in qs:
        vals = {norm(e['to']) for e in k['answer']['chain'] if e.get('to')}
        if not vals:
            continue
        buckets.setdefault(_bucket(k['chain_len']), []).append(1.0 / len(vals))
    return {b: round(sum(v) / len(v), 4) for b, v in buckets.items() if v}


def _pair_tol(p1: float, p2: float, n1: int, n2: int, z: float = Z95) -> float:
    """相邻两桶允许的**回升**上限 = 两比例差的标准误 × 1.96（抽样噪声）。

    ★ issue #20：旧实现用固定 0.05，不随桶样本量变化——long 桶只有 29 题，
      同一容差对三个桶的意义并不一样。改为按各桶 n 算 95% 置信限。
    """
    def se(p: float, n: int) -> float:
        return math.sqrt(max(p * (1.0 - p), 1e-12) / max(n, 1))
    return z * math.sqrt(se(p1, n1) ** 2 + se(p2, n2) ** 2)


def _nonincreasing(seq: list[float], ns: list[int] | None = None,
                   tol: float = 0.05, z: float = Z95) -> bool:
    """链长单调退化（相邻档不得显著回升）。

    给了各桶样本量 `ns` ⇒ 容差按抽样误差算；未给（兼容旧调用）⇒ 退回固定 `tol`。
    """
    if len(seq) < 2:
        return True
    for i in range(len(seq) - 1):
        lim = (_pair_tol(seq[i], seq[i + 1], ns[i], ns[i + 1], z)
               if ns and len(ns) == len(seq) else tol)
        if seq[i] < seq[i + 1] - lim:
            return False
    return True


def _all_equal(seq: list[float], tol: float = 1e-6) -> bool:
    return (max(seq) - min(seq)) <= tol


def two_prop_z(k1: int, n1: int, k2: int, n2: int) -> float:
    """单侧两比例 z（H1: p1 > p2，合并比例算标准误）。

    ★ issue #44-三：链长单调性此前只看**点估计**，与桶样本量无关 ⇒ 平坦臂靠抽样噪声就能
    过门（真值 0.80 三桶相同，400 次二项抽样有 24.2% 首尾差 ≥ 0.05）。这里按各桶实际
    命中数/分母算 z，样本不足或方差为 0 时返回 0（即「看不出差异」）。
    """
    if min(n1, n2) <= 0:
        return 0.0
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(max(p * (1.0 - p), 1e-12) * (1.0 / n1 + 1.0 / n2))
    if se <= 0:
        return 0.0
    return (p1 - p2) / se


def c3_direction(bm: dict, bn: dict, bk: dict | None = None,
                 min_bucket_n: int = MIN_BUCKET_N) -> tuple:
    """③ 的**方向判据**（纯函数，供 calibration 与 selftest 共用）。

    返回 `(是否满足, 理由, 明细)`；明细含 order/seq/ns/ks/z_drop/drop/rises。
    绝对水平下界（MIN_SUT_SHORT／结构基线）不在这里——那是对照臂与语料侧的诊断，
    由调用方另加。
    """
    bk = bk or {}
    order = [b for b in ('short', 'mid', 'long')
             if b in bm and bn.get(b, 0) >= min_bucket_n]
    seq = [bm[b] for b in order]
    ns = [bn[b] for b in order]
    ks = [int(bk[b]) if bk.get(b) is not None else int(round(bm[b] * bn[b]))
          for b in order]
    det = dict(order=order, seq=seq, ns=ns, ks=ks, z_drop=0.0, drop=0.0, rises=[])
    if len(seq) < 2:
        return False, f'可用桶不足（{order}，各桶 n={ns}，要求各桶 n ≥ {min_bucket_n}）', det
    drop = seq[0] - seq[-1]
    z_drop = two_prop_z(ks[0], ns[0], ks[-1], ns[-1])
    det.update(drop=round(drop, 4), z_drop=round(z_drop, 3))
    rises = []
    for i in range(len(seq) - 1):
        zr = two_prop_z(ks[i + 1], ns[i + 1], ks[i], ns[i])
        rises.append(dict(pair=f'{order[i]}→{order[i + 1]}',
                          delta=round(seq[i + 1] - seq[i], 4), z=round(zr, 3)))
    det['rises'] = rises
    bad_rise = [x for x in rises if x['delta'] > MIN_RISE or x['z'] >= MIN_DROP_Z]
    if _all_equal(seq):
        return False, f'三桶读数全等（{dict(zip(order, seq))}）——没有退化', det
    if bad_rise:
        return False, ('相邻档回升 %s 超过容差（点估计 ≤ %s 且单侧 z < %s）'
                       % (bad_rise, MIN_RISE, MIN_DROP_Z)), det
    if drop < MIN_DROP - DROP_EPS:
        return False, ('首尾仅下降 %+.4f（要求 ≥ %s）——相邻档未见显著回升也算不上「随链长退化」'
                       % (drop, MIN_DROP)), det
    if z_drop < MIN_DROP_Z:
        return False, ('首尾下降 %+.4f 未达单侧显著（z=%.3f < %s，α=0.05）——'
                       '点估计的差可能只是抽样噪声' % (drop, z_drop, MIN_DROP_Z)), det
    return True, ('桶 %s＝%s（n=%s，k=%s）：首尾下降 %+.4f 且单侧 z=%.3f ≥ %s；'
                  '相邻档回升均在容差内'
                  % (order, seq, ns, ks, drop, z_drop, MIN_DROP_Z)), det


def _damage_criterion(by: dict, sut_arm: str | None,
                      suts: list[dict]) -> tuple[bool | None, str, dict]:
    """预注册的 ②「破坏方向」：乙/丙/丁 三条破坏臂在映射指标上显著下降，且**两两可分**。

    ★ issue #26：这条判据此前根本没实现（判分器把预注册第 2 条换成了「读数自洽」），
    于是不跑任何破坏臂也能「四条全过」。现在：
      · 一条破坏臂都没跑 ⇒ 返回 None（未评），调用方据此把 passed 置 False、
        gate_stage 标为 `no-damage-arms`；
      · 只跑了部分 ⇒ False（缺臂）；
      · 三条齐备 ⇒ 每条在其映射指标上相对正常臂下降 ≥ MIN_DAMAGE_DROP，
        且三条臂的读数指纹两两 L∞ 距离 ≥ MIN_SEPARATION。
    """
    got = sorted(a for a in by if is_damage_arm(a))
    if not got:
        return (None,
                '未评：本轮读数里没有破坏臂（乙/丙/丁）——预注册第 2 条无法评，'
                'passed 不得为 True（须先跑 probe_runner --damage）', {})
    missing = [a for a in DAMAGE_ARMS if a not in by]
    detail: dict[str, dict] = {}
    all_ok = not missing
    for a in got:
        r = by[a]
        need = DAMAGE_MAP.get(a, ())
        # ★ issue #43-二①：基底取自**该臂自己的** `manifest.base_arm`（运行器写的，破坏臂
        #   就是以它破坏的那个系统），而不是 `SUT_ORDER` 排第一的臂。旧实现拿 lingshu 当
        #   基底，实测三条「零破坏」的 bm25 副本被读出 0.29–0.32 的「下降」⇒ c_damage=True。
        base_name = (_manifest(a).get('base_arm') or sut_arm
                     or (suts[0]['arm'] if suts else None))
        if base_name is None or base_name not in by:
            detail[a] = dict(base=base_name, required=list(need), drops={}, ok=False,
                             why=f'基底 {base_name!r} 不在本轮读数里')
            all_ok = False
            continue
        base = by[base_name]
        drops = {f: round(float(base.get(f, 0.0) or 0.0) - float(r.get(f, 0.0) or 0.0), 4)
                 for f in need}
        # ★ issue #43-二②：还要查**不是「什么都打垮」**（方向特异性）。旧实现只要求映射
        #   指标下降，于是一条把所有指标一起归零的臂满足任何映射——「方向与映射表一致」
        #   形同虚设（审计脚本 p1_2_2 ②：三条全空答卷全部 c_damage=True）。
        #   可机械检验的口径：破坏臂须在**至少一项非映射主指标**上仍与基底相当
        #   （|Δ| < MIN_DAMAGE_DROP / 2）——即破坏是有指向的，不是整机失效。
        #   诚实边界：这条只能否掉「整机归零」，不能证明下降**归因于**该机制；
        #   机制归因仍须靠 runner 侧的破坏实现（见 README §6 与 issue #43-一）。
        off = {f: round(abs(float(base.get(f, 0.0) or 0.0) - float(r.get(f, 0.0) or 0.0)), 4)
               for f in METRIC_FIELDS if f not in need}
        #   「本来有读数」＝基底该指标 ≥ MIN_DAMAGE_DROP（否则「0 保持 0」是空话）。
        kept = [f for f, v in off.items()
                if v < MIN_DAMAGE_DROP / 2 and float(base.get(f, 0.0) or 0.0) >= MIN_DAMAGE_DROP]
        okc = (bool(need) and all(d >= MIN_DAMAGE_DROP for d in drops.values())
               and bool(kept))
        detail[a] = dict(base=base_name, required=list(need), drops=drops,
                         unmapped_kept=kept,
                         unmapped_off={f: v for f, v in off.items() if v}, ok=okc)
        all_ok = all_ok and okc
    # ★ issue #43-二③：可分度只在**三条破坏臂映射指标的并集**上算。旧实现在
    #   `METRIC_FIELDS` 全部 18 个字段上取 L∞，任一与破坏无关、样本很小的字段（如
    #   four_state_absent，n=12）差 0.05 即可「分开」——实测三条全空答卷靠它拿到
    #   1.0 / 0.5 / 0.5 的「可分度」。
    fields = sorted({f for a in got for f in DAMAGE_MAP.get(a, ())})
    fps = {a: tuple(round(float(by[a].get(f, 0.0) or 0.0), 4) for f in fields) for a in got}
    names = sorted(fps)
    seps = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            seps[f'{names[i]} vs {names[j]}'] = round(
                max(abs(x - y) for x, y in zip(fps[names[i]], fps[names[j]])), 4)
    sep_ok = bool(seps) and all(v >= MIN_SEPARATION for v in seps.values())
    ok_all = bool(all_ok and sep_ok)
    reason = ('；'.join(f'{a}（基底 {detail[a].get("base")}）在 {detail[a]["required"]} 上下降 '
                        f'{detail[a]["drops"]}、非映射未受影响 {detail[a].get("unmapped_kept")}'
                        f'（{"合格" if detail[a]["ok"] else "不合格"}'
                        + ('' if detail[a].get('ok') else f'：{detail[a].get("why") or "下降不足或整机一起塌"}')
                        + '）' for a in got)
              + (f'；缺臂 {missing}' if missing else '')
              + f'；两两可分（仅在映射指标 {fields} 上）{seps}（要求 ≥ {MIN_SEPARATION}）'
              + f' ⇒ {"过" if ok_all else "不过"}')
    return ok_all, reason, detail


def calibration(readings: list[dict], limit: int = 0, sut_arm: str | None = None,
                control_arms: tuple = CONTROL_ARMS,
                closed_arm: str = 'closed') -> dict:
    """校准零号判据（全过才 passed）。

    ① 版本盲指纹（现值≈正常、历史/变更→0）＋现值分母 ≥ MIN_PRESENT_N；
    ② 破坏方向（乙/丙/丁 在映射指标上显著下降，且三臂两两可分）——
       ★ issue #26：这条是 README §6 预注册的第 2 条，旧实现根本没跑破坏臂，
       却把「四条全过」照发。现在没有破坏臂读数即「未评」，passed=False；
    ③ **被测系统臂**的主指标随链长单调退化（≥2 个桶、每桶 ≥ MIN_BUCKET_N）
       **且短链桶达绝对水平下界、且显著高于结构基线**（防常数猜测器蒙过，见 MIN_SUT_SHORT）；
       本轮读数里若**没有被测系统臂**（只跑了 versionblind/closed 两个对照臂），
       ③ 记为「未评」（`criteria.c3 is None`、`gate_stage='controls-only'`）——
       这一阶段 `passed` 仍为 false（不在缺 ③ 的情况下宣布过门），待被测臂答卷后
       再跑一次判分（`probe_judge.py --gate`）把 ③ 补上。
    ④ 读数自洽（**独立复核输入与读数**，不是把输出跟自己比）：九项主读数都在 [0,1]、
       每条臂的答卷与当前 keys **同源且完整**（manifest.keys_fp 一致、非可推题答卷数
       达 n_expected）、且能由**磁盘上的答卷**机械复算（防陈旧/伪造读数）。
    """
    keys, doc_norms, decoys = _corpus_index()
    fp = keys_fp(keys)
    fp_data = hmb_paths.data_fp()          # ★ issue #44-二：同源的第二把尺（语料/答案键/日志）
    n_expected = sum(1 for k in keys if not _excluded(k))
    by = {r['arm']: r for r in readings}
    vb = by.get(control_arms[0])
    cb = by.get(control_arms[1])

    vb_present_n = (vb or {}).get('counts', {}).get('present', 0)
    cb_n = (cb or {}).get('n', 0)
    c1 = bool(vb) and vb['present'] >= 0.5 and vb['history'] <= 0.15 \
        and vb['chain'] <= 0.15 and vb_present_n >= MIN_PRESENT_N
    # ★ issue #44-四：② 加**逐题**判据。旧实现只比三个聚合率：闭卷臂在 642 题里答对 51 道
    #   （各率 18%），三条率都 ≤ 0.2 ⇒ ② 判过；可那 51 道题根本没读材料就答对了，
    #   是**可猜题**，既说明题库有漏洞，也让被测臂在这些题上白拿分。现在两件事一起做：
    #   (a) 逐题命中率 ≤ CLOSED_MAX_HIT，否则 ② 不过（题库须重造）；
    #   (b) 命中清单从被测臂主读数中剔除（见 judge_arms 的 skip）。
    chits = closed_hits(keys, arm=closed_arm)
    n_main = sum(1 for k in keys if not _excluded(k))
    cb_hit_rate = (round(len(chits) / n_main, 4) if n_main else 0.0)
    c2_agg = bool(cb) and cb['present'] <= 0.2 and cb['history'] <= 0.2 \
        and cb['chain'] <= 0.2 and cb_n >= MIN_ARM_N
    c2_hit_ok = bool(cb) and cb_hit_rate <= CLOSED_MAX_HIT
    c2 = bool(c2_agg and c2_hit_ok)

    # ③ 只认被测系统臂的读数（对照臂与语料结构都不算）
    # ★ issue #25：③ 是「压力轴是否有效」的判据，属题库性质，旧实现却只评
    #   SUT_ORDER 排第一的臂（lingshu）——首轮 bm25／Hindsight 都不单调，代码仍判 c3=True，
    #   与手写校准记录「③ 不合格」相反。现在**逐臂**评，再按预注册口径汇总（全部满足）。
    suts = [r for r in readings
            if r['arm'] not in control_arms and not is_damage_arm(r['arm'])]
    suts.sort(key=lambda r: (SUT_ORDER.index(r['arm']) if r['arm'] in SUT_ORDER
                             else len(SUT_ORDER), r['arm']))
    if sut_arm is not None:
        # 显式指定 ⇒ 只评这一条（保留单臂诊断能力），但**不**据此宣布全门通过
        sut = by.get(sut_arm)
        eval_suts = [sut] if sut else []
    else:
        sut = suts[0] if suts else None
        eval_suts = suts
    struct = _structural_baseline(keys)          # 语料结构基线（诊断 + ③ 的下界参照）
    c3_by_arm: dict[str, dict] = {}

    def _eval_c3(r: dict) -> tuple[bool, str]:
        """对**一条**被测臂评 ③，返回 (是否满足, 理由)。"""
        bm = r.get('bucket_main') or {}
        bn = r.get('bucket_main_n') or {}
        # ★ 方向判据（issue #20 起、issue #44-三 定型）：**单侧两比例检验**。
        #   旧实现只看点估计（首尾差 ≥ 0.05、相邻回升 ≤ 抽样噪声）⇒ 平坦臂靠抽样噪声过门
        #   （真值三桶同为 0.80，400 次二项抽样 24.2% 判过），U 形臂（0.80→0.60→0.75）
        #   首尾差恰为 0.05 也判过。现在首尾须 z ≥ 1.645 且点估计差 ≥ 0.05 − 1e-9。
        mono, why_dir, det = c3_direction(bm, bn, r.get('bucket_main_k'))
        order, seq, ns = det['order'], det['seq'], det['ns']
        drop, drop_ok = det['drop'], bool(mono)
        # ★ 绝对水平下界：单调性**单独**不够——语料结构本身随链长单调（短链取值少），
        #   一个只会瞎猜（恒输出最高频答案值）的坏系统也能「非增且非全等」。故还须
        #   短链桶既达 MIN_SUT_SHORT，又显著高于结构基线（MIN_SUT_MARGIN）。
        short_rate = bm.get('short') if bn.get('short', 0) >= MIN_BUCKET_N else None
        base_short = struct.get('short')
        floor_ok = short_rate is not None and short_rate >= MIN_SUT_SHORT
        margin_ok = (short_rate is not None and base_short is not None
                     and short_rate >= base_short + MIN_SUT_MARGIN)
        okc = bool(mono and drop_ok and floor_ok and margin_ok)
        if okc:
            why = (f'{why_dir}；短链 {short_rate} ≥ 下界 {MIN_SUT_SHORT} 且 ≥ 结构基线 '
                   f'{base_short}+{MIN_SUT_MARGIN}')
        elif not drop_ok:
            why = why_dir
        elif not floor_ok:
            why = (f'短链桶 {short_rate} 低于绝对下界 {MIN_SUT_SHORT}'
                   f'（单调但绝对水平不合格，疑为常数猜测/瞎猜系统）')
        else:
            why = (f'短链桶 {short_rate} 未显著高于结构基线 {base_short}'
                   f'（要求 ≥ +{MIN_SUT_MARGIN}）')
        return okc, why

    if not eval_suts:
        c3 = None
        c3_reason = '未评：本轮读数只有对照臂（versionblind/closed），链长压力轴无被测对象'
        sut_buckets = {}
    else:
        for r in eval_suts:
            okc, why = _eval_c3(r)
            c3_by_arm[r['arm']] = dict(satisfied=okc, reason=why,
                                       buckets=r.get('bucket_main') or {},
                                       bucket_n=r.get('bucket_main_n') or {})
        # 预注册汇总口径：**全部被测臂**都要满足（README 写的是「主指标随链长单调退化」，
        # 没有「只看一条臂」的限定；若将来改判「至少 k 臂」，须在 README 预注册并写明 k）
        c3 = bool(c3_by_arm) and all(v['satisfied'] for v in c3_by_arm.values())
        sut_buckets = {b: {'rate': (sut.get('bucket_main') or {}).get(b),
                           'n': (sut.get('bucket_main_n') or {}).get(b)}
                       for b in (sut.get('bucket_main') or {})}
        bad_arms = [a for a, v in c3_by_arm.items() if not v['satisfied']]
        c3_reason = ('逐臂 ③：' + '；'.join(
            f'{a} {"满足" if v["satisfied"] else "不满足"}（{v["reason"]}）'
            for a, v in c3_by_arm.items())
            + f' ⇒ 汇总口径「全部被测臂满足」：{"过" if c3 else "不过"}'
            + (f'（不满足：{bad_arms}）' if bad_arms else ''))

    # ④ 自洽（2026-10-10 复核整改）：
    #   旧实现只把 readings 与 `judge_arm` 现算结果逐字段比对，而 readings 本来就是
    #   `judge_arm` 的输出 ⇒ 对「本管线生成的 calibration.json」**恒真**，唯一能触发它
    #   的是事后手改文件——它不独立验证任何东西，却占着四门之一。
    #   现在 ④ 改为**独立复核输入与读数**，三件事都必须过：
    #     (a) 每条臂的答卷**同源且完整**——manifest.keys_fp == 当前 keys 指纹、且
    #         非可推题答卷数 == n_expected（缺题/换语料重跑会当场失败，这是真会发生的
    #         管线故障，判分器在此之前只是把这类臂**静默剔除**、并不会让门不过）；
    #     (b) 九项主读数都在 [0,1]（防越界/伪造）；
    #     (c) 读数能由**磁盘上的答卷**独立复算（防陈旧 readings.json / 手改）。
    #   三件事各由不同来源（manifest / 值域 / 答卷文件）支撑，不再是把输出跟自己比。
    fresh = {r['arm']: judge_arm(r['arm'], keys, doc_norms, decoys) for r in readings}
    in_range = all(isinstance(r.get(f), (int, float)) and 0.0 <= r[f] <= 1.0
                   for r in readings for f in METRIC_FIELDS)
    # ★ issue #44-二：同源要**两把尺**都过——keys_fp（每题的值/状态/序号）＋ data_fp（语料／
    #   答案键／生成日志三份内容）。旧实现只有前者：9f31b1f 重新生成数据后语料 93/270 段已改、
    #   23 道题 reconstructible 翻转，keys_fp 却一位不变（bda3d94b7f29526a），旧卷照样判「同源」。
    same_source = all(_manifest(r['arm']).get('keys_fp') == fp
                      and _manifest(r['arm']).get('data_fp') == fp_data for r in readings)
    # ★ issue #44-四：分母随臂而异——被测臂已剔掉闭卷可猜题，须用**每行自己的** n_expected。
    complete = all(r.get('n') == (r.get('n_expected') or n_expected) for r in readings)
    repro = all(r.get(f) is not None
                and abs(float(r[f]) - float(fresh[r['arm']][f])) < 1e-9
                for r in readings for f in METRIC_FIELDS) and \
        all(r.get('n') == fresh[r['arm']]['n'] for r in readings)
    # ★ issue #41：某条臂 n=0（答卷目录里根本没卷）时不得宣布「自洽」——旧实现把它当成
    #   空集上的全称真命题，于是「判分器读错目录、什么都没判到」也会给 c4=True。
    empty_arms = [r['arm'] for r in readings if not r.get('n')]
    c4 = None if empty_arms else bool(in_range and repro and same_source and complete)
    if empty_arms:
        c4_reason = ('臂 ' + str(empty_arms) + ' 的答卷数 n=0：' + str(RUNS)
                     + ' 下没有可判的答卷（判分器与运行器读写的不是同一个目录？issue #41）')
    elif c4:
        c4_reason = '值域合法、答卷同源（keys_fp＋data_fp）完整、且读数可由答卷独立复算'
    elif not in_range:
        c4_reason = '指标值域越界'
    elif not same_source:
        c4_reason = ('答卷与当前数据不同源（manifest.keys_fp／data_fp 不符，或 manifest 缺失；'
                     'issue #44-二）')
    elif not complete:
        c4_reason = (f'答卷缺题（存在臂的主读数答卷数 < 该臂 n_expected＝{n_expected} − 已剔的'
                     f'闭卷可猜题）')
    else:
        c4_reason = '读数与答卷复算不一致（陈旧/被改写）'

    # ② 破坏方向（预注册；issue #26）
    damage_ok, damage_reason, damage_by_arm = _damage_criterion(by, sut_arm, suts)

    passed = bool(c1 and c2 and c4 and c3 is True and damage_ok is True)
    if c3 is None:
        stage = 'controls-only'
    elif damage_ok is None:
        stage = 'no-damage-arms'
    else:
        stage = 'full'
    details = (
        f'① 版本盲指纹：现值 {vb["present"] if vb else None}（要求 ≥0.5）、'
        f'历史 {vb["history"] if vb else None}、变更链 {vb["chain"] if vb else None}'
        f'（要求 ≤0.15）、现值分母 {vb_present_n}（要求 ≥{MIN_PRESENT_N}）'
        f'→ {"过" if c1 else "不过"}；'
        f'② 闭卷核心：现值 {cb["present"] if cb else None} / 历史 {cb["history"] if cb else None}'
        f' / 变更链 {cb["chain"] if cb else None}（各 ≤0.2）、答题量 {cb_n}（≥{MIN_ARM_N}）'
        f'→ {"过" if c2_agg else "不过"}；'
        f'② 闭卷逐题：可猜题 {len(chits)}/{n_main}＝{cb_hit_rate}（要求 ≤{CLOSED_MAX_HIT}，'
        f'已从被测臂主读数剔除）→ {"过" if c2_hit_ok else "不过"}；'
        f'③ 链长单调（**被测系统臂**）：{c3_reason}；结构基线 {struct}（仅诊断，不作判据）'
        f'→ {("过" if c3 else ("不过" if c3 is False else "未评"))}；'
        f'④ 读数自洽：{c4_reason} → {"过" if c4 else "不过"}；'
        f'② 破坏方向：{damage_reason} → '
        f'{("过" if damage_ok else ("不过" if damage_ok is False else "未评"))}。'
        f'（本次 limit={limit or "全量"}；阶段={stage}；'
        f'口径：可推题不进主读数，历史叙述豁免须状态判对。）')
    return dict(version_blind=dict(present=vb['present'] if vb else 0.0,
                                   history=vb['history'] if vb else 0.0,
                                   chain=vb['chain'] if vb else 0.0),
                c3_by_arm=c3_by_arm,
                damage_by_arm=damage_by_arm,
                sut_four_state=({s: (sut.get(f'four_state_{s}'),
                                     (sut.get('counts') or {}).get(f'four_state_{s}'))
                                 for s in FOUR_STATES} if sut else {}),
                sut_four_state_majority=(sut or {}).get('four_state_majority'),
                sut_timepoint=({k: (sut or {}).get(k)
                                for k in ('timepoint', 'timepoint_early', 'timepoint_late')}
                               if sut else {}),
                closed_book=(round((cb['present'] + cb['history'] + cb['chain']) / 3, 4)
                             if cb else 0.0),
                closed_hits=dict(n=len(chits), n_main=n_main, rate=cb_hit_rate,
                                 max=CLOSED_MAX_HIT, qids=sorted(chits)),
                chain_length_monotonic=bool(c3 is True),
                sut_arm=sut['arm'] if sut else None,
                sut_buckets=sut_buckets,
                gate_stage=stage,
                # ★ c4 保留三态（issue #41）：n=0 的臂上是「未评」（None），不是「过」。
                criteria=dict(c1=bool(c1), c2=bool(c2), c3=c3,
                              c4=(None if c4 is None else bool(c4)),
                              c_damage=damage_ok),
                passed=passed, details=details)


# ---------------- 自检（不调用 LLM：伪造 oracle / 对照臂 / 坏系统，验证判分器与效度门） ----------------
def _check(name: str, cond: bool, extra: str = '') -> None:
    print(f'[selftest] {name}: {"PASS" if cond else "FAIL"} {extra}')
    if not cond:
        raise AssertionError(name)


def selftest() -> None:
    """机械自检：① 判分器认得出 oracle/空答；② 变更链粒度、豁免、依据轴三条判据可被
    正反例区分；③ 效度门 ③④ 可失败（坏系统不过、好系统过、读数被改写不过）。"""
    keys, doc_norms, decoys = _corpus_index()
    corpus = _load(OUT / 'corpus.json', [])
    # ★ 新鲜 clone 里 `out/` 是空的（.gitignore）：旧实现会一路走到 `most_common(1)[0]`
    #   抛 IndexError，读者看不出「缺的是题库」。给一句能照做的提示并非零退出。
    if not keys or not corpus:
        print(f'[error] {OUT}/keys.json 或 corpus.json 不存在/为空——自检需要题库与语料。')
        print('        照 chain/README §8 把 chain/keys/keys.json、chain/keys/synth_log.json、')
        print(f'        chain/corpus/corpus.json 复制到 {OUT}/ 后重跑；')
        print('        或跑 chain/tools/tests/ 下的守卫套件（自带临时 out/，不写仓库）。')
        raise SystemExit(2)
    fp = keys_fp(keys)
    fp_data = hmb_paths.data_fp()          # ★ issue #44-二：假 manifest 也要带数据指纹
    by_seq = {(c['doc'], c['seq']): c['text'] for c in corpus}

    # ---- 单元级正反例 ----
    k_act = dict(answer=dict(value='v9', state='active', at_seq=9,
                             chain=[{'seq': 1, 'from': None, 'to': 'v1'},
                                    {'seq': 5, 'from': 'v1', 'to': 'v9'}],
                             change_chain=[{'seq': 5, 'from': 'v1', 'to': 'v9'}]))
    _check('豁免：自报 unresolved 但键为 active ⇒ 仍计滞后混淆',
           stale_confused(dict(value='v1', state='unresolved'), k_act) is True)
    k_ret = dict(answer=dict(value=None, state='retired', at_seq=5,
                             chain=[{'seq': 1, 'from': None, 'to': 'v1'},
                                    {'seq': 5, 'from': 'v1', 'to': None}],
                             change_chain=[]))
    _check('豁免：自报 retired 且键为 retired ⇒ 历史叙述豁免生效',
           stale_confused(dict(value='v1', state='retired'), k_ret) is False)
    _check('豁免：自报 retired 但键为 unresolved ⇒ 不豁免（状态须判对）',
           stale_confused(dict(value='v1', state='retired'),
                          dict(answer=dict(value='v9', state='unresolved', at_seq=9,
                                           chain=[{'seq': 1, 'from': None, 'to': 'v1'},
                                                  {'seq': 5, 'from': 'v1', 'to': 'v9'}],
                                           change_chain=[{'seq': 5, 'from': 'v1', 'to': 'v9'}]))
                          ) is True)
    _check('变更链：只列「值→值」变更即算完整（不要求 create/retire 行）',
           chain_complete(dict(chain=[{'seq': 5, 'from': 'v1', 'to': 'v9'}]), k_act) is True)
    _check('变更链：缺该次变更 ⇒ 不完整',
           chain_complete(dict(chain=[{'seq': 1, 'from': None, 'to': 'v1'}]), k_act) is False)
    _check('变更行召回：答对 0/1 行、行召回 0.0（链条仍判不完整）',
           chain_rows_hit(dict(chain=[{'seq': 1, 'from': None, 'to': 'v1'}]), k_act) == (0, 1))
    mat = (norm('猎户项目的有效期秒数由 300 改为 600，起因是压测暴露并发缺陷。'), {'A1#5'}, {5})
    _check('依据轴：quote 在材料内且 file 指向返回片段 ⇒ 命中',
           verbatim_ok(dict(basis=[{'file': 'A1#5', 'line': 5,
                                    'quote': '由 300 改为 600'}]), mat) is True)
    _check('依据轴：quote 不在材料内（别处语料）⇒ 不命中',
           verbatim_ok(dict(basis=[{'file': 'A1#5', 'line': 5,
                                    'quote': '井台边有人在打水'}]), mat) is False)
    _check('依据轴：quote 在材料内但 file/line 都不是返回片段 ⇒ 不命中',
           verbatim_ok(dict(basis=[{'file': 'A9#99', 'line': 99,
                                    'quote': '由 300 改为 600'}]), mat) is False)
    # ★ 甲-9：file 与 line 必须指向**同一个**返回片段（旧实现 ok_file or ok_line 会放行）
    mat2 = (norm('甲#1 片段一的正文内容。乙#2 片段二的正文内容。'), {'甲#1', '乙#2'}, {1, 2})
    _check('依据轴：file 命中片段 A、line 命中片段 B ⇒ 不命中（须同片段）',
           verbatim_ok(dict(basis=[{'file': '甲#1', 'line': 2,
                                    'quote': '片段一的正文内容'}]), mat2) is False)
    _check('依据轴：file 与 line 同指片段 A ⇒ 命中',
           verbatim_ok(dict(basis=[{'file': '甲#1', 'line': 1,
                                    'quote': '片段一的正文内容'}]), mat2) is True)
    # ★ 甲-4：同值异时——某值在取样点前已成立过，即便 T 之后又出现，也不算超前混淆
    k_rec = dict(answer=dict(value='vB', state='active', at_seq=3,
                             chain=[{'seq': 1, 'from': None, 'to': 'vA'},
                                    {'seq': 3, 'from': 'vA', 'to': 'vB'},
                                    {'seq': 5, 'from': 'vB', 'to': 'vA'},
                                    {'seq': 9, 'from': 'vA', 'to': 'vB'}],
                             change_chain=[]),
                 sample_at_seq=3)
    _check('超前混淆：候选值在取样点前已出现过（同值异时）⇒ 不算超前（旧实现会误判）',
           future_confused(dict(value='vA'), k_rec) is False)
    k_fut = dict(answer=dict(value='vB', state='active', at_seq=1,
                             chain=[{'seq': 1, 'from': None, 'to': 'vB'},
                                    {'seq': 9, 'from': 'vB', 'to': 'vA'}],
                             change_chain=[]),
                 sample_at_seq=1)
    _check('超前混淆：候选值仅在取样点之后才出现 ⇒ 算超前',
           future_confused(dict(value='vA'), k_fut) is True)
    # ★ 甲-5：时点问落在 unresolved 点，alt 是语料并列的可接受替代值
    k_acc = dict(answer=dict(value='X', state='unresolved', at_seq=5, accept=['Y'],
                             chain=[{'seq': 5, 'from': 'W', 'to': 'X'}], change_chain=[]),
                 sample_at_seq=5)
    _check('时点问 accept：答卷给出并列的另一取值 ⇒ 判对',
           value_correct(dict(value='Y'), k_acc) is True)
    _check('时点问 accept：alt 在后文复现也不算超前混淆',
           future_confused(dict(value='Y'), k_acc) is False)

    # ---- 端到端：伪造答卷（含材料件），跑真判分器 ----
    def oracle(k):
        seg = by_seq.get((k['doc'], k['sample_at_seq']), '')
        return dict(value=k['answer']['value'], state=k['answer']['state'],
                    at_seq=k['answer']['at_seq'], chain=k['answer']['chain'],
                    basis=[{'file': f'{k["doc"]}#{k["sample_at_seq"]}',
                            'line': k['sample_at_seq'], 'quote': seg[:40] or 'x' * 8}])

    def empty(k):
        return dict(value=None, state=None, at_seq=None, chain=[], basis=[])

    def vb_fake(k):
        """版本盲伪记忆：现值答对、历史/变更全空。"""
        if k['type'] == '现值':
            return dict(value=k['answer']['value'], state=k['answer']['state'],
                        at_seq=k['answer']['at_seq'], chain=[], basis=[])
        return empty(k)

    def bad_sut(k):
        """坏系统：答不对任何题。"""
        return empty(k)

    def good_sut(k):
        """好系统（仅用于证 ③ 可被满足）：短链答对、中/长链答错。"""
        b = _bucket(k['chain_len'])
        if b == 'short':
            return oracle(k)
        return empty(k)

    def dmg_write(k):
        """乙 坏写入：历史/变更全空（模拟丢 30% 事件）。"""
        return empty(k) if k['type'] in ('历史', '变更') else good_sut(k)

    def dmg_retrieval(k):
        """丙 坏检索：现值答不出、依据轴塌（模拟检索打乱+截断）。"""
        if k['type'] == '现值':
            return empty(k)
        a = dict(good_sut(k))
        a['basis'] = []
        return a

    def dmg_present(k):
        """丁 坏呈现：剥掉来源字段 ⇒ 依据轴塌。"""
        a = dict(good_sut(k))
        a['basis'] = []
        return a

    def only_changes(k):
        """只列「值→值」变更的系统（变更链粒度回归用）。"""
        if k['type'] == '变更':
            return dict(value=k['answer']['value'], state=k['answer']['state'],
                        at_seq=k['answer']['at_seq'],
                        chain=want_changes(k), basis=[])
        return empty(k)

    # ★ 甲-1：常数猜测器——恒输出全局最高频答案值，完全没有记忆。旧判据 ③ 只看
    #   「非增且非全等」会被它蒙过（语料结构本身随链长单调）；加绝对水平下界后必须失败。
    from collections import Counter as _C
    _mode = _C(str(k['answer']['value']) for k in keys
               if k['answer']['value'] is not None).most_common(1)[0][0]

    def const_sut(k):
        return dict(value=_mode, state='active', at_seq=None, chain=[], basis=[])

    # ★ issue #20：逐桶**缓升**的臂——短/中/长每档上升都不超过旧容差 0.05，
    #   但方向与预注册的「随链长单调退化」**相反**。旧判据（固定 tol + 非全等）会放行。
    _mainq = {}
    for k in keys:
        if not _excluded(k) and _main_ok(k, oracle(k)) is not None:
            _mainq.setdefault(_bucket(k['chain_len']), []).append(k['qid'])
    _want = {'short': 0.86, 'mid': 0.90, 'long': 0.94}
    _right = {q for b, qs in _mainq.items() for q in qs[:round(_want[b] * len(qs))]}

    def rising_sut(k):
        return oracle(k) if k['qid'] in _right else empty(k)

    # ★ issue #24：不认主体、不认槽位——把本文档**所有链**的「值→值」行全列上
    _by_doc = {}
    for k in keys:
        _by_doc.setdefault(k['doc'], []).append(k)

    def dump_sut(k):
        if k['type'] != '变更':
            return empty(k)
        rows = []
        for k2 in _by_doc[k['doc']]:
            for r in (k2['answer'].get('chain') or []):
                if r.get('from') is not None and r.get('to') is not None:
                    rows.append({'seq': r['seq'], 'from': r['from'], 'to': r['to']})
        return dict(value=None, state=None, at_seq=None, chain=rows, basis=[])

    # ★ issue #43-二：破坏臂的基底取自它自己的 `manifest.base_arm`。下面用「零破坏的副本」
    #   与「整机全空的答卷」两组臂复现旧实现的两处放行（假基底 / 只查映射指标）。
    _ABS = [k['qid'] for k in keys
            if k.get('type') == '状态归属' and k['answer'].get('state') == 'absent']

    def _tweak_absent(fn, frac):
        """只动「状态归属·absent」这批小题的自报 state（与破坏机制无关的小样本字段）。"""
        hit = set(_ABS[:round(len(_ABS) * frac)])

        def g(k):
            a = fn(k)
            if k['qid'] in _ABS:
                a = dict(a, state='absent' if k['qid'] in hit else 'retired')
            return a
        return g

    # ★ issue #43-三：时点方向/定位三臂
    def tp_early(k):
        a = oracle(k)
        if k['type'] == '时点' and isinstance(k['answer'].get('at_seq'), int):
            a['at_seq'] = k['answer']['at_seq'] - 1
        return a

    def tp_late(k):
        a = oracle(k)
        if k['type'] == '时点' and isinstance(k['answer'].get('at_seq'), int):
            a['at_seq'] = k['answer']['at_seq'] + 3
        return a

    def tp_noseq(k):
        """值/状态全对、`at_seq` 一律 null ⇒ 时点定位全错（旧实现仍判满分）。"""
        a = oracle(k)
        if k['type'] == '时点':
            a['at_seq'] = None
        return a

    # ★ issue #43-四：同一 seq 下枚举全部 (from, to) 组合
    def enum_sut(k):
        if k['type'] != '变更':
            return empty(k)
        rows_ = []
        for r in (k['answer'].get('chain') or []):
            for f in (None, r.get('from'), r.get('to'), 'x'):
                for t in (None, r.get('from'), r.get('to'), 'y'):
                    rows_.append({'seq': r['seq'], 'from': f, 'to': t})
        return dict(value=None, state=None, at_seq=None, chain=rows_, basis=[])

    def fake(name, fn, manifest=None):
        d = RUNS / f'chain_{name}' / 'sut' / 'out'
        d.mkdir(parents=True, exist_ok=True)
        (RUNS / f'chain_{name}' / 'retrieval').mkdir(parents=True, exist_ok=True)
        for k in keys:
            (d / f'{k["qid"]}.json').write_text(
                json.dumps(fn(k), ensure_ascii=False), encoding='utf-8')
            # 材料件：给本题 doc 的全部 seq（让 oracle 的 quote 可回源）
            mat = [{'cid': f'{k["doc"]}#{c["seq"]}', 'text': c['text'], 'score': 1.0}
                   for c in corpus if c['doc'] == k['doc']]
            (RUNS / f'chain_{name}' / 'retrieval' / f'{k["qid"]}.json').write_text(
                json.dumps({'qid': k['qid'], 'material': mat}, ensure_ascii=False),
                encoding='utf-8')
        m = {'arm': name, 'phase': 'ask', 'keys_fp': fp, 'data_fp': fp_data,
             'n_questions': len(keys), 'limit': 0, 'calib_sample': 0}
        m.update(manifest or {})
        (RUNS / f'chain_{name}' / 'manifest.json').write_text(
            json.dumps(m, ensure_ascii=False), encoding='utf-8')

    names = ['selftest_oracle', 'selftest_empty', 'selftest_vb', 'selftest_changes',
             'selftest_bad', 'selftest_good', 'selftest_const', 'selftest_rising',
             'selftest_dump', 'selftest_tp_early', 'selftest_tp_late',
             'selftest_tp_noseq', 'selftest_enum',
             'damage_bad_write', 'damage_bad_retrieval', 'damage_bad_present']
    fake('selftest_oracle', oracle)
    fake('selftest_empty', empty)
    fake('selftest_vb', vb_fake)
    fake('selftest_changes', only_changes)
    fake('selftest_bad', bad_sut)
    fake('selftest_good', good_sut)
    fake('selftest_const', const_sut)
    fake('selftest_rising', rising_sut)
    fake('selftest_dump', dump_sut)
    fake('selftest_tp_early', tp_early)
    fake('selftest_tp_late', tp_late)
    fake('selftest_tp_noseq', tp_noseq)
    fake('selftest_enum', enum_sut)
    fake('damage_bad_write', dmg_write)
    fake('damage_bad_retrieval', dmg_retrieval)
    fake('damage_bad_present', dmg_present)
    try:
        rows = {r['arm']: r for r in judge_arms(names, write=False)}
        o = rows['selftest_oracle']
        _check('oracle：现值/历史/变更链/行召回/四态/缘由/依据轴 全 1.0',
               o['present'] == 1.0 and o['history'] == 1.0 and o['chain'] == 1.0
               and o['chain_row_recall'] == 1.0
               and o['four_state'] == 1.0 and o['reason'] == 1.0 and o['verbatim'] == 1.0,
               f'(present={o["present"]}, history={o["history"]}, chain={o["chain"]}, '
               f'row_recall={o["chain_row_recall"]}, reason={o["reason"]}, '
               f'verbatim={o["verbatim"]})')
        e = rows['selftest_empty']
        _check('空答：九项主读数全 0',
               all(e[f] == 0.0 for f in METRIC_FIELDS))
        v = rows['selftest_vb']
        _check('版本盲指纹：现值 1.0 / 历史 0.0 / 变更链 0.0',
               v['present'] == 1.0 and v['history'] == 0.0 and v['chain'] == 0.0,
               f'(present={v["present"]}, history={v["history"]}, chain={v["chain"]})')
        ch = rows['selftest_changes']
        _check('只列变更（不含 create/retire）的系统：变更链完整率 1.0、行召回 1.0',
               ch['chain'] == 1.0 and ch['chain_row_recall'] == 1.0,
               f'(chain={ch["chain"]}, row_recall={ch["chain_row_recall"]})')

        # ---- 效度门可失败性 ----
        ctl = ('selftest_vb', 'selftest_empty')
        bad = calibration([v, e, rows['selftest_bad']], sut_arm='selftest_bad',
                          control_arms=ctl)
        _check('③ 可失败：坏系统（全 0）→ chain_length_monotonic=False',
               bad['chain_length_monotonic'] is False and bad['passed'] is False,
               f'(sut={bad["sut_arm"]}, buckets={bad["sut_buckets"]})')
        good = calibration([v, e, rows['selftest_good']], sut_arm='selftest_good',
                           control_arms=ctl)
        _check('③ 可满足：好系统（短链对/长链错）→ ③ 过；但无破坏臂 ⇒ ② 未评、passed=False',
               good['chain_length_monotonic'] is True and good['passed'] is False
               and good['criteria']['c_damage'] is None
               and good['gate_stage'] == 'no-damage-arms',
               f'(sut={good["sut_arm"]}, buckets={good["sut_buckets"]}, '
               f'stage={good["gate_stage"]})')
        # 仅对照臂（工作流 calibrate 现状）→ ③ 不可评、明确报「未评」，且不宣布过门
        only_ctl = calibration([v, e], control_arms=ctl)
        _check('③ 不可评：只有对照臂 → c3=None / gate_stage=controls-only / passed=False',
               only_ctl['criteria']['c3'] is None
               and only_ctl['chain_length_monotonic'] is False
               and only_ctl['gate_stage'] == 'controls-only'
               and only_ctl['sut_arm'] is None
               and only_ctl['passed'] is False
               and '未评' in only_ctl['details'])
        # ④ 可失败：读数被改写
        tampered = [dict(v, present=0.99), e, rows['selftest_good']]
        t = calibration(tampered, sut_arm='selftest_good', control_arms=ctl)
        _check('④ 可失败：读数与答卷复算不一致 → 不过',
               t['criteria']['c4'] is False and t['passed'] is False)
        # ★ 甲-1：常数猜测器（单调但绝对水平极低）必须让 ③ 失败
        cs = rows['selftest_const']
        cst = calibration([v, e, cs], sut_arm='selftest_const', control_arms=ctl)
        _check('③ 可失败：常数猜测器（桶率随链长单调但水平极低）→ 不过',
               cst['chain_length_monotonic'] is False and cst['passed'] is False,
               f'(buckets={cst["sut_buckets"]})')
        # ★ issue #24：整篇列出（不认主体/槽位）不得判「链完整」
        dp = rows['selftest_dump']
        _check('变更链：整篇列出别链的行 → chain 判不过、精度读数低',
               dp['chain'] < 0.2 and dp['chain_precision'] < 0.6
               and dp['chain_row_recall'] == 1.0
               and o['chain'] == 1.0 and o['chain_precision'] == 1.0,
               f'(dump chain={dp["chain"]}, precision={dp["chain_precision"]}；'
               f'oracle chain={o["chain"]}, precision={o["chain_precision"]})')
        # ★ issue #20：逐桶缓升（每档 < 0.05）必须让 ③ 失败——方向与预注册相反
        rs = rows['selftest_rising']
        rst = calibration([v, e, rs], sut_arm='selftest_rising', control_arms=ctl)
        _bm = [rs['bucket_main'].get(b) for b in ('short', 'mid', 'long')
               if rs['bucket_main'].get(b) is not None]
        _check('③ 可失败：逐桶缓升（每档 <0.05，方向相反）→ 不过',
               rst['chain_length_monotonic'] is False and rst['passed'] is False,
               f'(buckets={_bm})')
        # ★ issue #44-三：③ 的方向判据此前只看**点估计**（首尾差 ≥ 0.05、相邻回升 ≤ 抽样噪声），
        #   于是两类臂能蒙过：U 形（0.80→0.60→0.75，首尾差恰 0.05）与平坦臂（真值三桶相同，
        #   靠抽样噪声凑出 0.05 的差）。现在须过单侧两比例检验（z ≥ 1.645）。
        _n = {'short': 138, 'mid': 98, 'long': 29}          # 本轨真实桶样本量
        _u_bm = {'short': 0.80, 'mid': 0.60, 'long': 0.75}
        _u_bk = {'short': 110, 'mid': 59, 'long': 22}
        _u_ok, _u_why, _u_det = c3_direction(_u_bm, _n, _u_bk)
        _check('③ 可失败：U 形臂（0.80→0.60→0.75，首尾差恰 0.05）→ 不过',
               _u_ok is False,
               f'(drop={_u_det["drop"]}, z_drop={_u_det["z_drop"]}, rises={_u_det["rises"]})')
        _f_bm = {'short': 0.80, 'mid': 0.80, 'long': 0.80}
        _f_bk = {'short': 110, 'mid': 78, 'long': 23}
        _f_ok, _f_why, _f_det = c3_direction(_f_bm, _n, _f_bk)
        _check('③ 可失败：平坦臂（三桶同 0.80）→ 不过',
               _f_ok is False,
               f'(drop={_f_det["drop"]}, z_drop={_f_det["z_drop"]})')
        import random as _rndmod
        _rnd = _rndmod.Random(20261015)
        _npass = 0
        _TRIALS = 2000
        for _t in range(_TRIALS):
            _bm, _bn, _bk = {}, {}, {}
            for _b, _m in _n.items():
                _k = sum(1 for _ in range(_m) if _rnd.random() < 0.80)
                _bn[_b], _bk[_b], _bm[_b] = _m, _k, round(_k / _m, 4)
            _ok_t, _, _ = c3_direction(_bm, _bn, _bk)
            _npass += 1 if _ok_t else 0
        # 真值三桶相同 ⇒ 「随链长退化」为假，判过即**假阳性**。旧判据（点估计）实测 24.2%，
        # 新判据（单侧两比例检验 α=0.05）实测 ≈5.6%（有限样本离散 + 合并比例法的近似），
        # 这里卡 ≤ 10%。
        _check(f'③ 可失败：真值三桶同为 0.80 的 {_TRIALS} 次二项抽样 → 判过 {_npass}/{_TRIALS}'
               f'（旧判据 24.2%，新判据要求 ≤ 10%）',
               _npass <= _TRIALS // 10,
               f'({_npass}/{_TRIALS} = {100 * _npass / _TRIALS:.1f}%)')
        _fd = 0.8 - 0.7500000000000001                    # = 0.04999999999999993
        _check(f'③ 浮点：首尾差 {_fd!r} 视为达标（≥ MIN_DROP − {DROP_EPS}）——'
               '旧实现逐位比较会判「差一点」',
               _fd >= MIN_DROP - DROP_EPS and _fd < MIN_DROP)
        # ★ issue #44-四：闭卷臂逐题命中 18% ⇒ ② 不过（旧实现只看三个聚合率，判过）
        _cq = [k for k in keys if not _excluded(k)]
        _nc = int(round(0.18 * len(_cq)))
        _hitq = {x['qid'] for x in _cq[:_nc]}

        def closed18(k):
            """闭卷臂：18% 的题给出与答案键一致的作答，其余空答。"""
            return oracle(k) if k['qid'] in _hitq else empty(k)

        fake('selftest_closed18', closed18)
        e18 = judge_arm('selftest_closed18', keys, doc_norms, decoys)
        c18 = calibration([v, e18, rows['selftest_good']], sut_arm='selftest_good',
                          control_arms=(ctl[0], 'selftest_closed18'),
                          closed_arm='selftest_closed18')
        _check('② 可失败：闭卷臂逐题命中 18% ⇒ ② 不过（旧实现只比三个聚合率，判过）',
               c18['criteria']['c2'] is False
               and c18['closed_hits']['rate'] > CLOSED_MAX_HIT
               and c18['closed_hits']['n'] > 0,
               f'(c2={c18["criteria"]["c2"]}, closed_hits={c18["closed_hits"]["n"]}/'
               f'{c18["closed_hits"]["n_main"]}={c18["closed_hits"]["rate"]}, '
               f'present={e18["present"]}, history={e18["history"]}, chain={e18["chain"]})')
        _g1 = judge_arm('selftest_good', keys, doc_norms, decoys)
        _g2 = judge_arm('selftest_good', keys, doc_norms, decoys,
                        skip=set(c18['closed_hits']['qids']))
        _check('② 可猜题剔出被测臂主读数：分母按命中数下调，且 n_skipped 记账',
               _g2['n'] == _g1['n'] - c18['closed_hits']['n']
               and _g2['n_skipped'] == c18['closed_hits']['n'],
               f'(n {_g1["n"]} → {_g2["n"]}，剔除 {_g2["n_skipped"]}；'
               f'命中率 {c18["closed_hits"]["rate"]})')
        # ★ issue #21：四态必须**分项**报；常数 active 臂的 retired/unresolved/absent 须为 0
        cs2 = rows['selftest_const']
        _check('四态分项：常数 active 臂的 retired/unresolved/absent 全 0（合并数非零）',
               cs2['four_state_retired'] == 0.0 and cs2['four_state_unresolved'] == 0.0
               and cs2['four_state_absent'] == 0.0
               and cs2['four_state_active'] == 1.0
               and cs2['counts']['four_state'] > 0,
               f'(active={cs2["four_state_active"]}, retired={cs2["four_state_retired"]}, '
               f'unresolved={cs2["four_state_unresolved"]}, absent={cs2["four_state_absent"]}, '
               f'合并={cs2["four_state"]}，多数类基线={cs2["four_state_majority"]})')
        oo = rows['selftest_oracle']
        _check('时点指标：oracle 的 timepoint=1.0，且早晚方向分母为 0（全对）',
               oo['timepoint'] == 1.0 and oo['counts']['timepoint'] > 0
               and oo['timepoint_early'] == 0.0 and oo['timepoint_late'] == 0.0,
               f'(timepoint={oo["timepoint"]}, n={oo["counts"]["timepoint"]})')
        # ★ issue #25：③ 须**逐臂**评，不得只评 SUT_ORDER 排第一的臂
        multi = calibration([v, e, rows['selftest_good'], rs], control_arms=ctl)
        _check('③ 逐臂评：一条单调臂 + 一条缓升臂 ⇒ c3 不过，且逐臂结论入 c3_by_arm',
               multi['criteria']['c3'] is False
               and set(multi['c3_by_arm']) == {'selftest_good', 'selftest_rising'}
               and multi['c3_by_arm']['selftest_good']['satisfied'] is True
               and multi['c3_by_arm']['selftest_rising']['satisfied'] is False,
               f'(c3={multi["criteria"]["c3"]}, by_arm={ {a: x["satisfied"] for a, x in multi["c3_by_arm"].items()} })')
        one = calibration([v, e, rows['selftest_good'], rs], sut_arm='selftest_good',
                          control_arms=ctl)
        _check('③ 显式指定单臂 ⇒ 只评该臂（诊断用），逐臂表也只含该臂',
               one['criteria']['c3'] is True
               and set(one['c3_by_arm']) == {'selftest_good'})
        # ★ issue #26：② 破坏方向——三条破坏臂齐备且方向正确 ⇒ passed 才可能为 True
        dmg = [rows['damage_bad_write'], rows['damage_bad_retrieval'],
               rows['damage_bad_present']]
        dmg_ok = calibration([v, e, rows['selftest_good']] + dmg,
                             sut_arm='selftest_good', control_arms=ctl)
        _check('② 可满足：乙/丙/丁 三条破坏臂方向正确且两两可分 ⇒ ② 过、passed=True',
               dmg_ok['criteria']['c_damage'] is True and dmg_ok['passed'] is True
               and dmg_ok['gate_stage'] == 'full',
               f'(c_damage={dmg_ok["criteria"]["c_damage"]}, stage={dmg_ok["gate_stage"]})')
        # 把「正常臂」换成一个全 0 的坏系统 ⇒ 破坏臂相对它并不下降 ⇒ ② 须不过
        dmg_bad = calibration([v, e, rows['selftest_bad']] + dmg,
                              sut_arm='selftest_bad', control_arms=ctl)
        _check('② 可失败：破坏臂相对正常臂并未下降 ⇒ ② 不过、passed=False',
               dmg_bad['criteria']['c_damage'] is False and dmg_bad['passed'] is False,
               f'(drops={ {a: d["drops"] for a, d in dmg_bad["damage_by_arm"].items()} })')
        # 只跑部分破坏臂 ⇒ 缺臂即不过
        dmg_part = calibration([v, e, rows['selftest_good'], rows['damage_bad_present']],
                               sut_arm='selftest_good', control_arms=ctl)
        _check('② 可失败：破坏臂不齐（缺乙/丙）⇒ 不过（不按「跑了一条就算过」放行）',
               dmg_part['criteria']['c_damage'] is False and dmg_part['passed'] is False)
        # ★ issue #43-三：时点方向——`tp_early = tp_late = []` 曾使两向读数恒等。
        te, tl, tn = (rows['selftest_tp_early'], rows['selftest_tp_late'],
                      rows['selftest_tp_noseq'])
        _check('时点方向：全答早 ⇒ early=1.0/late=0.0；全答晚 ⇒ 0.0/1.0（旧实现两向恒等 0.5/0.5）',
               te['timepoint_early'] == 1.0 and te['timepoint_late'] == 0.0
               and tl['timepoint_early'] == 0.0 and tl['timepoint_late'] == 1.0,
               f'(早臂 {te["timepoint_early"]}/{te["timepoint_late"]}，'
               f'晚臂 {tl["timepoint_early"]}/{tl["timepoint_late"]})')
        _check('时点定位：值/状态全对但 at_seq 全错 ⇒ timepoint=0.0（旧实现给满分）',
               tn['timepoint'] == 0.0 and tn['counts']['timepoint'] > 0,
               f'(timepoint={tn["timepoint"]}, n={tn["counts"]["timepoint"]})')
        # ★ issue #43-四：多列判据从「seq 属不属于本链」收紧到「(seq, from, to) 是不是本链的行」
        en = rows['selftest_enum']
        _check('变更链：同 seq 下枚举全部 (from,to) ⇒ chain 判不过、精度低（旧口径一行都不算多列）',
               en['chain'] == 0.0 and en['chain_precision'] < 0.6
               and o['chain'] == 1.0 and o['chain_precision'] == 1.0,
               f'(enum chain={en["chain"]}, precision={en["chain_precision"]})')
        # ★ issue #43-二①：破坏臂的基底取自它自己的 manifest.base_arm（runner 写的），
        #   而不是 SUT_ORDER 排第一的臂。三条臂＝ selftest_good 的**零破坏副本**，
        #   只在「状态归属·absent」这批小题上答法不同（与破坏机制无关）。旧实现拿
        #   sut_arm（selftest_oracle）当基底 ⇒ 读出 0.4+ 的假下降、又靠那个小样本字段
        #   拿到「两两可分」⇒ c_damage=True。
        fake('damage_bad_write', _tweak_absent(good_sut, 1.0), {'base_arm': 'selftest_good'})
        fake('damage_bad_retrieval', _tweak_absent(good_sut, 0.5), {'base_arm': 'selftest_good'})
        fake('damage_bad_present', good_sut, {'base_arm': 'selftest_good'})
        r_copy = {r['arm']: r for r in judge_arms(names, write=False)}
        d_copy = calibration([v, e, rows['selftest_oracle'], r_copy['damage_bad_write'],
                              r_copy['damage_bad_retrieval'], r_copy['damage_bad_present']],
                             sut_arm='selftest_oracle', control_arms=ctl)
        _check('② 可失败：零破坏副本（基底写在各自 manifest 里）⇒ 不过',
               d_copy['criteria']['c_damage'] is False and d_copy['passed'] is False
               and all(d.get('base') == 'selftest_good'
                       for d in d_copy['damage_by_arm'].values()),
               f'(bases={ {a: d.get("base") for a, d in d_copy["damage_by_arm"].items()} })')
        # ★ issue #43-二②③：三条**全空答卷**的破坏臂——映射指标全 0（相对任何基底都「下降」），
        #   只在 absent 小题上答法不同。旧实现据此判 c_damage=True；新判据须否掉：
        #   ① 特异性——破坏须有指向，不得整机一起塌；② 可分度只在映射指标并集上算。
        fake('damage_bad_write', _tweak_absent(empty, 1.0), {'base_arm': 'selftest_good'})
        fake('damage_bad_retrieval', _tweak_absent(empty, 0.0), {'base_arm': 'selftest_good'})
        fake('damage_bad_present', _tweak_absent(empty, 0.5), {'base_arm': 'selftest_good'})
        r_emp = {r['arm']: r for r in judge_arms(names, write=False)}
        d_emp = calibration([v, e, rows['selftest_good'], r_emp['damage_bad_write'],
                             r_emp['damage_bad_retrieval'], r_emp['damage_bad_present']],
                            sut_arm='selftest_good', control_arms=ctl)
        _check('② 可失败：三条全空答卷（只在小样本字段上「可分」）⇒ 不过',
               d_emp['criteria']['c_damage'] is False and d_emp['passed'] is False,
               f'(drops={ {a: d["drops"] for a, d in d_emp["damage_by_arm"].items()} }, '
               f'kept={ {a: d.get("unmapped_kept") for a, d in d_emp["damage_by_arm"].items()} })')
        # 复原三条破坏臂为「方向正确」的版本（供后续用例与清理口径一致）
        fake('damage_bad_write', dmg_write)
        fake('damage_bad_retrieval', dmg_retrieval)
        fake('damage_bad_present', dmg_present)
        # ★ 甲-2：④ 独立于 judge_arm 复算——manifest 指纹不符（不同源）须让 ④ 失败
        mf = RUNS / 'chain_selftest_good' / 'manifest.json'
        bak = mf.read_text(encoding='utf-8')
        try:
            mf.write_text(json.dumps({'arm': 'selftest_good', 'keys_fp': 'deadbeef',
                                      'limit': 0}, ensure_ascii=False), encoding='utf-8')
            ns = calibration([v, e, rows['selftest_good']], sut_arm='selftest_good',
                             control_arms=ctl)
            _check('④ 可失败：答卷与当前 keys 不同源（manifest.keys_fp 不符）→ 不过',
                   ns['criteria']['c4'] is False and ns['passed'] is False
                   and '不同源' in ns['details'])
        finally:
            mf.write_text(bak, encoding='utf-8')
    finally:
        # 自检产物不留在 runs/ 里（否则缺省扫描会把它当成真臂）
        import shutil
        for name in names:
            shutil.rmtree(RUNS / f'chain_{name}', ignore_errors=True)
    print('[selftest] 全部通过')


def main() -> None:
    ap = argparse.ArgumentParser(description='状态链召回探针 · 机械判分器（零 LLM）')
    ap.add_argument('--arms', default='',
                    help='逗号分隔的臂名（缺省＝扫描 runs/chain_* 下已存在的臂）')
    ap.add_argument('--selftest', action='store_true',
                    help='用伪造答卷（oracle/对照臂/坏系统）自检判分器与效度门，不调用 LLM')
    ap.add_argument('--gate', action='store_true',
                    help='判分后**在全部现存臂上**评一次校准零号并写 out/calibration.json'
                         '（③ 需要被测系统臂的答卷，故须在被测臂答完之后跑）')
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if a.arms:
        arms = [x.strip() for x in a.arms.split(',') if x.strip()]
    else:
        arms = sorted(p.name[len('chain_'):] for p in RUNS.glob('chain_*')
                      if (p / 'sut' / 'out').is_dir())
    # ★ issue #41：读不到任何答卷时**非零退出**。旧实现打一个空表 `[]`、rc=0，第三方
    #   照 chain/README §8 跑完 bm25 全链会以为「判分跑过了、只是没有臂」。
    if not arms:
        print('[error] ' + str(RUNS) + ' 下没有找到任何答卷（runs/chain_*/sut/out/）。')
        print('        判分器与运行器共用同一份解析（chain/tools/hmb_paths.py）；')
        print('        请确认答卷目录：HMB_RUNS=<dir>，或先跑 chain/tools/probe_runner.py。')
        sys.exit(2)
    rows = judge_arms(arms)
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    if not rows:
        print('[error] ' + str(len(arms)) + ' 条臂全部被剔出整臂读数（无可用答卷）；')
        print('        明细见 out/readings_excluded.json（答卷根目录 ' + str(RUNS) + '）')
        sys.exit(2)
    if a.gate:
        excluded = _load(OUT / 'readings_excluded.json', [])
        if excluded:
            print('[gate] 以下臂被剔出整臂读数（指纹不符/截断/缺题）：'
                  + '；'.join(f"{r['arm']}（{r['exclude_reason']}）" for r in excluded))
        calib = calibration(rows)
        (OUT / 'calibration.json').write_text(
            json.dumps(calib, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"[gate] calibration.json 已写出：passed={calib['passed']}｜"
              f"判据 {calib['criteria']}｜③ 被测臂={calib['sut_arm']}")
        print('[gate] ' + calib['details'])


if __name__ == '__main__':
    main()
