# -*- coding: utf-8 -*-
import subprocess, json
REPO = 'FuRongJun-1999/hive-memory-bench'
def ls(path=''):
    p = subprocess.run(['gh','api','repos/%s/contents/%s' % (REPO, path), '--jq', '.[] | "\(.type)\t\(.size)\t\(.name)"'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        return None, p.stderr[:150]
    return p.stdout.strip().split(chr(10)), None
print('=== main 根目录 ===')
out, err = ls('')
if err: print('ERR', err)
else:
    for l in out: print('  ', l)
print()
for d in ('corpus', 'e2e', 'chain'):
    print('=== main /%s ===' % d)
    out, err = ls(d)
    if err:
        print('  ERR', err[:100]); continue
    for l in out[:25]: print('  ', l)
    print()