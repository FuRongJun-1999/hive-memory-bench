# -*- coding: utf-8 -*-
"""mem0 适配器 —— **未随本库发布**（桩）。

真实实现需要外部服务：Mem0（本地向量库 + LLM 抽取）。
真实实现按 store_dir 建独立 qdrant 目录，并用外部 LLM 做事实抽取。

本桩存在的意义：让 probe_runner.py --arm mem0 的失败面从一句
ModuleNotFoundError 变成可读的「缺什么、怎么补」。想跑这一臂：
  ① 自备上述服务；② 照 base.py 的契约写适配器（类名 Mem0Adapter 不变）；
  ③ 或改用开箱可跑的参考臂 --arm bm25。
"""
from __future__ import annotations

from ._stub import AdapterNotPublished, not_published
from .base import MemoryAdapter

NAME = "mem0"
SERVICE = "Mem0（本地向量库 + LLM 抽取）"
HINT = "真实实现按 store_dir 建独立 qdrant 目录，并用外部 LLM 做事实抽取。"


class Mem0Adapter(MemoryAdapter):
    name = NAME

    def __init__(self, *args, **kwargs):
        raise not_published(NAME, SERVICE, HINT)

    def ingest(self, chapters: list[dict]) -> dict:
        raise not_published(NAME, SERVICE, HINT)

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        raise not_published(NAME, SERVICE, HINT)


__all__ = ["Mem0Adapter", "AdapterNotPublished", "NAME", "SERVICE"]
