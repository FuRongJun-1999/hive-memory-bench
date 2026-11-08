import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','fetch','origin','main')
print('=== 尝试 merge 看冲突 ===')
rc, out = run('git','merge','origin/main','--no-commit','--no-ff')
print('merge rc:', rc)
print(out[-1500:])
print()
rc, out = run('git','status','--short')
conf = [l for l in out.split(chr(10)) if l.strip()]
print('变更条数:', len(conf))
for l in conf[:25]:
    print(' ', l[:110])