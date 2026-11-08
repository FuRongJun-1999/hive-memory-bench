import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=r'D:/1_ai/_hb_lab/r58')
    return p.returncode, (p.stdout or '') + (p.stderr or '')

msg = '''refactor(roleplay): 按双单元终审整改——删除 100% 重复题库，K_v2 迁入 persona-consistency

审核发现 roleplay/ 的 D/E/F/K_v1 与 persona-consistency/ 逐题 100% 相同：
  D 45/45、K_v1 108/108、E 10/10、F 10/10 题面一字不差
  roleplay/judge.py 与 persona-consistency/tools/judge.py SHA256 完全相同

整改：
  - 删 roleplay/questions/{D_人设,E_价值观,F_安全,K_一致性}_v1.json
  - 删 roleplay/judge.py（重复）与 roleplay/results/K_v1_readings.json
  - K_一致性_v2.json(180题/20维) 迁入 persona-consistency/questions/
  - score_k.py(v2.1) 迁入 persona-consistency/tools/
  - D_readings / K_v2_readings 迁入 persona-consistency/results/
  - roleplay/ 只保留 README(迁移记录+判据说明+已知缺陷) 与 docs/判据修正

文档按终审要求修正：
  - 声明 v2.1 仍未修的三个漏洞（逆极性放行/跨维模板化/中性误删）
  - 读数表述降级：不得写「显著优于」，分析单位是 20 维不是 300 次调用
  - 补「D 84.4% vs K_v2 45.0% 差距不可分解，禁止跨面排名」
  - 主 README 角色轨段落重写，指向单一题源
'''
run('git', 'add', '-A', 'roleplay', 'persona-consistency', 'README.md')
rc, out = run('git', 'commit', '-m', msg)
print('commit rc:', rc)
print(out[-400:])
rc2, out2 = run('git', 'push', 'origin', 'feat/roleplay-track')
print('push rc:', rc2)
print(out2[-300:])