# -*- coding: utf-8 -*-
"""记忆系统适配器基类（harness 契约）

任何要接入对比的记忆系统，只需实现两个方法：
    reset()                      —— 清空该系统的库（每次运行从零开始）
    ingest(chapters)             —— 写入 23 章（可一次全灌，也可逐章；实现自定）
    retrieve(query, k)           —— 返回 top-k 片段 [{'text','cid','score'}]

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
