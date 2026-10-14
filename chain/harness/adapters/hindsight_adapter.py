# -*- coding: utf-8 -*-
"""hindsight 适配器 —— **未随本库发布**（桩）。

真实实现需要外部服务：Hindsight 服务（bank 为隔离单位）。
真实实现按 bank 名隔离，并需服务端可连。

本桩存在的意义：让 probe_runner.py --arm hindsight 的失败面从一句
ModuleNotFoundError 变成可读的「缺什么、怎么补」。想跑这一臂：
  ① 自备上述服务；② 照 base.py 的契约写适配器（类名 HindsightAdapter 不变）；
  ③ 或改用开箱可跑的参考臂 --arm bm25。
"""
from __future__ import annotations

from ._stub import AdapterNotPublished, not_published
from .base import MemoryAdapter

NAME = "hindsight"
SERVICE = "Hindsight 服务（bank 为隔离单位）"
HINT = "真实实现按 bank 名隔离，并需服务端可连。"


class HindsightAdapter(MemoryAdapter):
    name = NAME

    def __init__(self, *args, **kwargs):
        raise not_published(NAME, SERVICE, HINT)

    def ingest(self, chapters: list[dict]) -> dict:
        raise not_published(NAME, SERVICE, HINT)

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        raise not_published(NAME, SERVICE, HINT)


__all__ = ["HindsightAdapter", "AdapterNotPublished", "NAME", "SERVICE"]
