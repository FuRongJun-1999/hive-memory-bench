import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
rc, out = run('git','fetch','origin','feat/hive-mcq-182-and-scores')
print('fetch:', rc, out[-200:])
rc2, out2 = run('git','checkout','feat/hive-mcq-182-and-scores')
print('checkout:', rc2, out2[-150:])
rc3, out3 = run('git','log','--oneline','-3')
print(out3[:250])
print()
import json
from pathlib import Path
d = json.loads(Path(r'D:/1_ai/_hb_lab/r58/questions/题目_选择题_182.json').read_text(encoding='utf-8'))
print('题数:', len(d))
print('字段:', sorted(d[0].keys()))
print()
print('=== 首题 ===')
print(json.dumps(d[0], ensure_ascii=False, indent=1)[:1200])