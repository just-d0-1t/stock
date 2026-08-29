#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据源注册中心（update/sources）。

MarketAnalyzer 通过 create_source(名称) 创建数据源实例，名称与命令行
-f/--fetch_from 一一对应。新增数据源三步：
  1. 在 update/sources/ 下新建 xxx_source.py，实现 DailySource.fetch_daily；
  2. 在下方 SOURCE_REGISTRY 中登记：名称 -> (模块路径, 类名)；
  3. 命令行 -f/--fetch_from 传入注册名即可使用。

采用惰性导入：只有真正使用某个数据源时才 import 其依赖库
（如 adata / akshare），注册表加载不要求所有依赖都已安装。
"""

from update.sources.base import DailySource

# 数据源注册表：名称 -> (模块路径, 类名)
SOURCE_REGISTRY = {
    "remote": ("update.sources.adata_source", "AdataSource"),  # adata / akshare（默认远程源）
    "adata": ("update.sources.adata_source", "AdataSource"),   # "remote" 的别名
    "ths": ("update.sources.ths_source", "ThsSource"),         # 同花顺 API
    "local": ("update.sources.local_source", "LocalSource"),   # 本地全市场快照
}


def create_source(name, **kwargs):
    """按注册名称创建数据源实例；未注册的名称直接报错。"""
    if name not in SOURCE_REGISTRY:
        raise ValueError(f"未知数据源: {name}，可用: {list(SOURCE_REGISTRY)}")
    module_path, class_name = SOURCE_REGISTRY[name]
    from importlib import import_module
    provider_cls = getattr(import_module(module_path), class_name)
    return provider_cls(**kwargs)