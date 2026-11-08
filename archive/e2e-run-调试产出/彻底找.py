# -*- coding: utf-8 -*-
import subprocess, json
REPO = 'FuRongJun-1999/hive-memory-bench'
def gh(args):
    p = subprocess.run(['gh'] + args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')

print('=== 1) 所有分支 ===')
rc, out = gh(['api', 'repos/%s/branches' % REPO, '--jq', '.[] | .name'])
print(out[:800] if rc==0 else 'ERR '+out[:200])

print()
print('=== 2) GitHub 代码搜索：秦吏特征词 ===')
for kw in ('警官学院', '派出所编制', '小资产阶级', '陈独秀'):
    rc, out = gh(['api', 'search/code?q=%s+repo:%s' % (__import__('urllib.parse', fromlist=['quote']).quote(kw), REPO), '--jq', '.total_count'])
    if rc == 0:
        print('  「%s」 命中文件数: %s' % (kw, out.strip()))
    else:
        print('  「%s」 搜索失败: %s' % (kw, out.strip()[:120]))

print()
print('=== 3) PR #64 完整文件列表 ===')
rc, out = gh(['api', 'repos/%s/pulls/64/files?per_page=100' % REPO, '--jq', '.[] | .filename'])
print(out.strip() if rc==0 else 'ERR '+out[:200])

print()
print('=== 4) 仓库里所有 .json/.md 文件名含「秦」「毛」「选」的 ===')
rc, out = gh(['api', 'git/trees/main?recursive=1', '--jq', '.tree[] | select(.type=="blob") | .path'])
if rc == 0:
    paths = out.strip().split(chr(10))
    print('  共', len(paths), '个 blob')
    for p in paths:
        if any(k in p for k in ('秦', '毛', '选')):
            print('   ', p)
else:
    print('ERR', out[:200])