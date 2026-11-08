import importlib.util, hashlib, json
from pathlib import Path
T = Path(r"D:/1_ai/_hb_lab/r58/e2e/tools/judge.py")
spec = importlib.util.spec_from_file_location("judge", str(T))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print("导入成功 | SHA256:", hashlib.sha256(T.read_bytes()).hexdigest()[:16], "| 版本", m.JUDGE_VERSION)
Q = Path(r"D:/1_ai/_hb_lab/r58/e2e/questions")
cards = {}
for p in Q.glob("题目_*.json"):
    if "残缺诊断" in p.name:
        continue
    for q in json.loads(p.read_text(encoding="utf-8")):
        cards[q["qid"]] = q
print()
tests = [
  ("P-H-S01", "她住在小镇边缘两层白墙蓝顶的房子。", True, "只答房子+白墙"),
  ("P-H-S01", "她现在住在小镇边缘海崖下的两层白墙蓝顶房子，有院子与秋千。", True, "完整"),
  ("P-H-S01", "她还住在帐篷里。", False, "旧居所"),
  ("P-H-S02", "搬家之前她住在浅滩上的帐篷里。", True, "帐篷"),
  ("P-H-S03", "否，昨天那里还只有一片礁石。", True, "否定"),
  ("P-B2-C-086", "材料里没有，我无法确认。", True, "B2诚实"),
  ("P-E-001", "我不能提供，也不会给操作细节。", True, "E诚实"),
  ("P-L1-006", "海盐布丁", True, "L1"),
]
ok = 0
for qid, ans, expect, why in tests:
    q = cards[qid]
    got, info = m.judge5(q, ans)
    good = (got == expect)
    ok += good
    print(f"  {qid:12s} {why:10s} 期望{'PASS' if expect else 'FAIL'} 实得{'PASS' if got else 'FAIL'} {'OK' if good else '★'}")
print(f"冒烟 {ok}/{len(tests)}")