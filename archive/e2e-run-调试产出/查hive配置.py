import json, os
from pathlib import Path
cands = [
    Path(r"D:/program/AEIS/hive/config.local.json"),
    Path(r"D:/1_ai/_refs/hive/config.local.json"),
    Path(os.path.expanduser("~/.hive/config.local.json")),
    Path(r"D:/program/hive/config.local.json"),
]
# 广搜
for root in (r"D:/program", r"D:/1_ai", r"D:/dsh-home"):
    p = Path(root)
    if not p.exists():
        continue
    try:
        for f in p.rglob("config.local.json"):
            cands.append(f)
    except Exception:
        pass
seen = set()
for c in cands:
    if str(c) in seen or not c.exists():
        continue
    seen.add(str(c))
    print("=" * 60)
    print(c)
    try:
        d = json.loads(c.read_text(encoding="utf-8"))
    except Exception as e:
        print("  解析失败:", str(e)[:100]); continue
    def walk(o, depth=0):
        if depth > 2 or not isinstance(o, dict):
            return
        for k, v in list(o.items())[:15]:
            if isinstance(v, dict):
                print("  " * (depth+1) + k + ":")
                walk(v, depth+1)
            elif isinstance(v, str) and any(x in k.lower() for x in ("key", "token", "secret")):
                print("  " * (depth+1) + k + ": <str len=" + str(len(v)) + "，不打印>")
            elif isinstance(v, str) and len(v) < 80:
                print("  " * (depth+1) + k + ": " + v)
    walk(d)