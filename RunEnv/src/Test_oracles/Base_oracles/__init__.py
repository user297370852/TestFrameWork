#!/usr/bin/env python3
"""
基础测试预言模块
包含基于固定阈值和经验规则的测试预言
"""
from .missing_required_fields import oracle_missing_required_fields
from .test_failure import oracle_test_failure
from .performance_anomaly import oracle_performance_anomaly
from .performance_regression import oracle_performance_regression
from .stw_anomaly import oracle_stw_anomaly
from .gc_overhead_anomaly import oracle_gc_overhead_anomaly
from .gc_count_anomaly import oracle_gc_count_anomaly
from .heap_anomaly import oracle_heap_anomaly

# 基础预言列表
BASE_ORACLES = [
    oracle_missing_required_fields,
    oracle_test_failure,
    oracle_performance_anomaly,
    oracle_performance_regression,
    oracle_stw_anomaly,
    oracle_gc_overhead_anomaly,
    oracle_gc_count_anomaly,
    oracle_heap_anomaly,
]

__all__ = ['BASE_ORACLES', 'oracle_heap_anomaly']
