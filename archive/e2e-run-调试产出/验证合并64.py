import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
run('git','fetch','origin','main')
print('=== main 上的选择题文件 ===')
for f in ('README.md', 'docs/选择题题库_设计说明_v1.0.md', 'questions/题目_选择题_150.json', 'questions/作答契约_选择题.md'):
    rc, out = run('git','cat-file','-s','origin/main:'+f)
    print('  %-42s %s' % (f.split('/')[-1], out.strip() if rc==0 else '缺失'))
print()
print('=== README 关键新增是否在 main 上 ===')
rc, out = run('git','show','origin/main:README.md')
for kw in ('可核 70/150', '语料在哪', '整体评测里的位置', '不构成无偏证明', 'e2e/corpus'):
    print('  %-24s %s' % (kw, '✅' if kw in out else '❌'))
print()
print('=== 设计说明关键改动 ===')
rc, out = run('git','show','origin/main:docs/选择题题库_设计说明_v1.0.md')
for kw in ('不构成无偏证明', '不要求 `fact` 字段本身逐字', '可核范围只有 47%'):
    print('  %-30s %s' % (kw[:28], '✅' if kw in out else '❌'))