#!/usr/bin/env python3
"""
高级测试预言模块
基于统计排名基准模型的异常检测预言
"""
from .ranking_anomaly import oracle_ranking_anomaly

# 高级预言列表
ADVANCED_ORACLES = [
    oracle_ranking_anomaly,
]

__all__ = ['ADVANCED_ORACLES']
