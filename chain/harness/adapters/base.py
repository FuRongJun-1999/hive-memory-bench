# -*- coding: utf-8 -*-
"""记忆系统适配器基类（harness 契约）

任何要接入对比的记忆系统，只需实现两个方法：
    ingest(chapters)             —— 写入 23 章（可一次全灌，也可逐章；实现自定）
    retrieve(query, k)           —— 返回 top-k 片段 [{'text','cid','score'}]
另有三个**可选**方法（不实现即用基类默认）：
    reset()                      —— 清空该系统的库。★ **运行器全流程不调用它**（见下方
                                    「调用面」）：库的隔离靠「库身份随破坏档分叉 + 写入前
                                    非空守卫」，不靠清库（issue #44-五）。
    count() / is_empty()         —— 库当前有多少条／是否为空。运行器在**写入前**问一句，
                                    非空即中止（除非 --allow-nonempty-store），避免往既有
                                    数据上追加（issue #44-五）。

约定：
  · retrieve 返回的 text 必须是**记忆系统自己吐出的原文片段**，不得由适配器代它改写或补写；
  · cid 能给出就给（便于检索评测），给不出填 None，评测会退回「内容包含」判定；
  · **不得替换固定生成器**（作答一律由 harness 的 LLM 完成），适配器只负责写入与检索。

★ 调用面（chain/tools/probe_runner.py 实际怎么用它——照这个写就能接上）：
  · ad.ingest(chapters)：chapters = [{"cid","title","text"}]，返回统计 dict；
    少数臂另有分支（如 OpenViking 传 processing_mode='vectors_only'），属该臂特例；
  · ad.retrieve(query, k=k)：返回 list[dict]，**允许返回空列表**；
    少数臂另有参数（如 OpenViking 的 target_uri=），属该臂特例；
  · ad.close()：可选，运行器把它当 closer 在收尾时调用；
  · ad.reset()：**运行器全流程不调用**（各臂共享既有库时会误删数据，见 chain/README §7）；
    因此库身份必须自带隔离——运行器按 `store_tag(arm, damage)` 派生（干净臂 `chain`、
    乙 `chain_bad_write`、丙 `chain_bad_retrieval`、丁 `chain_bad_present`），并把它写进
    manifest 的 `store` 字段（issue #44-五）；
  · ad.count() / ad.is_empty()：可选；实现了就会在写入前被问一次，非空即中止。
  · ad._cid_by_title：可选，部分臂用它把标题映射回 cid。

跑起来之后：python -X utf8 chain/tools/probe_runner.py --phase ingest --arm <你的臂>。
更完整的三步用法见 chain/README.md §8「用法」与 §「自备适配器」。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class MemoryAdapter(ABC):
    name: str = "unnamed"

    def reset(self) -> None:
        """清空库（默认无操作）。"""

    @abstractmethod
    def ingest(self, chapters: list[dict]) -> dict:
        """写入语料。返回统计（如 {'chunks': N} 或 {'episodes': N}）。"""

    @abstractmethod
    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        """检索 top-k → [{'text': str, 'cid': str|None, 'score': float|None}]"""

    def close(self) -> None:
        """释放资源（默认无操作）。"""
