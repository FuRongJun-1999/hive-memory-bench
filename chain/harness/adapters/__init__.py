# -*- coding: utf-8 -*-
"""记忆系统适配器。

发布面：
  · base.MemoryAdapter       —— 契约（任何系统只需实现 ingest / retrieve）
  · naive_bm25.BM25Adapter   —— 参考实现，纯标准库、无外部服务、开箱可跑

其余五家（lingshu / openviking / mem0 / memos / hindsight）是桩：
模块可 import、类名与调用面对齐，但实例化即抛 AdapterNotPublished，
写明该臂需要什么外部服务、以及自写适配器要照哪个契约。
"""

__all__ = ["base", "naive_bm25"]
