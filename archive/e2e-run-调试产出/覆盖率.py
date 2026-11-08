# -*- coding: utf-8 -*-
import json, re, sys
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
try:
    import yaml
except ImportError:
    print('need pyyaml'); sys.exit(1)

def load_card(qid):
    p = R/'cards'/(qid + '.yaml')
    if not p.exists(): return None
    txt = p.read_text(encoding='utf-8', errors='replace')
    # 只取 rubric 段（pyyaml 对中文 YAML 可能有坑，用简解析）
    return yaml.safe_load(txt)

def hit_pattern(pat, text):
    if pat.startswith('re: '):
        try: return re.search(pat[4:], text) is not None
        except re.error: return False
    return pat in text

def coverage(option, rubric):
    req = [r for r in rubric if r.get('required')]
    if not req: return None, 0, 0
    hit = 0
    detail = []
    for i, item in enumerate(req):
        pats = item.get('any_of') or []
        ok = any(hit_pattern(p, option) for p in pats)
        if ok: hit += 1
        detail.append('%s:%s' % (item.get('id', i), 'Y' if ok else 'N'))
    return hit/len(req), hit, len(req), detail

card = load_card('o027')
print('=== o027 rubric 条数:', len([r for r in card['rubric'] if r.get('required')]))
print()
qs = json.loads((R/'questions/题目_选择题_238.json').read_text(encoding='utf-8'))['questions']
o27 = next(x for x in qs if x['id'] == 'o027')
print('=== o027 五个选项的覆盖率 ===')
for k in 'ABCD':
    if k not in o27['options']: continue
    res = coverage(o27['options'][k], card['rubric'])
    cov, hit, tot, detail = res
    mark = ' ★答案' if k == o27['answer'] else ''
    print('  %s 覆盖 %d/%d = %.0f%% %s%s' % (k, hit, tot, cov*100, detail, mark))