# readings/2026-11-09 · 多跳六元素 rubric_92 验证留档

对应报告：[`docs/多跳六元素rubric92_验证报告_v1.0.md`](../../docs/多跳六元素rubric92_验证报告_v1.0.md)

口径：`deepseek-flash`，`thinking={"type":"disabled"}`，`temperature=0.0`，单次运行；
题集 = `mcq/reasoning/题目_多跳六元素_rubric92_平衡掩码.json`（92 题 / 552 条断言，3 真 3 假，平衡掩码）。

## 文件

| 文件 | 内容 | 每条记录字段 |
|---|---|---|
| `rubric92_single_s552.jsonl` | **正式口径**：552 条断言 × 闭卷/仅所引章节，各自单独作答 | `qid, pi, arm(closed\|chapter), truth, got, stmt, slots, mat_len` |
| `rubric92_batch6_full.jsonl` | 原设计口径：每题 6 条一次判（闭卷 / 给全文），已弃用但留档 | `qid, arm(closed\|open), truth[6], got[6], n, hits, parse_mode` |
| `six_element476_single.jsonl` | 476 条六元素主库同口径复测（闭卷 / 仅所引章节） | `idx, qid, arm, truth, got, stmt, mat_len` |
| `judged_single.json` | 对 `rubric92_single_s552.jsonl` 的判分（`grade_rubric.py`） | TPR/TNR/平衡准确率/φ/分槽位 |
| `judged_batch6.json` | 对 `rubric92_batch6_full.jsonl` 的判分 | 整题全对率 / p vs 1/64 / 要点级 |
| `judged_476_single.json` | 对 `six_element476_single.jsonl` 的判分 | 同上 |
| `sys1/four_arms_552.jsonl` | 四臂（闭卷/所引章节/千问RAG/OpenViking）逐条作答，552×4 = 2,208 条 | `qid, pi, arm, truth, got, slots, mat_len, stmt` |
| `sys1/judged_four_arms.json` | 用 `grade_rubric.py` 对四臂独立复算 | TPR/TNR/平衡准确率/φ/分槽位 |

> 四臂判分模型为 `deepseek-chat`（与他家实测同尺），不是本目录其它批次的 `deepseek-flash`；
> 见 [千问RAG与OpenViking实测](../../docs/新推理库_千问RAG与OpenViking实测_v1.0.md)。

`got` 取值：`true`=判「是」，`false`=判「否」，`null`=未解析（本批 0 例）。

## 读数（判分器输出原文）

| 臂 | TPR | TNR | 平衡准确率 | φ | 整题全对 6/6 |
|---|---:|---:|---:|---:|---:|
| 闭卷 | 0.0% | 100.0% | 50.0% | 0.000 | 0/92 |
| 开卷·仅所引章节 | 83.7% | 90.6% | 87.1% | 0.745 | 38/92 |

476 主库同口径：闭卷 50.0%（φ=0.000）/ 开卷·仅章 74.2%（φ=0.525）——注意该库事件槽是概述式
（逐字率 0.6%），与 rubric_92 不同源，两库不可同尺并列。

## 复算

```sh
python grade_rubric.py --answers readings/2026-11-09/rubric92_single_s552.jsonl \
    --protocol single --arms closed,chapter
```
