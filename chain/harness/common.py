# -*- coding: utf-8 -*-
"""记忆系统对比 harness · 共用模块（随库发布版）

与作者本地完整 harness 的关系：本文件是**发布子集**，只保留第三方跑臂必需的部分——
文本归一化（`norm`/`hit`）、章内切块（`chunk_chapters`）、语料读取（`load_corpus`）、
固定生成器客户端（`LLM`）、产物根目录（`RUNS`）。

口径要点（与完整版一致）：
  · 检索单位 = 章内切块（默认 500 字、重叠 100），块带 cid，便于与金标准对齐；
  · **适配器不得替换固定生成器**——作答一律由 harness 的 LLM 完成，否则测的就不是记忆系统。

与完整版的差异（有意为之，均因"公开面不带本机私有信息"）：
  · 不读本机绝对路径：语料默认取 `chain/corpus/corpus.json`（可用 `load_corpus(path=...)` 覆盖）；
  · 产物根目录 `RUNS` 可由环境变量 `HMB_RUNS` 覆盖，默认 `chain/tools/out/runs/`（已被 .gitignore）；
  · 凭据只读环境变量 `DEEPSEEK_API_KEY`（不回退 Windows 系统变量，不落盘、不打印）。
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent          # chain/harness
CHAIN_DIR = HARNESS_DIR.parent                          # chain
REPO_ROOT = CHAIN_DIR.parent                            # 仓根

CORPUS_FILE = CHAIN_DIR / "corpus" / "corpus.json"      # 已发布的合成语料（冻结快照）
RUNS = Path(os.environ.get("HMB_RUNS") or (CHAIN_DIR / "tools" / "out" / "runs"))

GEN_MODEL = "deepseek-flash"                             # 固定生成器（作答/判分一律用它）


# ---------------- 文本归一化 ----------------
_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    """归一化：去所有空白（与判分链同口径）。"""
    return _WS.sub("", s or "")


def hit(quote: str, text: str) -> bool:
    """金标准命中判定：归一化后 text 里逐字包含 quote。"""
    q, t = norm(quote), norm(text)
    return bool(q) and q in t


# ---------------- 语料 ----------------
def load_corpus(path: str | Path | None = None) -> list[dict]:
    """读语料 → [{"cid", "title", "text"}]。

    默认读已发布的 `chain/corpus/corpus.json`；`path` 可指向任意同形状文件
（`{"chapters": [{"cid", "title", "text"}, ...]}` 或直接是章节数组）。
    """
    p = Path(path) if path else CORPUS_FILE
    raw = json.loads(p.read_text(encoding="utf-8"))
    chs = raw.get("chapters") if isinstance(raw, dict) else raw
    if not isinstance(chs, list):
        raise ValueError(f"语料文件形状不认识（缺 chapters）：{p}")
    return [{"cid": c["cid"], "title": c.get("title", ""),
             "text": (c.get("text") or "").replace("\r", "")} for c in chs]


def chunk_chapters(chapters: list[dict], size: int = 500,
                   overlap: int = 100) -> list[dict]:
    """按 size 字切块（带 overlap），块保留 cid。"""
    chunks = []
    for ch in chapters:
        body = ch["text"]
        step = max(1, size - overlap)
        for i in range(0, len(body), step):
            seg = body[i:i + size]
            if len(seg.strip()) < 40:
                continue
            chunks.append({"cid": ch["cid"], "title": ch["title"],
                           "text": seg, "pos": i})
            if i + size >= len(body):
                break
    return chunks


# ---------------- 固定生成器 ----------------
class LLM:
    """固定生成器客户端（DeepSeek，官方 SDK 接法）。

    ★ `max_tokens` 只是上限、不改变实际计费，故一律给足（推理模型的思考会吃额度）。
      `thinking=False` 用于抽取/翻译/格式化这类不需要思考的活。
    凭据：只读环境变量 `DEEPSEEK_API_KEY`；缺失即报错，不回退、不猜测。
    """

    MAX_OUT = 384_000

    def __init__(self, model: str = GEN_MODEL, max_tokens: int = MAX_OUT,
                 thinking: bool = True, effort: str | None = None):
        from openai import OpenAI
        self.model = model
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.effort = effort
        self.key = self._read_key()
        self.client = OpenAI(api_key=self.key, base_url="https://api.deepseek.com")
        self.calls = 0
        self.tokens = 0

    @staticmethod
    def _read_key() -> str:
        k = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not k:
            raise RuntimeError(
                "未找到环境变量 DEEPSEEK_API_KEY。"
                "作答与判分需要固定生成器，请先设置该变量再重试（本库不代管凭据）。")
        return k

    def chat(self, messages: list[dict], retries: int = 3,
             temperature: float = 0.0) -> str:
        kw = {"model": self.model, "messages": messages,
              "max_tokens": self.max_tokens, "temperature": temperature}
        if self.thinking:
            kw["extra_body"] = {"thinking": {"type": "enabled"}}
            if self.effort:
                kw["reasoning_effort"] = self.effort
        else:
            kw["extra_body"] = {"thinking": {"type": "disabled"}}
        last = ""
        for a in range(retries):
            try:
                r = self.client.chat.completions.create(**kw)
                self.calls += 1
                self.tokens += int(getattr(r.usage, "total_tokens", 0) or 0)
                return (r.choices[0].message.content or "").strip()
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                time.sleep(2 * (a + 1))
        raise RuntimeError(f"LLM 调用失败（{retries} 次）：{last}")
