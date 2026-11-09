# scripts/ · 复测工具

> 三个脚本，**纯标准库**，无第三方依赖、无 API key。用于让外部人不必安装灵枢即可复测评测链。

| 脚本 | 干什么 | 需要什么 |
|---|---|---|
| `bench_common.py` | 公共件：`chapters_text`（语料按章聚合）、`cn2int`、`grade`（判分）| 语料 + 题库 |
| `bench_state_track.py` | **检索层复测**：用槽位共现推断时间桶，再在桶内核对六要素。不调模型 | 语料 + 题库 |
| `reproduce_e2e.py` | **端到端复测**：读已发布的检索明细 → 拼材料 → 生成单断言任务 → 判分 | 语料 + 题库 + 检索明细 |

## 跑法

```sh
# 检索层（确定性，秒级）
HMB=$(pwd) python scripts/bench_state_track.py
# → {"n": 552, "scope_infer_top1": 0.9928, "oracle_judge_balanced": 0.9801, ...}

# 端到端：先生成任务
python scripts/reproduce_e2e.py --task --arm top1 --out tasks_top1.jsonl
python scripts/reproduce_e2e.py --task --arm top3 --out tasks_top3.jsonl

# 你拿 tasks_*.jsonl 去问任何系统，把「是/否」填成答卷：
#   {"qid": "o001", "answers": [{"idx": 0, "answer": "是"}, {"idx": 1, "answer": false}]}

# 再判分
python scripts/reproduce_e2e.py --grade --picks my_answers.jsonl
```

## 为什么能复测：检索明细已发布

灵枢的检索需要 `md_cg`（内部库），外部机器上没有。所以仓库发布
[`readings/lingshu_retrieval_rubric92.json`](../readings/lingshu_retrieval_rubric92.json)：
**552 条断言各自的 gold 章、top-1 章、top-3 章**。你据此取原文即可，不必复现检索。

该文件由灵枢生产模块 `md_cg.scopeselect.pick_scopes` 导出，核对值：

| 指标 | 读数 |
|---|---:|
| top-1 命中率 | **0.9783** |
| top-3 命中率 | **0.9982** |

与 [三种口径与统一尺度 v2.0](../docs/灵枢实测_三种口径与统一尺度_v2.0.md) 的 97.83% / 99.82% 一致。

## ⚠ 材料粒度不同，读数不可直接互换

| 来源 | 材料 | 平均字数 |
|---|---|---:|
| `reproduce_e2e.py`（本脚本）| **整章全文** | ~5,527 字（top-1 单章）|
| 灵枢生产模块（口径 C 表里的 0.9312）| **桶内命中块** | 2,670 字 |

两者都能跑，但**材料规模差一倍**，读数不可直接相减。引用时写明用的是哪种材料。
（灵枢生产模块返回命中块而非整章，是为了控制材料规模；本脚本用整章是为了「任何人拿到就能复测」。）

## ⚠ 待补测：单断言 vs 批量判

口径 C 表里的 **0.9312（top-1）/ 0.9426（top-3）是批量判**（一次给 6 条断言）。
统一尺度提案要求**单断言**（一次 1 条），预计会下降 5–7 点，**尚未补测**。

`reproduce_e2e.py --task` 生成的正是**单断言任务**（每行一条），所以你跑出来的数就是单断言口径——
如果与 0.9312 有差距，那正是这个待补测项。