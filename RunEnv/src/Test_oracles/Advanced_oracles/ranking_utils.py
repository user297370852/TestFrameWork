#!/usr/bin/env python3
"""
排名计算工具
计算GC在各项指标上的排名，并进行异常检测
"""
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
import math


class MetricType(Enum):
    """指标类型枚举"""
    DURATION = "duration_ms"
    GC_STW_TIME = "gc_stw_time_ms"
    MAX_STW_TIME = "max_stw_time_ms"
    GC_COUNT = "total_gc_count"


class AnomalySeverity(Enum):
    """异常严重程度"""
    NONE = "none"
    MODERATE = "moderate"      # 2 < Z <= 3
    SEVERE = "severe"          # Z > 3


class AnomalyDirection(Enum):
    """异常方向"""
    NONE = "none"
    OVERPERFORM = "overperform"   # 排名比预期好 (Z < -k) - 不报告
    UNDERPERFORM = "underperform" # 排名比预期差 (Z > k) - 需要报告


def classify_gc_type(result: Dict[str, Any]) -> str:
    """
    根据GC参数识别GC类型
    
    Args:
        result: 测试结果，包含GC_parameters字段
    
    Returns:
        GC类型字符串
    """
    gc_params = result.get("GC_parameters", [])
    params_str = " ".join(gc_params).upper()
    
    # 检查是否是分代ShenandoahGC
    if "+USESHENANDOAHGC" in params_str:
        if "SHENANDOAHGCMODE=GENERATIONAL" in params_str:
            return "ShenandoahGC-Gen"
        return "ShenandoahGC"
    elif "+USEZGC" in params_str:
        return "ZGC"
    elif "+USEEPSILONGC" in params_str:
        return "EpsilonGC"
    elif "+USEG1GC" in params_str:
        return "G1GC"
    elif "+USEPARALLELOLDGC" in params_str:
        return "ParallelOldGC"
    elif "+USEPARALLELGC" in params_str:
        return "ParallelGC"
    elif "+USESERIALGC" in params_str:
        return "SerialGC"
    else:
        return "Unknown"


def get_metric_value(result: Dict[str, Any], metric_type: str) -> Optional[float]:
    """
    从测试结果中提取指标值
    
    Args:
        result: 测试结果
        metric_type: 指标类型
    
    Returns:
        指标值，如果不存在返回None
    """
    if metric_type == MetricType.DURATION.value:
        return result.get("duration_ms")
    
    gc_analysis = result.get("gc_analysis")
    if gc_analysis is None:
        return None
    
    if metric_type == MetricType.GC_STW_TIME.value:
        return gc_analysis.get("gc_stw_time_ms")
    elif metric_type == MetricType.MAX_STW_TIME.value:
        return gc_analysis.get("max_stw_time_ms")
    elif metric_type == MetricType.GC_COUNT.value:
        return gc_analysis.get("total_gc_count")
    
    return None


def calculate_rankings(
    test_results: List[Dict[str, Any]], 
    metric_type: str,
    jdk_version: str
) -> Dict[str, Dict[str, Any]]:
    """
    计算指定JDK版本内各GC的排名
    
    Args:
        test_results: 测试结果列表
        metric_type: 指标类型
        jdk_version: JDK版本
    
    Returns:
        {gc_type: {"rank": 排名, "value": 指标值, "result": 完整结果}}
    """
    # 筛选该JDK版本的成功测试
    jdk_tests = [
        r for r in test_results 
        if r.get("jdk_version") == jdk_version 
        and r.get("success", True) 
        and r.get("exit_code", 0) == 0
    ]
    
    if not jdk_tests:
        return {}
    
    # 提取GC类型和指标值
    gc_data = []
    for result in jdk_tests:
        gc_type = classify_gc_type(result)
        value = get_metric_value(result, metric_type)
        
        if value is not None and gc_type != "Unknown":
            gc_data.append({
                "gc_type": gc_type,
                "value": value,
                "result": result
            })
    
    if not gc_data:
        return {}
    
    # 按指标值排序（升序，值越小排名越靠前）
    sorted_data = sorted(gc_data, key=lambda x: x["value"])
    
    # 分配排名（处理并列情况）
    rankings = {}
    n = len(sorted_data)
    
    i = 0
    while i < n:
        # 找出所有相同值的项
        j = i
        same_values = [sorted_data[i]]
        while j + 1 < n and sorted_data[j + 1]["value"] == sorted_data[i]["value"]:
            j += 1
            same_values.append(sorted_data[j])
        
        # 并列排名 = 所有相同值项的排名平均值
        avg_rank = (i + 1 + j + 1) / 2  # i+1 到 j+1 的平均
        
        for item in same_values:
            gc_type = item["gc_type"]
            # 如果同一GC类型有多个结果，取排名最好的
            if gc_type not in rankings or avg_rank < rankings[gc_type]["rank"]:
                rankings[gc_type] = {
                    "rank": avg_rank,
                    "value": item["value"],
                    "result": item["result"]
                }
        
        i = j + 1
    
    return rankings


def calculate_z_score(
    actual_rank: float,
    mu: float,
    sigma: float
) -> float:
    """
    计算Z-Score
    
    Args:
        actual_rank: 实际排名
        mu: 排名期望
        sigma: 排名标准差
    
    Returns:
        Z-Score值，如果sigma=0且排名不同返回None表示不应该是异常
    """
    if sigma == 0:
        # 如果标准差为0，说明排名恒定（如EpsilonGC在GC相关指标上总是排名第一）
        # 此时无法进行有意义的Z-Score比较，返回None表示不检测
        return None
    
    return (actual_rank - mu) / sigma


def classify_anomaly(
    z_score: float,
    threshold_moderate: float = 2.0,
    threshold_severe: float = 3.0,
    detect_overperform: bool = False
) -> Tuple[AnomalySeverity, AnomalyDirection]:
    """
    根据Z-Score分类异常
    
    Args:
        z_score: Z-Score值（可能为None）
        threshold_moderate: 中度异常阈值
        threshold_severe: 严重异常阈值
        detect_overperform: 是否检测超表现（默认只检测欠表现）
    
    Returns:
        (严重程度, 异常方向)
    """
    # z_score为None表示无法比较（如sigma=0）
    if z_score is None:
        return AnomalySeverity.NONE, AnomalyDirection.NONE
    
    abs_z = abs(z_score)
    
    if abs_z <= threshold_moderate:
        return AnomalySeverity.NONE, AnomalyDirection.NONE
    
    direction = AnomalyDirection.OVERPERFORM if z_score < 0 else AnomalyDirection.UNDERPERFORM
    
    # 默认只检测欠表现（underperform），忽略超表现
    if direction == AnomalyDirection.OVERPERFORM and not detect_overperform:
        return AnomalySeverity.NONE, AnomalyDirection.NONE
    
    if abs_z > threshold_severe:
        return AnomalySeverity.SEVERE, direction
    else:
        return AnomalySeverity.MODERATE, direction


def calculate_confidence(z_score: float) -> float:
    """
    根据Z-Score计算置信度
    
    Args:
        z_score: Z-Score值
    
    Returns:
        置信度 (0-1)
    """
    if z_score is None:
        return 0.0
    
    abs_z = abs(z_score)
    
    # 使用标准正态分布的累积分布函数
    # P(|Z| > abs_z) = 2 * (1 - CDF(abs_z))
    # 置信度 = 1 - P(|Z| > abs_z) = 2 * CDF(abs_z) - 1
    
    # 简化的CDF近似（使用误差函数近似）
    try:
        confidence = 2 * (0.5 * (1 + math.erf(abs_z / math.sqrt(2)))) - 1
        return min(1.0, max(0.0, confidence))
    except:
        # 如果计算失败，使用线性近似
        if abs_z >= 3:
            return 0.997
        elif abs_z >= 2:
            return 0.95
        elif abs_z >= 1:
            return 0.68
        else:
            return 0.5


def is_all_zero_for_metric(
    test_results: List[Dict[str, Any]], 
    metric_type: str,
    jdk_version: str
) -> bool:
    """
    检查指定JDK版本下所有GC的指标值是否都为0
    
    Args:
        test_results: 测试结果列表
        metric_type: 指标类型
        jdk_version: JDK版本
    
    Returns:
        是否全为0
    """
    jdk_tests = [
        r for r in test_results 
        if r.get("jdk_version") == jdk_version 
        and r.get("success", True)
    ]
    
    for result in jdk_tests:
        value = get_metric_value(result, metric_type)
        if value is not None and value != 0:
            return False
    
    return True
