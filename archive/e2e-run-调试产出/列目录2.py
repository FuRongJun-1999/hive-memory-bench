# -*- coding: utf-8 -*-
import subprocess
REPO = 'FuRongJun-1999/hive-memory-bench'
def ls(path):
    p = subprocess.run(['gh','api','repos/%s/contents/%s' % (REPO, path)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0: return None, p.stderr[:120]
    try: return subprocess.run(['gh','api','repos/%s/contents/%s' % (REPO, path), '--jq', '.[] | .type + "|" + (.size|tostring) + "|" + .name'], capture_output=True, text=True, encoding='utf-8').stdout.strip().split(chr(10)), None
    except Exception as e: return None, str(e)[:100]
for d in ('questions', 'cards', 'docs', 'e2e/corpus', 'systems'):
    print('=== /%s ===' % d)
    out, err = ls(d)
    if err: print('  ERR', err[:100]); print(); continue
    for l in out[:30]: print('  ', l)
    if len(out) > 30: print('   ... 共', len(out), '项')
    print()