import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e")
rc, out = run(*G, "commit", "-m", "test(e2e): 双单元复核题库后做判据分级——5面可横比/3面有条件/1面不可机械判/3面空缺；新增 check_judge.py 正反例门禁")
print("commit:", rc, out[-200:])
print(run(*G, "push")[1][-110:])