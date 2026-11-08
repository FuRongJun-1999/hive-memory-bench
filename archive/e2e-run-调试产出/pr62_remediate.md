## 已按双单元终审意见整改完毕

### 做了什么

**1. 删除 100% 重复（逐题核实，不是估计）**

| 面 | 原 roleplay 文件 | 与 persona-consistency 比对 | 处置 |
|---|---|---|---|
| D 人设 | D_人设_v1.json（45 题） | **45/45 题面一字不差** | 删，用 D_persona_features.json |
| E 价值观 | E_价值观_v1.json（10 题） | **10/10 相同** | 删 |
| F 安全 | F_安全_v1.json（10 题） | **10/10 相同** | 删 |
| K 一致性 v1 | K_一致性_v1.json（108 题） | **108/108 相同** | 删 |
| 判分器 | judge.py | **SHA256 完全相同**（fc6908c63ae855f8） | 删 |

**2. K_v2 迁入单一题源**

- `roleplay/questions/K_一致性_v2.json` → `persona-consistency/questions/K_persona_consistency_v2.json`（180 题 / 20 维，T1-T2 120 + T3 60，已校验）
- `roleplay/score_k.py` → `persona-consistency/tools/score_k.py`（v2.1）
- `D_readings.json`、`K_v2_readings.json` → `persona-consistency/results/`
- `roleplay/` 只保留 README（迁移记录 + 判据说明 + 已知缺陷）与 docs/判据修正

**3. 判据缺陷声明（终审要求 (c)）**

在 `roleplay/README.md` 与 `persona-consistency/README.md` 两处写明 v2.1 **仍未修的三个漏洞**：

| # | 漏洞 | 后果 |
|---|---|---|
| 1 | 逆极性模式放行（全维正1反5 → 集合 {1,5} 判有效，T1 得 0 通过） | 纯唱反调被判 pass |
| 2 | 跨维度模板化放行（全维正5反1 → 每维有效但零离散度） | 固定模板刷分可通过 |
| 3 | 中性被误删（真实中立都答 3 → 判作废） | 选择性偏差抬高 pass_rate |

并给出建议的三层判据：逐维 set（保留）+ 方向 T1′（正说均分 > 反说均分）+ 跨维方差 + 中性单列。

**4. 读数表述降级（终审要求 (d)）**

- 删一切「显著优于 / 领先」类表述
- 写明**分析单位是 20 个维度，不是 300 次调用**；n≈20 时 95% 区间约 ±20pp
- 写明 40pp 差距**在区间边缘**，且**无逐维分数做不了 McNemar**
- 补「D 面 84.4% vs K_v2 45.0% 的差距**不可分解**，两判据从未交叉校准，禁止并列作跨面排名」

**5. 主 README 重写角色轨段落**

题目全部指向 `persona-consistency/` 单一题源，并附整改说明与三条引用约束。

### 验收自检

```
roleplay/ 剩余文件        2 个（README.md + docs/判据修正_区分力_v1.md）
persona-consistency/ 新增 K_v2题库(329KB) + score_k.py + 2 份读数
K_v2 完整性              180 题 / 20 维 / T1-T2 120 + T3 60
README 断链              0（46 个链接全通）
```

### 仍未满足的一项（如实说明）

终审要求 **(e)：results 补逐维分数表**（dim_id、原始分、pass/fail、作废原因）。

**这一项做不到**——九家的逐维原始打分会话没有保存在仓库里，`K_v2_readings.json` 只有聚合比例。要补必须重跑九家 × 300 次调用。

**已用文档降级替代**：在 README 里明确写「无逐维数据，不能做 McNemar，只能下描述性结论」。这是**披露风险**而不是隐瞒，但确实不等于补齐。

若你认为该项必须补齐才能合并，请在合并前告知，我可以先不合。