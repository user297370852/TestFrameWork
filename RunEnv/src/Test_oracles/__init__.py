#!/usr/bin/env python3
"""
测试预言模块注册表
集中管理所有测试预言，供ResAnalyzer调用
"""
# 导入所有测试预言
from .missing_required_fields import oracle_missing_required_fields
from .test_failure import oracle_test_failure
from .performance_anomaly import oracle_performance_anomaly
from .performance_regression import oracle_performance_regression
from .stw_anomaly import oracle_stw_anomaly
from .gc_overhead_anomaly import oracle_gc_overhead_anomaly

# 测试预言注册表
# 在此添加新的测试预言函数
TEST_ORACLES = [
    #oracle_missing_required_fields,
    #oracle_test_failure,
    #oracle_performance_anomaly,
    #oracle_performance_regression,
    oracle_stw_anomaly,
    #oracle_gc_overhead_anomaly,
]

# 导出主要接口
__all__ = ['TEST_ORACLES']
