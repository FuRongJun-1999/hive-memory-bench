# -*- coding: utf-8 -*-
"""lingshu 适配器 —— **未随本库发布**（桩）。

真实实现需要外部服务：灵枢私有运行时（不在发布面，需自备）。
真实实现另需本机认知图库路径与运行标签身份隔离；本库不含其代码与数据。

本桩存在的意义：让 probe_runner.py --arm lingshu 的失败面从一句
ModuleNotFoundError 变成可读的「缺什么、怎么补」。想跑这一臂：
  ① 自备上述服务；② 照 base.py 的契约写适配器（类名 LingshuAdapter 不变）；
  ③ 或改用开箱可跑的参考臂 --arm bm25。
"""
from __future__ import annotations

from ._stub import AdapterNotPublished, not_published
from .base import MemoryAdapter

NAME = "lingshu"
SERVICE = "灵枢私有运行时（不在发布面，需自备）"
HINT = "真实实现另需本机认知图库路径与运行标签身份隔离；本库不含其代码与数据。"


class LingshuAdapter(MemoryAdapter):
    name = NAME

    def __init__(self, *args, **kwargs):
        raise not_published(NAME, SERVICE, HINT)

    def ingest(self, chapters: list[dict]) -> dict:
        raise not_published(NAME, SERVICE, HINT)

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        raise not_published(NAME, SERVICE, HINT)


__all__ = ["LingshuAdapter", "AdapterNotPublished", "NAME", "SERVICE"]
