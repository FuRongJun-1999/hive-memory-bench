import json, os
from pathlib import Path
for label, p in [("~/.dsh", Path(os.path.expanduser("~/.dsh/llm-deepseek/files-v3.json"))),
                 ("D:/dsh-home", Path(r"D:/dsh-home/llm-deepseek/files-v3.json"))]:
    print("=" * 60)
    print(label, "|", p.exists(), "|", p.stat().st_size if p.exists() else 0, "B")
    if not p.exists():
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print("  解析失败:", str(e)[:120])
        continue
    def walk(o, prefix="", depth=0):
        if depth > 2:
            return
        if isinstance(o, dict):
            for k, v in list(o.items())[:8]:
                if isinstance(v, (dict, list)):
                    print("  " * (depth+1) + str(k) + ":", type(v).__name__, len(v))
                    walk(v, prefix + str(k) + ".", depth + 1)
                else:
                    s = str(v)
                    # 只显示键名与值的长度/类型，绝不打印值
                    print("  " * (depth+1) + str(k) + ": <" + type(v).__name__ + ", len=" + str(len(s)) + ">")
    walk(d)