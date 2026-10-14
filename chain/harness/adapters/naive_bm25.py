# -*- coding: utf-8 -*-
"""朴素 BM25 基线（对照，不是记忆系统）——**本库随库发布的参考实现**。

它存在的三个理由：
  1. **下限参照**——任何记忆系统如果打不赢它，说明架构没带来增益；
  2. **harness 自检**——不依赖任何外部服务，可用来验证「写入→检索→作答→判分」链路；
  3. **适配器范例**——想知道怎么写自己的适配器，照本文件 60 行抄一遍即可
     （契约见 base.py；写入＝切块建索引，检索＝打分取 top-k，cid 原样带出）。

纯标准库实现（中文用字符 unigram+bigram，无需分词器）。
"""
from __future__ import annotations

import math
from collections import Counter

from .base import MemoryAdapter
import common as C  # harness 目录在 sys.path 上（由 probe_runner.py 注入）


def tokens(s: str) -> list[str]:
    t = C.norm(s)
    uni = list(t)
    bi = [t[i:i + 2] for i in range(len(t) - 1)]
    return uni + bi


class BM25Adapter(MemoryAdapter):
    name = "naive-bm25"

    def __init__(self, size: int = 500, overlap: int = 100,
                 k1: float = 1.5, b: float = 0.75):
        self.size, self.overlap, self.k1, self.b = size, overlap, k1, b
        self.docs: list[dict] = []
        self.tf: list[Counter] = []
        self.len: list[int] = []
        self.df: Counter = Counter()
        self.avg = 0.0

    def reset(self) -> None:
        self.docs, self.tf, self.len, self.df, self.avg = [], [], [], Counter(), 0.0

    def ingest(self, chapters: list[dict]) -> dict:
        self.reset()
        self.docs = C.chunk_chapters(chapters, self.size, self.overlap)
        for d in self.docs:
            tk = tokens(d["text"])
            c = Counter(tk)
            self.tf.append(c)
            self.len.append(len(tk))
            for w in c:
                self.df[w] += 1
        self.avg = sum(self.len) / max(1, len(self.len))
        return {"chunks": len(self.docs)}

    def retrieve(self, query: str, k: int = 10) -> list[dict]:
        N = len(self.docs)
        qs = set(tokens(query))
        scored = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for w in qs:
                f = c.get(w)
                if not f:
                    continue
                idf = math.log(1 + (N - self.df[w] + 0.5) / (self.df[w] + 0.5))
                s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [{"text": self.docs[i]["text"], "cid": self.docs[i]["cid"],
                 "score": round(s, 4)} for s, i in scored[:k]]
