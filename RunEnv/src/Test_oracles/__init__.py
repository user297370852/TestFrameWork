#!/usr/bin/env python3
"""
测试预言模块注册表
集中管理所有测试预言，供ResAnalyzer调用

预言模块分为两类:
1. Base_oracles: 基于固定阈值和经验规则的基础预言
2. Advanced_oracles: 基于统计排名基准模型的高级预言
"""

# ============================================================
# 基础预言导入 (Base_oracles)
# ============================================================
from .Base_oracles.missing_required_fields import oracle_missing_required_fields
from .Base_oracles.test_failure import oracle_test_failure
from .Base_oracles.performance_anomaly import oracle_performance_anomaly
from .Base_oracles.performance_regression import oracle_performance_regression
from .Base_oracles.stw_anomaly import oracle_stw_anomaly
from .Base_oracles.gc_overhead_anomaly import oracle_gc_overhead_anomaly
from .Base_oracles.gc_count_anomaly import oracle_gc_count_anomaly

# 基础预言列表
BASE_ORACLES = [
    oracle_missing_required_fields,
    oracle_test_failure,
    oracle_performance_anomaly,
    oracle_performance_regression,
    oracle_stw_anomaly,
    oracle_gc_overhead_anomaly,
    oracle_gc_count_anomaly,
]

# ============================================================
# 高级预言导入 (Advanced_oracles)
# ============================================================
from .Advanced_oracles.ranking_anomaly import oracle_ranking_anomaly

# 高级预言列表
ADVANCED_ORACLES = [
    oracle_ranking_anomaly,
]

# ============================================================
# 测试预言注册表
# ============================================================
# 在此添加要启用的测试预言函数
# 建议: 开发调试时使用基础预言，生产环境使用高级预言

TEST_ORACLES = [
    # --- 基础预言 (可选启用) ---
    # oracle_missing_required_fields,
    # oracle_test_failure,
    # oracle_performance_anomaly,
    # oracle_performance_regression,
    #oracle_stw_anomaly,
    #oracle_gc_count_anomaly,
    #oracle_gc_overhead_anomaly,
    
    # --- 高级预言 (推荐) ---
    oracle_ranking_anomaly,  # 基于统计基准模型的异常检测
]

# 导出主要接口
__all__ = [
    'TEST_ORACLES',
    'BASE_ORACLES',
    'ADVANCED_ORACLES',
    'oracle_missing_required_fields',
    'oracle_test_failure',
    'oracle_performance_anomaly',
    'oracle_performance_regression',
    'oracle_stw_anomaly',
    'oracle_gc_overhead_anomaly',
    'oracle_gc_count_anomaly',
    'oracle_ranking_anomaly',
]
