from pathlib import Path
p = Path(r"D:/1_ai/_hb_lab/r58/README.md")
s = p.read_text(encoding="utf-8")
old = "三级检验全部要求 \\|差\\| ≤ 1："
new = "三级检验全部要求「差」≤ 1："
if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("已修")
else:
    print("未匹配，跳过")