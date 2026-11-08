import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
rc, out = run('git','fetch','origin','feat/mcq-150-selection-bank')
print('fetch rc:', rc)
print(out[-400:])
if rc == 0:
    rc2, out2 = run('git','checkout','feat/mcq-150-selection-bank')
    print('checkout rc:', rc2, out2[-200:])
    rc3, out3 = run('git','log','--oneline','-3')
    print(out3[:300])