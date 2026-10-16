# -*- coding: utf-8 -*-
"""状态链召回探针 · 运行器（多臂写入 + 统一契约作答）

命令行：`--phase ingest|ask|calibrate --arm <名> [--limit N] [--shard i/n]`
臂：bm25 / lingshu / openviking / mem0 / memos / hindsight / versionblind / closed

并行：`--shard i/n` 按题在 keys.json 里的下标取模分片（同一臂多片并发写同一个
  `sut/out/`，qid 唯一 ⇒ 文件名不重叠；并集＝不分片结果集，见 `--selftest-shard`）。
  分片模式下 calibrate **不覆盖** `out/calibration.json`（写 `calibration_shard_iOfn.json`），
  全量门由跑完全部分片后的 `probe_judge.py --gate` 从合并答卷写出。

口径（一句话一件）
  · harness：优先用作者本地的完整 harness（`membench/dist/记忆系统对比_v1.0/harness/`，
    六家真实适配器），没有则回落**随库发布**的参考 harness（`chain/harness/`：契约 ＋
    bm25 参考实现 ＋ 五家桩）——第三方 clone 即可跑 bm25 臂（issue #35）。
    只 import、不改这些文件；接线照 `run_e2e.py`。强制发布版：`HMB_HARNESS=repo`。
  · versionblind ＝ 自实现的「只留每条链最新值」伪记忆：写入时按 synth_log 把每条链
    折叠成一条「当前状态」记录（历史全部丢弃），检索仍用同一 BM25。
  · closed ＝ 不给任何材料作答（闭卷基线）。契约＝`CLOSED_SYS`：**只把规则 1 换成
    「无材料，凭先验给最可能的值」**，其余四条与 `CHAIN_SYS` 逐字相同（issue #44-四）——
    照旧契约（规则 1 要求「材料里没有的就不要编」）等于指示模型不作答，闭卷 ≈ 0 由指令
    决定、说明不了题目可猜。它猜对的题由判分器 `closed_hits` 逐题记录并剔出被测臂主读数。
  · 隔离：所有写入用新身份 `chain`（MDCG_RUN_TAG=_chain、mem0 库目录 mem0_chain、
    memos user/cube、hindsight bank、OV 前缀 chain_novel）。
    ★ 隔离强度的诚实口径（2026-10-10 复核整改·甲-7）：并非所有臂都能做到**物理隔离**。
    memos 只改 MEMOS_USER/MEMOS_CUBE，实际经同一 MemOS 服务写进**同一 Neo4j 图库**
    （仅 cube 名不同）——是**逻辑隔离**，不是物理隔离；其余臂（lingshu 独立 MDCG_ROOT、
    mem0 独立 qdrant 目录、hindsight 独立 bank、OV 独立 workspace/端口）才是物理隔离。
    故本运行器对 memos 臂要求显式 `--memos-shared-graph` 认下「与既有 memos 库共用
    Neo4j 图库」这一事实，且**全流程绝不调用 ad.reset()**（memos_adapter.reset 会对集合
    neo4j_vec_db 发 {'filter':{}} 全删，一旦调用会清空既有 memos 向量）。
    ★ OV 例外：OpenViking 的 workspace 是**全进程共享**的单一目录
    （ov.conf:storage.workspace），一个 server 只有一个 workspace，无法按身份隔离；
    且适配器的 `_kill_port_owner` 会杀掉占用所设端口的进程。故本运行器**拒绝**直接
    在共享 workspace 上跑 OV 臂：要么传 `--ov-port <专用端口>`（如 19433；本运行器会把
    ov.conf 复制到隔离目录、改 workspace 与 port），要么在 `--ov-shared-workspace` 下
    显式认下「该臂与既有 OV 库共用 workspace」这一事实。
  · 作答契约：{"qid","value","state","at_seq","chain","basis","confidence"}，生成器
    ＝ common.LLM（deepseek-flash，thinking 开）。
  · 产物：`runs/chain_<arm>/`（sut/out/<qid>.json、retrieval/<qid>.json、manifest.json）；
    manifest 记 `keys_fp`（当前答案键指纹）与 `limit`，判分器据此把「非当前 keys / --limit
    截断」的答卷剔出整臂读数（见 probe_judge.judge_arms）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out'
ROOT = HERE.parent.parent                                   # 仓根
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import hmb_paths                                            # noqa: E402

# harness / 答卷目录的解析**只此一处**（chain/tools/hmb_paths.py，issue #41）：
#   · 仓内 `chain/harness/` 是**随库发布的参考 harness**（common.py ＋ 适配器契约
#     ＋ bm25 参考实现 ＋ 五家桩）——第三方 clone 即可跑 bm25 臂，见 chain/README §8；
#   · `membench/dist/记忆系统对比_v1.0/harness/` 是作者本地的完整 harness（六家真实
#     适配器与题库切换，不在发布面）。
#   默认顺序＝本地优先（作者既有行为不变）；第三方没有本地 harness 时自动回落仓内发布版。
#   要强制用发布版：环境变量 HMB_HARNESS=repo。
#   ★ 判分器 `probe_judge.py` 读同一份解析结果——两边不再各写一个 RUNS（issue #41）。
HARNESS = hmb_paths.harness_dir()[0]
RUNS = hmb_paths.runs_dir()                                  # 答卷根目录（与判分器同源）
if HARNESS is None:
    raise SystemExit('找不到 harness（common.py）。已找过：\n  '
                     + '\n  '.join(str(p) for p in (hmb_paths.HARNESS_LOCAL,
                                                    hmb_paths.HARNESS_REPO))
                     + '\n本库已随库发布参考 harness：chain/harness/（见 chain/README §8）。')
for p in (str(HERE), str(HARNESS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import random                                                 # noqa: E402

import common as C                                          # noqa: E402

ARMS = ('bm25', 'lingshu', 'openviking', 'mem0', 'memos', 'hindsight',
        'versionblind', 'closed')

# ★ 预注册的**破坏臂**（README §6 第 2 条「破坏方向」；issue #26：此前完全没有实现）：
#   乙 bad_write（坏写入：随机丢 30% 事件）／丙 bad_retrieval（坏检索：打乱+截断）／
#   丁 bad_present（坏呈现：剥来源字段）。臂名与 probe_judge.DAMAGE_ARMS 一一对应。
DAMAGE_KINDS = ('bad_write', 'bad_retrieval', 'bad_present')
DAMAGE_DROP_RATE = 0.30      # 乙：丢掉的事件比例
DAMAGE_KEEP_RATE = 0.60      # 丙：打乱后保留的材料比例
DAMAGE_SEED = 20261013       # 固定种子（可复现）


def damage_arm_name(kind: str) -> str:
    return f'damage_{kind}'


def damage_chapters(chapters: list[dict], kind: str,
                    seed: int = DAMAGE_SEED) -> list[dict]:
    """乙 坏写入：按固定种子随机丢弃 30% 的语料块（模拟事件没写进去）。

    ★ 这是**纯函数**（输入→输出，无副作用），故可在无 LLM 的环境里单测；
      端到端跑破坏臂仍需要被测系统可用（见 README §6）。
    """
    if kind != 'bad_write':
        return list(chapters)
    rnd = random.Random(seed)
    keep = [c for c in chapters if rnd.random() >= DAMAGE_DROP_RATE]
    return keep or list(chapters)


def damage_material(material: list[dict], kind: str,
                    seed: int = DAMAGE_SEED) -> list[dict]:
    """丙 坏检索：打乱材料顺序并只留 60%；丁 坏呈现：剥掉 cid/score（来源字段）。

    纯函数，理由同 `damage_chapters`。
    """
    if kind == 'bad_retrieval':
        rnd = random.Random(seed)
        out = [dict(m) for m in material]
        rnd.shuffle(out)
        n = max(1, int(len(out) * DAMAGE_KEEP_RATE))
        return out[:n]
    if kind == 'bad_present':
        return [{k: v for k, v in m.items() if k == 'text'} for m in material]
    return [dict(m) for m in material]
IDENTITY = 'chain'
# ★ issue #44-五：有**外部持久库**的臂（其余臂的库在进程内，随进程消失）。
PERSISTENT_ARMS = ('lingshu', 'openviking', 'mem0', 'memos', 'hindsight')


def store_tag(arm: str, damage: str = '') -> str:
    """该次运行使用的**库身份**（issue #44-五）。

    旧实现各臂的库身份只由常量 `IDENTITY='chain'` 派生（lingshu `MDCG_RUN_TAG=_chain`、
    OpenViking 前缀 `chain_novel`、mem0 目录 `mem0_chain/qdrant`、memos cube `memos_chain_cube`、
    hindsight `bank=novel_chain`），而运行器**从不 reset**（契约如此）⇒ 干净臂与三条破坏臂
    共用同一个库：乙 bad_write 被追加进干净臂已经灌满的库（等于没破坏），反过来先跑乙则
    干净臂读到的是被破坏过的库，重跑干净臂还会重复灌入。现在库身份随破坏档分叉。
    """
    return IDENTITY + (f'_{damage}' if damage else '')


def _ledger_path() -> Path:
    return RUNS / '_store_ledger.json'


def store_guard(arm: str, store: str, d: Path) -> None:
    """写入前确认该库**没被之前的运行写过**；非空即中止（issue #44-五）。

    两道检查：
      ① 本地账本 `RUNS/_store_ledger.json`：本运行器每次 ingest 记一条（库身份 + 块数 +
         答卷目录）。库身份已按破坏档分叉，账本命中的都是「同一个库被写第二次」；
      ② 适配器自报：实现了可选的 `count()`／`is_empty()` 时直接问它。
    二选一命中即中止，除非显式 `--allow-nonempty-store`。
    """
    if arm not in PERSISTENT_ARMS or not store:
        return
    if ALLOW_NONEMPTY_STORE:
        log(f'  ⚠ --allow-nonempty-store：跳过「库 {store} 是否为空」的检查')
        return
    led = _read_json(_ledger_path())
    prev = led.get(store)
    if prev:
        raise SystemExit(
            f'[store] 拒绝写入：库 {store} 已被之前的运行写过（{prev.get("at")}，'
            f'{prev.get("n_chapters")} 块，答卷目录 {prev.get("dir")}）。\n'
            '        运行器不调用 ad.reset()（各臂共享既有库时会误删数据），故不能替你清库。\n'
            '        处理：① 换一个库身份（改 --damage／臂名）；② 手工清库后重跑；'
            '③ 确认要往非空库追加，则显式加 --allow-nonempty-store。')
    # 适配器自报（可选契约）：实现了就问一句，避免账本之外的既有数据被追加
    try:
        ad, closer, _note = make_adapter(arm, store)
    except SystemExit:
        return
    except Exception as e:                                # noqa: BLE001
        # 适配器建不起来（如桩报「未随库发布」）⇒ 无从自报，跳过这一道（账本那一道仍生效）。
        log(f'  （库非空自检跳过：适配器不可用 {type(e).__name__}）')
        return
    try:
        cnt = None
        if hasattr(ad, 'count'):
            cnt = int(ad.count())
        elif hasattr(ad, 'is_empty'):
            cnt = 0 if ad.is_empty() else 1
        if cnt:
            raise SystemExit(
                f'[store] 拒绝写入：适配器自报库 {store} 非空（count={cnt}）。'
                '确认要追加则加 --allow-nonempty-store。')
    except SystemExit:
        raise
    except Exception as e:                                   # noqa: BLE001
        log(f'  （库非空自检跳过：{type(e).__name__}: {str(e)[:80]}）')
    finally:
        if closer:
            closer()


def store_commit(arm: str, store: str, d: Path, n_chapters: int) -> None:
    """把本次 ingest 记进本地账本（供下一次运行判「库是不是非空」）。"""
    if arm not in PERSISTENT_ARMS or not store:
        return
    led = _read_json(_ledger_path())
    led[store] = dict(arm=arm, n_chapters=n_chapters, dir=str(d),
                      at=time.strftime('%Y-%m-%d %H:%M:%S'))
    write_json(_ledger_path(), led)


K = 6                     # 常规问型的 top-k 块数
MATERIAL_CHARS = 14000    # 常规问型的材料字数上限
# ★ 变更问要「按序号列出每一次变更前后的值」：一条 45–60 事件的链跨 45–60 个 seq，
#   单 seq 约 400 字 ⇒ 6 块/14k 字物理上装不下，chain_complete 会变成地板指标。
#   故变更问单独放大检索面（拿得下才谈得上「记不记得住」）。
CHAIN_K = 60
CHAIN_MATERIAL_CHARS = 80000

CHAIN_SYS = (
    '你是被评测的记忆理解系统。下面给你**检索到的材料片段**（可能不完整、可能乱序），'
    '以及一个关于「主体 × 属性 × 值 × 生效序号」状态链的问题。\n'
    '规则：\n'
    '1. 只依据给定材料作答，不得使用你自己的知识；材料里没有的就不要编。\n'
    '2. 输出一个 JSON 对象（不要输出任何 JSON 之外的内容），字段：\n'
    '   {"qid":"...", "value":"<该题所问的值；若不存在或已撤销填 null>",\n'
    '    "state":"active|retired|unresolved|absent",\n'
    '    "at_seq": <该值生效的序号，整数或 null>,\n'
    '    "chain": [{"seq":1,"from":null,"to":"..."}],\n'
    '    "basis": [{"file":"<片段头里的 doc#seq>","line":<序号>,"quote":"<逐字原文>"}],\n'
    '    "confidence":"certain|probable|unknown"}\n'
    '3. chain 只在「变更问」里需要完整填写（按序号列出每一次变更前后的值）；'
    '其它问型留空数组 []。\n'
    '4. basis 的 quote 必须是材料里的**逐字原文**（不改写、不拼接），1–3 条；'
    'file 填片段头里的 doc#seq，line 填该片段头的序号。\n'
    '5. 不要输出任何 JSON 之外的内容。'
)

# ★ issue #44-四：闭卷臂的契约＝**只改规则 1**。规则 1 原为「只依据给定材料作答……材料里
#   没有的就不要编」——空材料下这是「不要作答」的指令，于是闭卷 ≈ 0 由指令决定，
#   不能说明题目不可猜。换成「凭先验给最可能的值」后，闭卷臂真的在猜，它猜对的题才是可猜题。
#   其余四条（JSON 字段、chain 用法、basis 用法、只输出 JSON）与 `CHAIN_SYS` 逐字相同。
CLOSED_SYS = CHAIN_SYS.replace(
    '1. 只依据给定材料作答，不得使用你自己的知识；材料里没有的就不要编。',
    '1. 本次**不提供任何材料**：请凭你自己的先验知识给出最可能的值，不要因为「没有材料」'
    '就留空——每道题都必须给出一个具体的猜测（value/state/at_seq 都要填），'
    '猜不出也请给出你认为最可能的那个。')


def log(*a) -> None:
    print(*a, flush=True)


# OV 专用端口/workspace（由命令行注入；见 _check_ov_isolation）
OV_PORT = os.environ.get('OV_PORT', '')
# ★ issue #44-五：向非空库写入须显式认下（见 store_guard）
ALLOW_NONEMPTY_STORE = False
OV_SHARED_OK = False
# memos 与既有库共用 Neo4j 图库（逻辑隔离）——须显式认下（见 _check_memos_isolation）
MEMOS_SHARED_OK = False


def _check_memos_isolation() -> None:
    """跑 memos 臂前先证隔离：它做不到物理隔离，须显式认下。

    MemOS 走同一台服务写**同一 Neo4j 图库**（仅 cube 名不同），其余臂都是物理隔离
    （独立目录/bank/端口）。若把 memos 的「独立 user/cube」当成「独立库」，报告会误以为
    chain 臂读数与既有 memos 库互不影响。故要求 `--memos-shared-graph` 显式认下；
    且本运行器全流程不调 ad.reset()（它会全删共享 Qdrant 集合，见模块头）。
    """
    if MEMOS_SHARED_OK:
        log('  memos: ⚠ 已显式认下「与既有 memos 库共用 Neo4j 图库」（仅 cube 名不同，'
            '逻辑隔离；本运行器不调用 reset，报告须标注不可比）')
        return
    raise SystemExit(
        '拒绝在未认下共享图库的情况下跑 memos 臂：\n'
        '  · memos 只改 user/cube，写入落在**同一 Neo4j 图库**（逻辑隔离，非物理隔离）；\n'
        '  · 其余臂均为物理隔离（独立 MDCG_ROOT / qdrant 目录 / bank / workspace）。\n'
        '  请传 --memos-shared-graph 显式认下污染（报告须标注该臂读数与既有库互不影响不成立）。')


def _setup_ov_isolated(ova, port: str) -> None:
    """把 OV 适配器指到**专用 conf / 专用 workspace**（端口≠19333 时才调用）。

    原 ov.conf 的 storage.workspace 是全进程共享的既有 OV 库目录；这里复制一份到
    ASCII 路径，改 workspace 与 server.port，再把适配器的模块级 OV_CONF/OV_HOME/OV_LOG
    指过去——适配器 `_start_server` 起的是这份 conf，写入落在隔离目录里。
    """
    src = ova.OV_CONF
    cfg = json.loads(src.read_text(encoding='utf-8'))
    data_dir = ROOT / 'membench' / 'ovdata'
    conf = data_dir / 'ov_chain.conf'
    ws = data_dir / 'openviking_chain'
    cfg['storage']['workspace'] = str(ws).replace('\\', '/')
    cfg['server']['port'] = int(port)
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    ova.OV_CONF = conf
    ova.OV_HOME = data_dir / 'ov_chain_home'
    ova.OV_LOG = ova.OV_HOME / 'server.log'
    ova.OV_DATA = ws
    # ★ 适配器的 PORT/BASE_URL/__init__ 默认值都是 **def/import 时求值**的，改模块全局
    #   不会影响已捕获的默认参数：故既要改 PORT（_kill_port_owner/_stop_server 用它），
    #   又必须在构造时显式传 base_url（见 make_adapter）。
    ova.PORT = int(port)
    ova.BASE_URL = f'http://127.0.0.1:{port}'
    log(f'  openviking: 隔离 conf={conf}｜workspace={ws}｜port={port}')


def _check_ov_isolation() -> None:
    """跑 OV 臂前先证隔离：端口必须是专用端口（≠默认 19333），否则报错退出。

    理由：OpenViking 的 workspace 是全进程共享的单一目录、一个端口一个 workspace；
    适配器还会杀掉端口占用进程。若在默认端口/默认 workspace 上跑，这一臂会把
    chain_novel 写进既有 OV 库、并可能复用/杀掉别的轮次的 server——
    `probe_runner` 文档里「绝不触碰既有库」对这一臂不成立。故须显式给专用端口；
    `--ov-shared-workspace` 是唯一（且须自觉）的例外。
    """
    default_port = '19333'
    if OV_PORT and OV_PORT != default_port:
        os.environ['OV_PORT'] = OV_PORT
        log(f'  openviking: 专用端口 {OV_PORT}（OV_PORT 已设；server 用该端口自己的 workspace）')
        return
    if OV_SHARED_OK:
        log('  openviking: ⚠ 已显式认下「与既有 OV 库共用 workspace/端口 '
            f'{OV_PORT or default_port}」——本臂读数与既有库互相污染，报告须标注')
        return
    raise SystemExit(
        '拒绝在 OpenViking 默认端口/共享 workspace 上跑 chain 臂：\n'
        '  · 该 workspace 是全进程共享的单目录，chain_novel 会写进既有 OV 库；\n'
        '  · 适配器会杀掉任何占用 19333 的进程（可能踩到别的轮次）。\n'
        '  二选一：① 设 OV_PORT=<专用端口>（如 19433）并让该端口的 server 用专用 workspace；\n'
        '           ② 传 --ov-shared-workspace 显式认下污染（报告须标注不可比）。')


def write_json(p: Path, o) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding='utf-8')


def keys_fp(keys: list[dict]) -> str:
    """当前答案键指纹（与 probe_judge.keys_fp 同口径）——写进 manifest，供判分器判同源。"""
    h = hashlib.sha256()
    for k in keys:
        h.update(json.dumps([k['qid'], k['type'], k['answer'].get('value'),
                             k['answer'].get('state'), k['answer'].get('at_seq')],
                            ensure_ascii=False, sort_keys=True).encode('utf-8'))
    return h.hexdigest()[:16]


def run_dir(arm: str) -> Path:
    # ★ 用 hmb_paths 的解析结果，**不读 harness 自己的 `C.RUNS`**（issue #41）：
    #   答卷目录必须与 probe_judge.py 读的那个逐字相同，而 harness 是随库/本机两套，
    #   各自的 RUNS 定义不一定同步。这里以判分器同源的那份为准。
    d = RUNS / f'chain_{arm}'
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------- 语料 ----------------
def load_corpus() -> list[dict]:
    """读 out/corpus.json；补 `title`＝cid（harness 的 chunk_chapters 需要 title 字段）。"""
    raw = json.loads((OUT / 'corpus.json').read_text(encoding='utf-8'))
    return [dict(c, title=c.get('title') or c['cid']) for c in raw]


def load_keys() -> list[dict]:
    return json.loads((OUT / 'keys.json').read_text(encoding='utf-8'))


def versionblind_corpus() -> list[dict]:
    """把语料折叠成「每条链只剩最新值」的伪记忆（历史全部丢弃）。

    从 synth_log 逐链取**最后一次事件**，渲染成一条「当前状态」记录；每个 doc 一章。
    """
    import synth as S
    lg = json.loads((OUT / 'synth_log.json').read_text(encoding='utf-8'))
    by_doc: dict[str, list[str]] = {}
    for c in lg['chains']:
        evs = c['events']
        last = evs[-1]
        unit = S.UNIT[c['kind']]
        if last['to'] is None:
            line = f"{c['subject']} 的{c['slot']}当前已撤销，不再保留取值。"
        else:
            line = (f"{c['subject']} 的{c['slot']}当前为 {last['to']}"
                    f"（第 {last['seq']} {unit}生效）。")
        by_doc.setdefault(c['doc'], []).append(line)
    return [dict(cid=f'{doc}#latest', doc=doc, title=f'{doc}#latest', seq=0,
                 text=''.join(lines)) for doc, lines in by_doc.items()]


# ---------------- 适配器装配（隔离身份 chain） ----------------
def make_adapter(arm: str, store: str | None = None):
    """返回 (adapter, closer, note)。

    `store`＝本次运行的**库身份**（issue #44-五）。省略时退回常量 `IDENTITY`（兼容旧调用），
    但运行器自己的三条路径（do_ingest／do_ask／store_guard）一律显式传入，干净臂与破坏臂
    因此各自一个库。
    """
    store = store or IDENTITY
    if arm in ('bm25', 'versionblind'):
        from adapters.naive_bm25 import BM25Adapter
        return BM25Adapter(), None, '本地内存库（进程内，无外部服务）'
    if arm == 'closed':
        return None, None, '闭卷基线：不发检索、材料恒空'
    if arm == 'lingshu':
        os.environ['MDCG_RUN_TAG'] = f'_{store}'             # 库路径隔离 runs/lingshu_<store>/mdcg
        from adapters.lingshu_adapter import LingshuAdapter
        return LingshuAdapter(), None, f'MDCG_RUN_TAG=_{store}'
    if arm == 'openviking':
        _check_ov_isolation()
        import adapters.openviking_adapter as ova
        base = ova.BASE_URL
        if OV_PORT and OV_PORT != '19333':
            _setup_ov_isolated(ova, OV_PORT)
            base = f'http://127.0.0.1:{OV_PORT}'
        ova.NOVEL_URI = f'viking://resources/{store}_novel'      # 新前缀，不动既有库
        # ★ 注意：OpenVikingAdapter.retrieve 的 target_uri 是**默认参数**（def 时求值），
        #   改模块全局不会影响它 —— 调用时必须显式传 target_uri（见 retrieve_for）。
        #   同理 base_url 的默认值也是 def 时求值的，隔离端口必须显式传。
        return ova.OpenVikingAdapter(base_url=base), None, f'OV 前缀 {ova.NOVEL_URI}'
    if arm == 'mem0':
        from adapters.mem0_adapter import Mem0Adapter
        sdir = RUNS / f'mem0_{store}' / 'qdrant'
        ad = Mem0Adapter(store_dir=str(sdir))
        ad.USER = store
        return ad, None, f'mem0 库 {sdir}'
    if arm == 'memos':
        _check_memos_isolation()
        os.environ['MEMOS_USER'] = f'novel_{store}'
        os.environ['MEMOS_CUBE'] = f'memos_{store}_cube'
        import adapters.memos_adapter as ma
        import importlib
        importlib.reload(ma)          # 模块级读 env；同一进程内先跑过别臂时须重载
        return ma.MemOSAdapter(), None, \
            f'memos user/cube {ma.USER}/{ma.CUBE}（逻辑隔离·共享 Neo4j 图库）'
    if arm == 'hindsight':
        from adapters.hindsight_adapter import HindsightAdapter
        ad = HindsightAdapter(bank=f'novel_{store}')
        return ad, ad.close, f'hindsight bank novel_{store}'
    raise SystemExit(f'未知臂：{arm}')


# ---------------- ingest ----------------
def _read_json(p: Path) -> dict:
    """读 JSON；不存在或解析失败一律返回 {}（manifest 属诊断面，不因它中断跑批）。"""
    try:
        o = json.loads(p.read_text(encoding='utf-8'))
        return o if isinstance(o, dict) else {}
    except Exception:                                     # noqa: BLE001
        return {}


def do_ingest(arm: str, d: Path, limit: int, damage: str = '') -> dict:
    chapters = versionblind_corpus() if arm == 'versionblind' else load_corpus()
    if damage:                                   # ★ 乙：坏写入（丢 30% 语料块）
        before = len(chapters)
        chapters = damage_chapters(chapters, damage)
        log(f'  [damage={damage}] 语料块 {before} → {len(chapters)}'
            f'（丢 {100 * (1 - len(chapters) / max(before, 1)):.0f}%）')
    if limit:
        docs = sorted({c['doc'] for c in chapters})
        # --limit 在 ingest 阶段按 doc 截断无意义，这里只做整体提示；题量截断在 ask 阶段
        pass
    t0 = time.time()
    store = store_tag(arm, damage)          # ★ issue #44-五：库身份随破坏档分叉
    store_guard(arm, store, d)              # 非空即中止（除非 --allow-nonempty-store）
    if arm == 'closed':
        st = {'note': '闭卷臂无库可写'}
        note = ''
    else:
        ad, closer, note = make_adapter(arm, store)
        if arm == 'lingshu':
            titled = [dict(ch, text=f"# {ch['cid']}\n{ch['text']}") for ch in chapters]
            ad._cid_by_title = {ch['cid']: ch['cid'] for ch in chapters}
            st = ad.ingest(titled)
            st['title_rule'] = '每块盖 `# <cid>` 一级标题'
        elif arm == 'openviking':
            st = ad.ingest(chapters, processing_mode='vectors_only')
        elif arm == 'memos':
            st = ad.ingest(chapters)
        else:
            st = ad.ingest(chapters)
        if closer:
            closer()
    manifest = dict(arm=(damage_arm_name(damage) if damage else arm),
                    identity=IDENTITY, phase='ingest', dir=str(d),
                    harness=hmb_paths.harness_label(),
                    base_arm=arm, damage=damage,
                    n_chapters=len(chapters),
                    chars=sum(len(c['text']) for c in chapters),
                    ingest=st, generator=C.GEN_MODEL,
                    # ★ issue #44-二/五：库身份与三份身份指纹（数据／适配器／harness）
                    store=store, store_note=note, persistent=arm in PERSISTENT_ARMS,
                    data_fp=hmb_paths.data_fp(),
                    adapter=hmb_paths.adapter_fp(arm),
                    harness_files=hmb_paths.harness_fp(),
                    elapsed=round(time.time() - t0, 1))
    store_commit(arm, store, d, len(chapters))
    write_json(d / 'manifest.json', manifest)
    # ★ issue #43-一B：ask 阶段的 manifest 会覆盖上面这份，ingest 读数（乙丢了多少块）另存。
    write_json(d / 'manifest_ingest.json', manifest)
    log(f'  ingest 完成：{json.dumps(st, ensure_ascii=False)[:300]}（{manifest["elapsed"]}s）')
    return manifest


# ---------------- ask ----------------
def build_prompt(qid: str, question: str, material: list[dict]) -> list[dict]:
    blocks = []
    for i, m in enumerate(material, 1):
        cid = m.get('cid') or '未知'
        blocks.append(f'【片段{i} · {cid}】\n{m.get("text", "")}')
    user = ('## 检索到的材料\n\n' + ('\n\n'.join(blocks) if blocks else '（无材料）') +
            f'\n\n## 问题（{qid}）\n\n{question}\n\n'
            '请按契约输出 JSON（qid 填 ' + qid + '）。')
    return [{'role': 'system', 'content': CHAIN_SYS}, {'role': 'user', 'content': user}]


def build_closed_prompt(qid: str, question: str) -> list[dict]:
    """闭卷臂的提问：**只改第 1 条**的输出契约 ＋ 空材料（issue #30 ＋ issue #44-四）。

    ★ issue #30：旧实现把答案模板逐字写进提示词（`"value":null, "state":"absent"`），
    闭卷臂照抄模板即可在「答案为 null」的题上白拿分——首轮报告里 closed 臂的四态
    0.512 与版本盲臂 0.508 几乎相同（照抄模板应得 ≈ 0.512，正好是「absent 在四态里的
    占比」），这是**照着答案模板抄**，不是「闭卷能猜」。现在不给任何字段取值。
    ★ issue #44-四：但「只给空材料、契约逐字照旧」还不够——`CHAIN_SYS` 规则 1 是
    「只依据给定材料作答……材料里没有的就不要编」，value 字段说明是「若不存在或已撤销
    填 null」，空材料下模型被**明确指示不作答**，于是「闭卷 ≈ 0」主要由指令决定，
    不能说明题目不可猜。现在闭卷臂单独一份 `CLOSED_SYS`：只把规则 1 换成「无材料，
    凭先验给出最可能的值」，其余四条逐字相同。这样闭卷臂才真的在猜——它猜对的题就是
    可猜题（由 `probe_judge.closed_hits` 逐题记录并剔出主读数）。
    """
    return [{'role': 'system', 'content': CLOSED_SYS},
            {'role': 'user', 'content': build_prompt(qid, question, [])[1]['content']}]


def parse_chain_answer(raw: str, qid: str) -> dict:
    """解析被测系统的作答；`_json_ok` 表示**真的解析出了一个 JSON 对象**。

    ★ issue #43-五：旧实现 `o['_json_ok'] = bool(m)`——`m` 只是「正则找到了一对花括号」，
      `json.loads` 失败（尾逗号、未加引号的键、单引号…）时仍为 True，于是「占位卷剔除」
      漏掉了最常见的 JSON 失败：40% 题尾逗号的臂 `n_error=0`、`complete=True`，
      以 present 0.6102 进 readings（同答案正常解析是 1.0）。现在以解析结果为准。
    """
    s = (raw or '').strip()
    m = re.search(r'\{.*\}', s, re.S)
    o = None
    if m:
        try:
            o = json.loads(m.group(0))
        except Exception:
            o = None
    json_ok = isinstance(o, dict)
    if not json_ok:
        o = {}
    o['qid'] = qid
    o.setdefault('value', None)
    o.setdefault('state', None)
    o.setdefault('at_seq', None)
    if not isinstance(o.get('chain'), list):
        o['chain'] = []
    if not isinstance(o.get('basis'), list):
        o['basis'] = []
    o.setdefault('confidence', 'unknown')
    o['_json_ok'] = json_ok
    return o


def retrieve_for(arm: str, ad, query: str, k: int) -> list[dict]:
    """检索接线：OV 的 target_uri 是默认参数（def 时求值），必须显式传新前缀。"""
    if arm == 'openviking':
        import adapters.openviking_adapter as ova
        return ad.retrieve(query, k=k, target_uri=ova.NOVEL_URI) or []
    return ad.retrieve(query, k=k) or []


def parse_shard(s: str) -> tuple[int, int] | None:
    """`--shard i/n` → (i, n)；空串 → None。i 从 0 起。"""
    s = (s or '').strip()
    if not s:
        return None
    try:
        i, n = s.split('/')
        i, n = int(i), int(n)
    except Exception:
        raise SystemExit(f'--shard 格式应为 i/n（如 0/4）：{s!r}')
    if n < 1 or not (0 <= i < n):
        raise SystemExit(f'--shard 越界：i={i} n={n}（要求 0≤i<n）')
    return i, n


def shard_keys(keys: list[dict], shard: tuple[int, int] | None) -> list[dict]:
    """按题在 keys.json 里的下标做 `index % n == i` 过滤（分片并发用）。

    同一臂的多个分片写同一个 `sut/out/`，因 qid 唯一、下标不重叠 ⇒ 答卷文件名互不重叠；
    全部跑完后合并集合＝不分片的结果集（见 `--selftest-shard`）。
    """
    if not shard:
        return keys
    i, n = shard
    return [k for idx, k in enumerate(keys) if idx % n == i]


def do_ask(arm: str, d: Path, limit: int, shard: tuple[int, int] | None = None,
           damage: str = '') -> dict:
    keys_all = load_keys()
    keys = shard_keys(keys_all, shard)
    if limit:
        keys = keys[:limit]
    chapters = versionblind_corpus() if arm == 'versionblind' else load_corpus()
    # ★ issue #43-一B：进程内臂（bm25／versionblind）的库只活在内存里，ingest 阶段丢掉的语料块
    #   随进程一起没了；旧实现 ask 前用 `load_corpus()` **原样**重建，乙（坏写入）于是变成空操作
    #   ——实测 642 题检索结果与干净 bm25 逐题相同、命中里 1744/7254 来自「本应被丢弃」的块。
    #   现在 ask 前按同一个 `damage` 再套一次 `damage_chapters`（同一固定种子 ⇒ 同一批块）。
    if damage == 'bad_write':
        before = len(chapters)
        chapters = damage_chapters(chapters, damage)
        log(f'  [damage={damage}] ask 前重建进程内库：语料块 {before} → {len(chapters)}')
    store = store_tag(arm, damage)          # ★ issue #44-五：库身份随破坏档分叉
    ad = None
    if arm != 'closed':
        ad, closer, note = make_adapter(arm, store)
        if arm in ('bm25', 'versionblind'):                 # 进程内库：ask 前必须重建
            ad.ingest(chapters)
        elif arm == 'lingshu':
            ad._cid_by_title = {ch['cid']: ch['cid'] for ch in chapters}
    # issue #51-D7: the thinking switch is declared **at the call site** (the default
    # is now False, see common.LLM). The generator arm does want thinking, so say so.
    llm = C.LLM(thinking=True)
    (d / 'sut' / 'out').mkdir(parents=True, exist_ok=True)
    (d / 'retrieval').mkdir(parents=True, exist_ok=True)
    ok = err = 0
    per_q = {}
    t0 = time.time()
    for i, q in enumerate(keys, 1):
        qid = q['qid']
        # ★ 变更问要整条链的前后值：单独放大检索面（见模块头 CHAIN_K/CHAIN_MATERIAL_CHARS）
        is_chain_q = q['type'] == '变更'
        k = CHAIN_K if is_chain_q else K
        cap = CHAIN_MATERIAL_CHARS if is_chain_q else MATERIAL_CHARS
        try:
            if arm == 'closed':
                hits = []
            else:
                hits = retrieve_for(arm, ad, q['question'], k)
            material = []
            used = 0
            for h in hits:
                t = h.get('text') or ''
                if used + len(t) > cap:
                    t = t[:max(0, cap - used)]
                if not t.strip():
                    continue
                material.append({'cid': h.get('cid'), 'text': t, 'score': h.get('score')})
                used += len(t)
                if used >= cap:
                    break
            # ★ issue #43-一C：破坏**之前**的那一份另存 `material_full`。判分器的依据轴
            #   要拿它取 cid/seq——丁（坏呈现）剥的正是 cid，若判分器只读被剥过的那份，
            #   则任何答卷的 verbatim 都恒为 0，「丁的下降」量到的是判分器自己丢了来源。
            material_full = [dict(m) for m in material]
            if damage:                           # ★ 丙/丁：坏检索 / 坏呈现
                material = damage_material(material, damage)
            write_json(d / 'retrieval' / f'{qid}.json',
                       {'qid': qid, 'query': q['question'], 'k': k,
                        'material_chars_cap': cap, 'damage': damage,
                        'hits_returned': len(hits), 'hits': hits,
                        'material': material, 'material_full': material_full})
            prompt = (build_closed_prompt(qid, q['question']) if arm == 'closed'
                      else build_prompt(qid, q['question'], material))
            raw = llm.chat(prompt)
            ans = parse_chain_answer(raw, qid)
            ans['_n_material'] = len(material)
            write_json(d / 'sut' / 'out' / f'{qid}.json', ans)
            per_q[qid] = {'hits': len(hits), 'material': len(material),
                          'json_ok': ans['_json_ok']}
            ok += 1
            if i % 20 == 0 or i == len(keys):
                log(f'  [{i}/{len(keys)}] 作答完成（{time.time()-t0:.0f}s，tokens={llm.tokens}）')
        except Exception as e:                              # noqa: BLE001
            err += 1
            write_json(d / 'sut' / 'out' / f'{qid}.json',
                       {'qid': qid, 'value': None, 'state': None, 'at_seq': None,
                        'chain': [], 'basis': [], 'confidence': 'unknown',
                        '_error': f'{type(e).__name__}: {e}'})
            log(f'  [{i}/{len(keys)}] {qid} 失败：{type(e).__name__}: {str(e)[:120]}')
    # ★ issue #43-一B：ingest 阶段写的 manifest 不能就此丢掉——ask 阶段的 manifest 覆盖了它，
    #   于是 `n_chapters`（乙到底丢了多少块）在盘上无处可查。ingest 的那份另存一份。
    ing = _read_json(d / 'manifest_ingest.json')
    manifest = dict(arm=(damage_arm_name(damage) if damage else arm),
                    identity=IDENTITY, phase='ask', dir=str(d),
                    harness=hmb_paths.harness_label(),
                    base_arm=arm, damage=damage,
                    n_questions=len(keys), ok=ok, errors=err,
                    llm_calls=llm.calls, llm_tokens=llm.tokens,
                    generator=C.GEN_MODEL, k=K, material_chars_cap=MATERIAL_CHARS,
                    chain_k=CHAIN_K, chain_material_chars_cap=CHAIN_MATERIAL_CHARS,
                    keys_fp=keys_fp(keys_all), limit=limit,
                    store=store, persistent=arm in PERSISTENT_ARMS,
                    data_fp=hmb_paths.data_fp(),
                    adapter=hmb_paths.adapter_fp(arm),
                    harness_files=hmb_paths.harness_fp(),
                    shard=(f'{shard[0]}/{shard[1]}' if shard else ''),
                    n_questions_all=len(keys_all),
                    calib_sample=int(bool(limit)),
                    n_chapters=ing.get('n_chapters'),
                    chars=ing.get('chars'),
                    ingest=ing.get('ingest'),
                    elapsed=round(time.time() - t0, 1))
    write_json(d / 'manifest.json', manifest)
    log(f'  ask 完成：{ok}/{len(keys)} 题，{llm.calls} 次调用 / {llm.tokens} tokens'
        f'（{manifest["elapsed"]}s）')
    return manifest


# ---------------- calibrate ----------------
def do_calibrate(arms: list[str], limit: int, shard: tuple[int, int] | None = None) -> dict:
    for arm in arms:
        log(f'=== calibrate · {arm} ===')
        d = run_dir(arm)
        do_ingest(arm, d, limit)
        do_ask(arm, d, limit, shard)
    # ★ 破坏臂（乙/丙/丁）不是独立系统，而是**对同一个被测系统的三种破坏**：
    #   以第一条被测系统臂为基底各跑一次，臂名 damage_<kind>（见 README §6 第 2 条）。
    base = next((a for a in arms if a not in ('versionblind', 'closed')), None)
    damage_names = []
    if base:
        for kind in DAMAGE_KINDS:
            name = damage_arm_name(kind)
            damage_names.append(name)
            log(f'=== calibrate · 破坏臂 {name}（基底 {base}）===')
            dd = run_dir(name)
            do_ingest(base, dd, limit, damage=kind)
            do_ask(base, dd, limit, shard, damage=kind)
    import probe_judge
    # ★ issue #43-一A：破坏臂**跑完却不进判分**——旧实现只把用户给的臂名传给 `judge_arms`，
    #   `damage_<kind>` 不在其中，`_damage_criterion` 于是走「没有破坏臂 ⇒ 未评」分支，
    #   `c_damage` 恒为 None（实测 damage_by_arm={}）。跑了的臂必须一并判。
    readings = probe_judge.judge_arms(list(arms) + damage_names)
    calib = probe_judge.calibration(readings, limit=limit)
    if shard:
        # ★ 分片模式下**不写 out/calibration.json**：本片的读数只覆盖 1/n 的题，
        #   若覆盖全量文件会被误当成整臂门读数。写分片专用文件；全量门由跑完全部分片后
        #   的 `probe_judge.py --gate` 从合并答卷写出。
        p = OUT / f'calibration_shard_{shard[0]}of{shard[1]}.json'
        write_json(p, calib)
        log(f'  （分片模式：本片读数写 {p.name}，不覆盖 calibration.json）')
    else:
        write_json(OUT / 'calibration.json', calib)
        log(f'  calibration.json 已写出：passed={calib["passed"]}｜'
            f'判据 {calib["criteria"]}｜③ 被测臂={calib["sut_arm"]}')
    log('  注：③（链长单调退化）**只在被测系统臂上评**——只跑 versionblind+closed 两个'
        '对照臂时 ③ 无可评对象，passed 必为 false（这不是 bug，是效度门不再恒真）。')
    return calib


def selftest_shard() -> None:
    """分片机械自检（不调用 LLM、不调外部服务）：分片答卷**文件名**互不重叠、并集＝全集。

    两层验证：
      ① 逻辑层：`shard_keys` 对 n=2/3/4 的分片 qid 列表，交集空、并集=全集；
      ② 文件层（对应编排侧 `--shard 0/3` / `--shard 1/3` 的真实落盘）：在临时目录里
         按两片各自写一遍 `sut/out/<qid>.json`，断言两片文件名集合交集为空、并集等于
         不分片时的全集——即同一臂多片并发写同一个 `sut/out/` 不会互相覆盖。
    """
    keys = load_keys()
    qids = [k['qid'] for k in keys]
    full_names = {f'{q}.json' for q in qids}
    for n in (2, 3, 4):
        parts = [[k['qid'] for k in shard_keys(keys, (i, n))] for i in range(n)]
        union = [q for p in parts for q in p]
        inter = set(parts[0]).intersection(*[set(p) for p in parts[1:]]) if n > 1 else set()
        ok_disjoint = not inter
        ok_union = sorted(union) == sorted(qids) and len(union) == len(qids)
        print(f'[shard] n={n}：分片 {[len(p) for p in parts]}｜'
              f'交集空={ok_disjoint}｜并集=全集={ok_union}')
        if not (ok_disjoint and ok_union):
            raise AssertionError(f'分片自检失败 n={n}')

    # ② 文件层：真实落盘（临时目录），核对文件名交集/并集
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='chain_shard_selftest_'))
    try:
        outdir = tmp / 'sut' / 'out'
        outdir.mkdir(parents=True, exist_ok=True)
        name_sets = []
        for i in range(3):
            names = set()
            for k in shard_keys(keys, (i, 3)):
                fn = f'{k["qid"]}.json'
                (outdir / fn).write_text('{}', encoding='utf-8')
                names.add(fn)
            name_sets.append(names)
        on_disk = {p.name for p in outdir.iterdir() if p.is_file()}
        ok_disjoint = not (name_sets[0] & name_sets[1])
        ok_union = on_disk == full_names
        print(f'[shard] 文件层：--shard 0/3 ∩ --shard 1/3 = '
              f'{len(name_sets[0] & name_sets[1])} 个文件（应 0）｜'
              f'三片合并文件数 {len(on_disk)} = 全集 {len(full_names)}：{ok_union}')
        if not (ok_disjoint and ok_union):
            raise AssertionError('文件层分片自检失败（文件名交集非空或合并≠全集）')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('[shard] 分片自检全部通过（逻辑层 + 文件层）')


def main() -> None:
    ap = argparse.ArgumentParser(description='状态链召回探针 · 多臂运行器')
    ap.add_argument('--phase', choices=('ingest', 'ask', 'calibrate'),
                    help='运行阶段（--selftest-shard 时可不给）')
    ap.add_argument('--arm', default='',
                    help='臂名（逗号分隔；calibrate 缺省=versionblind,closed）')
    ap.add_argument('--limit', type=int, default=0, help='只跑前 N 题（0=全部）')
    ap.add_argument('--damage', default='', choices=('',) + DAMAGE_KINDS,
                    help='以 --arm 为基底跑**破坏臂**（乙 bad_write／丙 bad_retrieval／'
                         '丁 bad_present）；臂名写作 damage_<kind>，供效度门 ② 使用')
    ap.add_argument('--shard', default='', help='分片 i/n（如 0/4；按 keys.json 下标取模）')
    ap.add_argument('--selftest-shard', action='store_true',
                    help='分片机械自检（不调 LLM，不写答卷）：交集空、并集=全集')
    ap.add_argument('--ov-port', default='',
                    help='OpenViking 专用端口（≠19333；隔离要求，见 _check_ov_isolation）')
    ap.add_argument('--ov-shared-workspace', action='store_true',
                    help='显式认下「OV 臂与既有库共用 workspace」（读数不可比，报告须标注）')
    ap.add_argument('--allow-nonempty-store', action='store_true',
                    help='显式认下「往已有数据的持久库里追加」（issue #44-五；默认拒绝）')
    ap.add_argument('--memos-shared-graph', action='store_true',
                    help='显式认下「memos 臂与既有库共用 Neo4j 图库」（逻辑隔离，报告须标注）')
    a = ap.parse_args()
    global OV_PORT, OV_SHARED_OK, MEMOS_SHARED_OK, ALLOW_NONEMPTY_STORE
    OV_PORT = a.ov_port
    OV_SHARED_OK = a.ov_shared_workspace
    MEMOS_SHARED_OK = a.memos_shared_graph
    ALLOW_NONEMPTY_STORE = a.allow_nonempty_store
    if a.selftest_shard:
        selftest_shard()
        return
    if not a.phase:
        raise SystemExit('--phase 必填（ingest|ask|calibrate）')
    shard = parse_shard(a.shard)

    if a.phase == 'calibrate':
        if a.damage:
            raise SystemExit('--damage 只配 --phase ingest|ask（calibrate 会自动跑三条破坏臂）')
        arms = ([x.strip() for x in a.arm.split(',') if x.strip()] if a.arm
                else ['versionblind', 'closed'])
        for x in arms:
            if x not in ARMS:
                raise SystemExit(f'未知臂：{x}')
        do_calibrate(arms, a.limit, shard)
        return

    if not a.arm or a.arm not in ARMS:
        raise SystemExit(f'--arm 必填且须为 {ARMS} 之一')
    d = run_dir(damage_arm_name(a.damage) if a.damage else a.arm)
    if a.phase == 'ingest':
        do_ingest(a.arm, d, a.limit, damage=a.damage)
    else:
        do_ask(a.arm, d, a.limit, shard, damage=a.damage)


if __name__ == '__main__':
    main()
