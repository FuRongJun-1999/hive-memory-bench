import json, os
from pathlib import Path
cfg = Path(r"D:/program/dsh-memory-main/hive/config.local.json")
d = json.loads(cfg.read_text(encoding="utf-8"))
key = d.get("HIVE_API_KEY") or ""
base = d.get("HIVE_API_BASE") or ""
print("key 存在:", bool(key), "| 长度:", len(key), "| base:", base)

# 写临时 patch：把 bench-meow 的 provider 改成智谱
patch = [
  "# 临时覆盖：用智谱路由替代 tianxun（仅本次运行，不改原 profile）",
  "- id: llm-pi-ai",
  "  name: \"@deepseek-ai/dsh-llm-pi-ai\"",
  "  config:",
  "    providers:",
  "      zhipu:",
  "        apiKeyEnv: ZHIPU_API_KEY",
  "        api: openai-completions",
  "        baseURL: " + base.strip(),
  "        models:",
  "          - id: glm-5.3-flash",
  "            name: glm-5.3-flash",
  "            contextWindow: 200000",
  "            maxTokens: 32000",
  "            input:",
  "              - text",
  "- id: agent-default-model",
  "  name: \"@deepseek-ai/dsh-agent-default-model\"",
  "  config:",
  "    provider: zhipu",
  "    model: glm-5.3-flash",
].join(chr(10))
out = Path(r"D:/1_ai/_hb_lab/r58/e2e/run/patch_zhipu.yml")
out.write_text(patch, encoding="utf-8")
print("patch 已写:", out, "|", len(patch), "字符")
print("前 3 行:", patch.split(chr(10))[:3])