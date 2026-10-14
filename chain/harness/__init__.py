# -*- coding: utf-8 -*-
"""随库发布的参考 harness（外部可运行版）。

本目录是记忆系统对比 harness 的**发布子集**：第三方 clone 本库后，
`chain/tools/probe_runner.py` 可直接 import 本目录（不再 ModuleNotFoundError），
`bm25` 参考臂可开箱跑通「写入 → 检索 → 作答 → 判分」全链。

发布面（本目录）：
  · `common.py`              —— 文本归一化、切块、固定生成器客户端、产物根目录
  · `adapters/base.py`       —— 适配器契约（任何记忆系统只需实现 ingest/retrieve）
  · `adapters/naive_bm25.py` —— 参考实现（朴素 BM25，纯标准库、无外部服务）
  · `adapters/*_adapter.py`  —— 其余五家为**桩**：import 成功，实例化即报「未随库发布」

未发布面：题库切换、判分器、报告生成、各系统适配器的真实实现（需自备服务与凭据）。
自写适配器的接口约定见 `../README.md` §「自备适配器」与 `adapters/base.py` 的模块文档。
"""

__all__ = ["common", "adapters"]
