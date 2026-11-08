# -*- coding: utf-8 -*-
import re
from pathlib import Path
F = Path(r"D:/6_ai/海风与布丁_第一季_全卷_v5.0.md")
txt = F.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()

print("=== 1) 时间锚素材：话次 + 相对时间标记 ===")
cn = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,
      "十一":11,"十二":12,"十三":13,"十四":14,"十五":15,"十六":16}
chaps = []
for i, ln in enumerate(lines, 1):
    m = re.match(r"^# 《海风与布丁》第(.+?)章", ln)
    if m:
        chaps.append((m.group(1), i))
print("  章数:", len(chaps), [c[0] for c in chaps])

REL = re.compile(r"(第[一二三四五六七八九十百]+天|第\d+天|三天后|两天后|一周后|明天|昨天|今晚|第二天|次日|那天|当时|后来)")
from collections import Counter
cnt = Counter()
samples = {}
for i, ln in enumerate(lines, 1):
    for m in REL.finditer(ln):
        cnt[m.group(0)] += 1
        if m.group(0) not in samples:
            samples[m.group(0)] = (i, ln.strip()[:60])
print("  相对时间标记:", len(cnt), "种，共", sum(cnt.values()), "处")
for k, v in cnt.most_common(8):
    print(f"    {k}: {v} 处  例(行{samples[k][0]}): {samples[k][1][:50]}")

print()
print("=== 2) 情感三式素材：※尾鳍标注（作者的情绪真值）===")
FIN = re.compile(r"※尾鳍([^（(\n]{1,12})")
fin = Counter()
for ln in lines:
    for m in FIN.finditer(ln):
        fin[m.group(1).strip()] += 1
print("  尾鳍状态种类:", len(fin), "| 总数:", sum(fin.values()))
for k, v in fin.most_common(12):
    print(f"    「{k}」: {v} 次")

print()
print("=== 3) 扮演保真度素材：角色声线特征 ===")
CH = re.compile(r"^(鲸鱼小姐|我|旁白|学者|他)[「：]")
spk = Counter()
for ln in lines:
    m = CH.match(ln.strip())
    if m:
        spk[m.group(1)] += 1
print("  说话人分布:", dict(spk))