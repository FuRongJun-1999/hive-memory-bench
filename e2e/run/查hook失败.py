import json, os
from pathlib import Path
# 检查 hook 报 failed 的具体原因
p = Path(os.path.expanduser("~/.dsh/logs/dsh-memory-hook-audit.json"))
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=== hook audit 结构 ===")
    print("顶层键:", list(d.keys())[:10])
    ev = d.get("events") or d.get("entries") or []
    print("事件数:", len(ev))
    fails = [e for e in ev if e.get("action") == "skipped" and e.get("reason") == "failed"]
    print("failed 次数:", len(fails))
    if fails:
        print("最近 failed:", json.dumps(fails[-2], ensure_ascii=False)[:400])
    print()
    print("=== 最近 5 条 ===")
    for e in ev[-5:]:
        print(" ", json.dumps(e, ensure_ascii=False)[:160])