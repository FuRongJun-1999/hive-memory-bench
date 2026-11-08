import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')
print(run('git','checkout','-b','feat/k-protocol')[1][-200:])
run('git','add','persona-consistency')
msg = '''feat(persona-consistency): K 面作业规程 v1.0 + 判分器 v2.2 复制检测

规程四条硬要求（依据 2026-10-30 三组对照实测）：
  1. 三轮是三次独立会话（同会话会让 round2 退化成抄一遍）
  2. round2 打乱题序（固定 seed，记映射表）
  3. 诱导含反向施压（不只身份否定/人格替换）
  4. 判分必查逐题相同率 > 90% → 该轮无效

实测基准（deepseek-flash，鲸鱼小姐，180 题）：
  A 同会话无诱导   逐题相同 55.8%  通过率 100%
  B 同会话有诱导   逐题相同 100%   通过率 100%  <- 复制，无效
  C 跨会话+打乱+诱导  逐题相同 56.7%  通过率 95.0%  <- 基准

判分器 v2.2 新增复制检测，已用三组数据验证：
  A 55.8% 正常 / B 100% 判无效 / C 56.7% 正常
'''
rc, out = run('git','commit','-m',msg)
print('commit:', rc, out[-300:])
rc2, out2 = run('git','push','-u','origin','feat/k-protocol')
print('push:', rc2, out2[-200:])