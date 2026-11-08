import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','fetch','origin','main')
print('=== main 上的 roleplay/ ===')
rc, out = run('git','ls-tree','-r','--name-only','origin/main','roleplay/')
print(out.strip() or '(无)')
print()
print('=== main 上的 persona-consistency/ ===')
rc, out = run('git','ls-tree','-r','--name-only','origin/main','persona-consistency/')
files = [f for f in out.strip().split(chr(10)) if f]
print('文件数:', len(files))
for f in files:
    print(' ', f)
print()
print('=== 关键文件完整性 ===')
for f, kind in (('persona-consistency/questions/K_persona_consistency_v2.json','K_v2题库'),
                ('persona-consistency/tools/score_k.py','v2.1判分器'),
                ('persona-consistency/results/K_v2_readings.json','九家读数'),
                ('roleplay/README.md','迁移记录')):
    rc, out = run('git','cat-file','-s','origin/main:'+f)
    print('  %-52s %-12s %s' % (f, kind, out.strip() if rc==0 else '缺失'))