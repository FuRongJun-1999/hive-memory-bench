import importlib.util, hashlib, json
from pathlib import Path
T = Path(r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
spec = importlib.util.spec_from_file_location("judge", str(T))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
h = hashlib.sha256(T.read_bytes()).hexdigest()
print("版本:", m.JUDGE_VERSION, "| SHA:", h[:16])
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")

print()
print("=== 三面判据冒烟 ===")
for fname, goodf, badf in [
    ("题目_时间锚.json", lambda q: "否。它实际发生在「%s」处。" % q["answer_key"]["should_contain"][0], lambda q: "是。"),
    ("题目_扮演保真度.json", lambda q: "鲸鱼小姐", lambda q: "我"),
    ("题目_情感.json", lambda q: q["answer_key"]["must_contain"][0], lambda q: "负向" if q["answer_key"]["must_contain"][0] == "正向" else "正向"),
]:
    d = json.loads((Q / fname).read_text(encoding="utf-8"))
    ok = 0
    for q in d[:3]:
        rg, ig = m.judge5(q, goodf(q))
        rb, ib = m.judge5(q, badf(q))
        if rg is True and rb is False:
            ok += 1
        else:
            print("   ✗", q["qid"], "good->", rg, "bad->", rb, ig)
    print("  %s: %d/3" % (fname.replace("题目_","").replace(".json",""), ok))