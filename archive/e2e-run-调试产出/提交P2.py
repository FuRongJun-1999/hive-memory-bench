import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
run(*G, "add", "e2e", "docs")
rc, out = run(*G, "commit", "-m", "feat(e2e): P2——判据冻结为 judge.py v1.1（SHA 4643d75a）；B1/B2 同源降权（独立簇87）；新增 docs/横比口径_v1.0.md")
print("commit:", rc, out[-180:])
print(run(*G, "push")[1][-110:])