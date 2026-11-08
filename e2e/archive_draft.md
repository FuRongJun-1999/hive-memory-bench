# 功能名：hive-memory-bench 全面改用选择题判分 —— 题库重组为三类，旧论述题体系作废

# 生效条件
仓库 FuRongJun-1999/hive-memory-bench，分支 feat/hive-mcq-182-and-scores，commit afc086a。
新结构 mcq/ 三类；archive/ 保存全部旧论述题体系。

# 子功能
三类题库：
  mcq/e2e-simple/  端到端简单检索  150 题（秦吏39/毛选41/蜂巢38/对话32，全部单跳）
  mcq/reasoning/   复杂推理        238 题（蜂巢，open110/objective38/intervention90/E类56）
  mcq/persona/     人格一致性      108/180 题（K 面 v1/v2 + 作业规程）

统一判分 pick == answer（grade_mcq.py），不经任何模型或人工。
人格一致性面仍用三级检验（T1/T2/T3），待选择题化。

README 从 43.9KB 精简到 4.3KB，只保留现行选择题体系；新增 mcq/README.md 说明三类与判分口径。

归档到 archive/（570 项 6.6MB，可追溯不作现行读数）：
  e2e-questions-论述题470、cards-旧rubric92、docs-旧分析25、
  results-旧读数、systems-旧读数、persona-落实_旧11面题库、persona-落实_旧判分器、
  roleplay-旧K面说明、tests-旧测试。

保留：corpus/（蜂巢指南）、e2e/corpus/（真实对话 32.5MB 语料）、chain/（状态链探针，另一条线）、sut/。

# 执行
· 盘点 641 文件 45.7MB，按 23 个顶层目录分类；
· 建 mcq/ 三类目录，150 题从 main 拉入、238 题 git mv、K 面从 persona-consistency/questions 迁入；
· 旧体系 git mv 到 archive/（保留历史），清空 questions/ 与 persona-consistency/；
· 重写 README（删旧推论与旧读数，保留选择题口径与基线约束）。

# 验证方式
· 150 题：150 题数 / 材料分布 39-41-38-32 / 答案分布 A37 B38 C38 D37 全部核对；
· 238 题：238 题数 / kind 110-38-90 / 答案分布 A48 B46 C45 D54 E45；
· 最终结构确认：mcq/ 10 项 1.36MB + corpus 350KB + e2e/corpus 32.5MB + archive 570 项 6.6MB；
· push 成功 604bf8e..afc086a。

# 不适用条件
· 人格一致性面尚未选择题化（仍是三级检验量表），三类口径未完全统一；
· 简单检索题里秦吏39+毛选41共80题因版权第三方不可核，可核仅 70/150=47%；
· 复杂推理题的干扰项未按 v2.1 规则（漏两条以上）重写，抽样5题有4题仍含漏条型；
· 新结构尚未在 238 题上重跑三方案（直喂/千问/灵枢），旧读数不可迁移；
· chain/ 状态链探针未纳入三类体系，仍是独立评测线。