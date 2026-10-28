import json, os
from pathlib import Path
p = Path(os.path.expanduser("~/.dsh/logs/dsh-memory-hook-audit.json"))
d = json.loads(p.read_text(encoding="utf-8"))
print("counts:", json.dumps(d.get("counts"), ensure_ascii=False)[:500])
print("kinds:", json.dumps(d.get("kinds"), ensure_ascii=False)[:300])
print("source_shapes:", json.dumps(d.get("source_shapes"), ensure_ascii=False)[:300])
print("updated_at:", d.get("updated_at"))