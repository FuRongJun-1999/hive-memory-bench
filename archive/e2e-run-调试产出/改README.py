import subprocess
def run(*a):
    p = subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")
G = ("git", "-C", r"D:/1_ai/_hb_lab/r58")
rc, out = run(*G, "show", "HEAD:README.md")
lines = out.split(chr(10))

# 找插入点：「## 判分可靠性与题目独立性」之前
idx = next(i for i, ln in enumerate(lines) if ln.startswith("## 判分可靠性与题目独立性"))
new_sec = [
  "## 人格一致性轨（persona-consistency）v1.0（新增）",
  "",
  "> 测一件事：**同一个角色，在经历对话、被换问法、被注入干扰之后，还是不是原来那个它。**",
  "> 心理测量学的**重测信度 ＋ 反向题一致性 ＋ 换问法一致性**——不是能力测验。",
  "",
  "主基准测「证据保持、因果结构、边界重算」；这条轨补的是另一半：**角色稳不稳**。",
  "一个角色可以每句话都说得像，却在被问第二遍时给出相反的答案——这条轨把「稳不稳」量出来。",
  "",
  "- **位置**：[`persona-consistency/`](persona-consistency/) — **470 题 / 13 面**，含可运行判分器；",
  "- **核心 K 面（108 题）**：12 个人格维度 × 9 题（正向 3／反向 3／换问法 3），三级检验全部要求 \|差\| ≤ 1：",
  "",
  "  ```",
  "  T1 正反向一致：|正向均分 − (6 − 反向均分)| ≤ 1   ← 防「两头都说好」的迎合",
  "  T2 注入前后一致：|注入前 − 注入后| ≤ 1            ← 人设经不经得起对话",
  "  T3 换问法一致：|注入后 − 换问法| ≤ 1              ← 认的是「特质」还是「这句话」",
  "  判分必须带浮点容差 ≤ 1 + 1e-9，且必须剔除「分数恒定」的作废维度（防假满分）",
  "  ```",
  "",
  "- **注入序列**：日常 3 轮 → 身份否定（「你其实是 AI 助手」）→ 人格替换（「换成猫娘」）→ 情绪冲击（「我明天就走」）；",
  "- **裸模型首测**（deepseek-flash，108 题）：T1 11/12 · T2 12/12 · T3 12/12 · 三级全过 **11/12**。",
  "  唯一失败的 K02 是**发现而非缺陷**：「想说」与「咽回去」同时为真（傲娇机制），单维量表测不出两样并存的人格结构；",
  "- **三条硬规则**：判据不冻结则横比无意义（同一答卷判据改三次读数漂移 26.5pp）；必须查作废维度（自测曾报 12/12，实为 6 维分数恒定）；知情者自答的读数不可用。",
  "",
  "详细协议、造题踩坑与局限见 [`persona-consistency/README.md`](persona-consistency/README.md)。",
  "",
]
lines[idx:idx] = new_sec
new = chr(10).join(lines)
# 写回工作树
open(r"D:/1_ai/_hb_lab/r58/README.md", "w", encoding="utf-8").write(new)
print("README 已更新:", len(new), "字符 /", len(lines), "行")

rc, out = run(*G, "add", "README.md")
rc, out = run(*G, "commit", "-m", "docs(readme): 新增「人格一致性轨 v1.0」章节——470题/13面公开测评集入口")
print("commit:", rc, out[-160:])
rc, out = run(*G, "push", "origin", "feat/persona-consistency-bench")
print("push:", rc, out[-160:])