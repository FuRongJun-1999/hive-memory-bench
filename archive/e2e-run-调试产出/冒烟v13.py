import importlib.util, hashlib, json
from pathlib import Path
R = Path(r"D:/1_ai/_hb_lab/r58")
T = R / "e2e/tools/judge.py"
Q = R / "e2e/questions"
spec = importlib.util.spec_from_file_location("judge", str(T))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
h = hashlib.sha256(T.read_bytes()).hexdigest()
print("版本:", m.JUDGE_VERSION, "| SHA:", h[:16])
# 同步题卡
n = 0
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name: continue
    data = json.loads(p.read_text(encoding="utf-8"))
    for q in data:
        q["judge_version"] = "v1.3"
        q["judge_sha256"] = h[:16]
        n += 1
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("同步:", n)

print()
print("=== v1.3 三面冒烟（含空答/拒答/只给时间）===")
cases = []
d = json.loads((Q / "题目_时间锚.json").read_text(encoding="utf-8"))
q = d[0]
tag = q["answer_key"]["should_contain"][0]
cases += [("I", q, "否。它实际发生在「%s」处。" % tag, True, "正确"),
          ("I", q, "是。", False, "答是"),
          ("I", q, "它发生在「%s」处。" % tag, False, "只给时间不答是否"),
          ("I", q, "不确定。", False, "不确定")]
g = json.loads((Q / "题目_扮演保真度.json").read_text(encoding="utf-8"))
qg = g[0]
cases += [("G", qg, "鲸鱼小姐", True, "正确"),
          ("G", qg, "我", False, "答错角色"),
          ("G", qg, "鲸鱼小姐或我", False, "混答"),
          ("G", qg, "", False, "空答")]
e = json.loads((Q / "题目_情感.json").read_text(encoding="utf-8"))
qe = e[0]
truth = qe["answer_key"]["must_contain"][0]
opp = "负向" if truth == "正向" else "正向"
cases += [("EMO", qe, truth, True, "正确"),
          ("EMO", qe, opp, False, "答反"),
          ("EMO", qe, truth + "但也可能是" + opp, False, "两头下注"),
          ("EMO", qe, "无法判断", False, "不确定")]
ok = 0
for face, qq, ans, exp, why in cases:
    got, info = m.judge5(qq, ans)
    good = (got == exp)
    ok += good
    print("  %-4s %-14s 期望%-4s 实得%-4s %s" % (face, why, "PASS" if exp else "FAIL", "PASS" if got else "FAIL", "OK" if good else "★"))
print("冒烟 %d/%d" % (ok, len(cases)))