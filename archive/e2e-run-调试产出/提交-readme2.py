import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','add','README.md')
run('git','add','docs/选择题题库_设计说明_v1.0.md')
rc, out = run('git','status','--short','--untracked-files=no')
print('暂存:', out.strip()[:200])
rc, out = run('git','commit','-F','e2e/run/commitmsg.txt')
print('commit rc:', rc)
print(out[-300:])
rc2, out2 = run('git','push','origin','feat/mcq-150-selection-bank')
print('push rc:', rc2)
print(out2[-250:])