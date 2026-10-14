# -*- coding: utf-8 -*-
"""memos 适配器 —— **未随本库发布**（桩）。

真实实现需要外部服务：MemOS 服务（Neo4j 图库 + 向量库）。
真实实现只能做到逻辑隔离（共用同一图库，仅 cube 名不同）。

本桩存在的意义：让 probe_runner.py --arm memos 的失败面从一句
ModuleNotFoundError 变成可读的「缺什么、怎么补」。想跑这一臂：
  ① 自备上述服务；② 照 base.py 的契约写适配器（类名 MemOSAdapter 不变）；
  ③ 或改用开箱可跑的参考臂 --arm bm25。
"""
from __future__ import annotations

from ._stub import AdapterNotPublished, not_published
from .base import MemoryAdapter

NAME = "memos"
SERVICE = "MemOS 服务（Neo4j 图库 + 向量库）"
HINT = "真实实现只能做到逻辑隔离（共用同一图库，仅 cube 名不同）。"


class MemOSAdapter(MemoryAdapter):
    name = NAME

    def __init__(self, *args, **kwargs):
        raise not_published(NAME, SERVICE, HINT)

    def ingest(self, chapters: list[dict]) -> dict:
        raise not_published(NAME, SERVICE, HINT)

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        raise not_published(NAME, SERVICE, HINT)


__all__ = ["MemOSAdapter", "AdapterNotPublished", "NAME", "SERVICE"]
