import json, os
from pathlib import Path
from collections import Counter
for label, p in [("~/.dsh", Path(os.path.expanduser("~/.dsh/llm-deepseek/files-v3.json"))),
                 ("D:/dsh-home", Path(r"D:/dsh-home/llm-deepseek/files-v3.json"))]:
    d = json.loads(p.read_text(encoding="utf-8"))
    recs = d.get("records", [])
    print("=" * 64)
    print(label, "| records:", len(recs))
    if recs:
        print("  首条字段:", sorted(recs[0].keys()))
    # 收集 provider / key 名（不打印值）
    names = Counter()
    kinds = Counter()
    for r in recs:
        for f in ("provider", "name", "key", "id", "kind", "type"):
            v = r.get(f)
            if isinstance(v, str) and len(v) < 40:
                names[f + "=" + v] += 1
    for k, n in names.most_common(20):
        print("   ", k, "x", n)