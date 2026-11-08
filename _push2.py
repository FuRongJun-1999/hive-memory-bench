import subprocess, os
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','add','README.md')
rc, out = run('git','commit','-F','_msg2.txt')
print('commit:', rc)
print(out[-200:])
rc2, out2 = run('git','push','origin','feat/hive-mcq-182-and-scores')
print('push:', rc2)
print(out2[-200:])
for f in ('_msg2.txt','_ref.py','_ref_readme.md','_mainreadme.py','_warch.py','_arch.md','_push.py','_commit.py'):
    try: os.remove(os.path.join(r'D:/1_ai/_hb_lab/r58', f))
    except Exception: pass