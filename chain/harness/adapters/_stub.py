# -*- coding: utf-8 -*-
"""未发布适配器的统一桩（把 ModuleNotFoundError 换成能读懂的话）。

为什么要有桩：probe_runner.py 按臂名 import 适配器模块。若模块不存在，
第三方看到的是一句 ModuleNotFoundError，既不知道缺什么、也不知道该怎么补。
桩把这个失败面变成可读的接口约定：模块在、类名对、报错里写清服务与契约。
"""
from __future__ import annotations


class AdapterNotPublished(RuntimeError):
    """该臂的适配器未随本库发布（需要自备服务与凭据）。"""


def not_published(name: str, service: str, hint: str = "") -> AdapterNotPublished:
    """构造一条可读的「未发布」错误。"""
    msg = (f"{name} 适配器未随本库发布：它需要外部服务 —— {service}。\n"
           "  本库发布的是「出题 + 判分」半侧；ingest/ask 半侧需要各系统自己的实例。\n"
           "  想跑这一臂：① 自备该服务；② 照 chain/harness/adapters/base.py 的契约"
           "（reset/ingest/retrieve/close）写一个适配器，类名与本模块保持一致；\n"
           "  或者 ③ 直接用开箱可跑的参考臂：--arm bm25（纯标准库、无外部服务）。")
    if hint:
        msg += f"\n  备注：{hint}"
    return AdapterNotPublished(msg)
