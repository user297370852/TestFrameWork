#!/usr/bin/env python3
"""
排名计算工具
计算GC在各项指标上的排名，并进行异常检测

V2.1 新增：三通道鲁棒检测所需的工具函数
- calculate_regret: 计算相对最优值的退化量
- robust_z: 鲁棒Z分数计算（基于MAD）
- calculate_log_tail_score: log尺度尾部分数
- calculate_rank_tail_prob_from_hist: 基于历史排名直方图的尾概率
"""
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
import math
import statistics


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
    #这里我们暂时只输出严重异常
    else:
        return AnomalySeverity.NONE, AnomalyDirection.NONE
        # return AnomalySeverity.MODERATE, direction

    


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


# ============================================================
# V2.1 三通道鲁棒检测工具函数
# ============================================================

def calculate_regret(value: float, best_value: float, alpha: float = 1.0) -> float:
    """
    计算相对最优值的退化量 (Self-Regret)
    
    regret = log((x + alpha) / (x_best + alpha))
    
    该指标无量纲，跨测试用例可比，乘法差异变成加法差异。
    regret = 0 表示该GC是组内最优。
    
    Args:
        value: 当前GC的指标值
        best_value: 同一testcase下该指标的最优值
        alpha: 平滑参数，避免除零和log(0)
    
    Returns:
        regret值（非负）
    """
    if value is None or best_value is None:
        return 0.0
    
    # 确保值为非负
    value = max(0, value)
    best_value = max(0, best_value)
    
    # 计算log ratio
    numerator = value + alpha
    denominator = best_value + alpha
    
    if denominator <= 0:
        return 0.0
    
    regret = math.log(numerator / denominator)
    # regret应是非负的（因为 value >= best_value，越小越好）
    return max(0.0, regret)


def robust_z(value: float, median: float, mad: float, eps: float = 1e-9) -> float:
    """
    计算鲁棒Z分数（基于中位数和MAD）
    
    Z = (value - median) / (1.4826 * MAD + eps)
    
    1.4826 是正态分布下 MAD 到标准差的转换系数。
    这比基于均值和标准差的Z分数更鲁棒，不受极端值影响。
    
    Args:
        value: 当前值
        median: 中位数
        mad: 中位数绝对偏差 (Median Absolute Deviation)
        eps: 防止除零的小常数
    
    Returns:
        鲁棒Z分数
    """
    if mad is None or mad < 0:
        return 0.0
    
    # MAD为0时，检查值是否等于中位数
    if mad < eps:
        if abs(value - median) < eps:
            return 0.0
        else:
            # MAD为0但值不等，返回一个较大值表示异常
            return 10.0 if value > median else -10.0
    
    z = (value - median) / (1.4826 * mad + eps)
    return z


def calculate_log_tail_score(
    values_by_gc: Dict[str, float],
    alpha: float = 1.0,
    eps: float = 1e-9
) -> Dict[str, Dict[str, float]]:
    """
    在log尺度上计算各GC的尾部分数
    
    用于通道C：极端值检测
    
    y = log(x + alpha)
    Z_tail = (y - median(y)) / (1.4826 * MAD(y) + eps)
    
    Args:
        values_by_gc: {gc_type: 原始值}
        alpha: 平滑参数
        eps: 防止除零
    
    Returns:
        {gc_type: {"log_value": y, "z_tail": z_tail}}
    """
    if not values_by_gc:
        return {}
    
    # 计算log值
    log_values = {}
    for gc_type, value in values_by_gc.items():
        if value is not None and value >= 0:
            log_values[gc_type] = math.log(value + alpha)
        else:
            log_values[gc_type] = math.log(alpha)
    
    # 计算中位数和MAD
    log_list = list(log_values.values())
    median_log = statistics.median(log_list)
    
    # 计算MAD
    deviations = [abs(v - median_log) for v in log_list]
    mad_log = statistics.median(deviations) if deviations else 0.0
    
    # 计算各GC的Z分数
    result = {}
    for gc_type, log_val in log_values.items():
        z_tail = robust_z(log_val, median_log, mad_log, eps)
        result[gc_type] = {
            "log_value": log_val,
            "z_tail": z_tail
        }
    
    return result


def calculate_rank_tail_prob_from_hist(
    observed_rank: float,
    rank_hist: Dict[str, int],
    smoothing: float = 1.0,
    eps: float = 1e-9
) -> float:
    """
    基于历史排名直方图计算尾概率
    
    不再假设排名服从正态分布，而是直接使用经验离散分布。
    
    p_rank = P(R >= observed_rank | 历史分布)
    
    Args:
        observed_rank: 观察到的排名
        rank_hist: 历史排名频数字典 {"1": 120, "2": 340, ...}
        smoothing: 平滑参数（Laplace平滑）
        eps: 防止log(0)
    
    Returns:
        尾概率 p_rank (0~1)
    """
    if not rank_hist:
        return 0.5  # 无历史数据时返回中性概率
    
    # 转换为整数排名（处理并列排名）
    rank_int = int(round(observed_rank))
    
    # 统计总数（加平滑）
    total_count = sum(rank_hist.values()) + smoothing * len(rank_hist)
    
    # 计算尾概率：P(R >= observed_rank)
    tail_count = smoothing / 2  # 初始化为平滑值的一半
    for rank_str, count in rank_hist.items():
        try:
            rank = int(rank_str)
            if rank >= rank_int:
                tail_count += count
        except ValueError:
            continue
    
    p_rank = tail_count / total_count
    
    # 确保概率在有效范围内
    return max(eps, min(1.0 - eps, p_rank))


def calculate_rank_surprise_score(p_rank: float, eps: float = 1e-9) -> float:
    """
    将尾概率转换为惊奇分数
    
    S_rank = -log10(p_rank + eps)
    
    该分数越高表示越罕见/异常。
    例如：p=0.01 -> S=2, p=0.001 -> S=3
    
    Args:
        p_rank: 尾概率
        eps: 防止log(0)
    
    Returns:
        惊奇分数 (非负)
    """
    if p_rank is None or p_rank <= 0:
        return 10.0  # 极端罕见的上限
    
    return -math.log10(p_rank + eps)


def calculate_gate_factor(regret: float, tau: float) -> float:
    """
    计算门控因子，用于调节排名信号
    
    gate = min(1, regret / tau)
    
    当退化量很小时（regret < tau），排名信号的权重被压低，
    从而减少"数值接近但排名波动"导致的误报。
    
    Args:
        regret: 退化量
        tau: 门控阈值
    
    Returns:
        门控因子 [0, 1]
    """
    if tau <= 0:
        return 1.0
    
    return min(1.0, regret / tau)


def calculate_tail_ratio(value: float, best_value: float) -> float:
    """
    计算相对最优值的倍数
    
    ratio = value / best_value
    
    用于通道C的"有实际差距"判断条件。
    
    Args:
        value: 当前值
        best_value: 最优值
    
    Returns:
        比值 (>=1)
    """
    if best_value is None or best_value <= 0:
        return 1.0
    if value is None or value < 0:
        return 1.0
    
    return max(1.0, value / best_value)
