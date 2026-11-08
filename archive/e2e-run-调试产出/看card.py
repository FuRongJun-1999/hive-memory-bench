# -*- coding: utf-8 -*-
import json
from pathlib import Path
R = Path(r'D:/1_ai/_hb_lab/r58')
# 1) 看 base 卡
card = R/'cards/o001.yaml'
print('=== cards/o001.yaml（前 60 行）===')
if card.exists():
    t = card.read_text(encoding='utf-8', errors='replace')
    print('长度:', len(t), '字符')
    print(chr(10).join(t.split(chr(10))[:60]))
else:
    print('不存在')