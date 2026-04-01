#!/usr/bin/env python3
"""
测试预言: 基于统计排名基准模型的异常检测
规则: 使用Z-Score检测排名显著偏离基准的GC测试（仅检测欠表现）
"""
from typing import Dict, Any, Optional, List
from .baseline_loader import get_baseline_loader
from .ranking_utils import (
    MetricType,
    calculate_rankings,
    calculate_z_score,
    classify_anomaly,
    calculate_confidence,
    is_all_zero_for_metric,
    AnomalySeverity,
    AnomalyDirection
)


# Z-Score阈值配置
# 注意：阈值越高，误报率越低，但漏报率也越高
# Z=2.0 对应95%置信度，约5%误报率（太高）
# Z=2.5 对应98.8%置信度，约1.2%误报率
# Z=3.0 对应99.7%置信度，约0.3%误报率
Z_SCORE_THRESHOLD_MODERATE = 2.5  # 中度异常阈值（提高以减少误报）
Z_SCORE_THRESHOLD_SEVERE = 3.5    # 严重异常阈值

# 是否检测超表现（默认False，只检测欠表现）
DETECT_OVERPERFORM = False

# 指标权重（用于多指标联合检测）
# 注意：执行时间(duration_ms)波动较大且受非GC因素影响，不建议用于异常检测
METRIC_WEIGHTS = {
    "gc_stw_time_ms": 1.0,    # GC总暂停时间 - 核心指标
    "max_stw_time_ms": 0.9,   # 最大单次暂停时间 - 重要指标
    "total_gc_count": 0.5,    # GC次数 - 辅助指标
    # "duration_ms": 0.0,     # 执行时间 - 不参与异常检测（波动大、受非GC因素影响）
}

# 是否检测执行时间异常（默认关闭，因为波动大、误报高）
DETECT_DURATION_ANOMALY = False


def oracle_ranking_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言: 基于统计排名基准模型的异常检测
    
    检测逻辑:
    1. 按JDK版本分组
    2. 计算各指标下各GC的排名
    3. 使用Z-Score检测排名偏离基准的异常
    4. 仅报告"欠表现"的异常（排名比预期差）
    5. 忽略sigma=0的情况（无法比较）
    
    Args:
        log_data: 测试日志数据
        file_path: 文件路径
    
    Returns:
        异常报告字典，无异常返回None
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # 获取基准模型加载器
    loader = get_baseline_loader()
    
    # 收集所有JDK版本
    jdk_versions = set()
    for result in test_results:
        jdk_version = result.get("jdk_version")
        if jdk_version:
            jdk_versions.add(jdk_version)
    
    all_anomalies = []
    
    # 对每个JDK版本进行分析
    for jdk_version in jdk_versions:
        jdk_anomalies = _analyze_jdk_version(
            test_results, 
            jdk_version, 
            loader,
            file_path
        )
        all_anomalies.extend(jdk_anomalies)
    
    if not all_anomalies:
        return None
    
    # 计算综合异常分数（只计算有效的z_score）
    total_score = 0.0
    for a in all_anomalies:
        z_score = a.get("z_score")
        if z_score is not None and not (isinstance(z_score, float) and (z_score != z_score)):  # 排除NaN
            total_score += a.get("weighted_z_score", 0)
    
    # 按指标分组统计
    metrics_affected = list(set(a["metric"] for a in all_anomalies))
    
    # 按严重程度分组统计
    severe_count = len([a for a in all_anomalies if a["severity"] == "severe"])
    moderate_count = len([a for a in all_anomalies if a["severity"] == "moderate"])
    
    return {
        "type": "ranking_anomaly",
        "file_path": file_path,
        "score": round(total_score, 4),
        "class_info": log_data.get("class_file_info", {}),
        "anomalies": all_anomalies,
        "summary": {
            "total_anomalies": len(all_anomalies),
            "severe_anomalies": severe_count,
            "moderate_anomalies": moderate_count,
            "metrics_affected": metrics_affected,
            "jdk_versions_analyzed": list(jdk_versions)
        },
        "analysis_note": "基于统计排名基准模型的Z-Score异常检测（仅检测欠表现）",
        "detection_params": {
            "z_threshold_moderate": Z_SCORE_THRESHOLD_MODERATE,
            "z_threshold_severe": Z_SCORE_THRESHOLD_SEVERE,
            "detect_overperform": DETECT_OVERPERFORM
        }
    }


def _analyze_jdk_version(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    loader,
    file_path: str
) -> List[Dict[str, Any]]:
    """
    分析单个JDK版本下的排名异常
    
    Args:
        test_results: 测试结果列表
        jdk_version: JDK版本
        loader: 基准模型加载器
        file_path: 文件路径
    
    Returns:
        异常列表
    """
    anomalies = []
    
    # 检查该JDK版本是否在基准模型中
    supported_jdks = loader.get_supported_jdk_versions()
    if jdk_version not in supported_jdks:
        return anomalies
    
    # 分析每个指标
    for metric_type in loader.get_supported_metrics():
        # 跳过执行时间指标（波动大、受非GC因素影响）
        if metric_type == "duration_ms" and not DETECT_DURATION_ANOMALY:
            continue
            
        metric_anomalies = _analyze_metric(
            test_results,
            jdk_version,
            metric_type,
            loader
        )
        anomalies.extend(metric_anomalies)
    
    return anomalies


def _analyze_metric(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    metric_type: str,
    loader
) -> List[Dict[str, Any]]:
    """
    分析单个指标的排名异常
    
    Args:
        test_results: 测试结果列表
        jdk_version: JDK版本
        metric_type: 指标类型
        loader: 基准模型加载器
    
    Returns:
        异常列表
    """
    anomalies = []
    
    # 检查是否需要过滤零值
    if loader.should_filter_zero(metric_type):
        if is_all_zero_for_metric(test_results, metric_type, jdk_version):
            return anomalies
    
    # 计算排名
    rankings = calculate_rankings(test_results, metric_type, jdk_version)
    
    if not rankings:
        return anomalies
    
    # 获取指标信息
    metric_info = loader.get_metric_info(metric_type)
    
    # 对每个GC检测异常
    for gc_type, rank_data in rankings.items():
        actual_rank = rank_data["rank"]
        actual_value = rank_data["value"]
        
        # 获取基准参数
        baseline_params = loader.get_baseline_params(metric_type, jdk_version, gc_type)
        
        if baseline_params is None:
            # 尝试使用整体基准
            overall_params = loader.get_overall_baseline_params(metric_type, gc_type)
            if overall_params is None:
                continue
            mu, sigma = overall_params
        else:
            mu, sigma, n = baseline_params
        
        # 跳过sigma=0的情况（无法进行有意义的比较）
        if sigma == 0:
            continue
        
        # 计算Z-Score
        z_score = calculate_z_score(actual_rank, mu, sigma)
        
        # z_score为None表示无法比较
        if z_score is None:
            continue
        
        # 分类异常（仅检测欠表现）
        severity, direction = classify_anomaly(
            z_score, 
            Z_SCORE_THRESHOLD_MODERATE,
            Z_SCORE_THRESHOLD_SEVERE,
            detect_overperform=DETECT_OVERPERFORM
        )
        
        if severity == AnomalySeverity.NONE:
            continue
        
        # 计算置信度
        confidence = calculate_confidence(z_score)
        
        # 获取权重
        weight = METRIC_WEIGHTS.get(metric_type, 0.5)
        
        # 构建异常记录
        anomaly = {
            "metric": metric_type,
            "metric_name": metric_info.get("name", metric_type) if metric_info else metric_type,
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "actual_rank": round(actual_rank, 2),
            "expected_rank_mu": round(mu, 3),
            "expected_rank_sigma": round(sigma, 3),
            "actual_value": round(actual_value, 4),
            "z_score": round(z_score, 4),
            "weighted_z_score": round(z_score * weight, 4),  # 对于欠表现，z_score为正
            "confidence": round(confidence, 4),
            "severity": severity.value,
            "direction": direction.value,
            "possible_causes": _get_possible_causes(metric_type, direction, z_score)
        }
        
        anomalies.append(anomaly)
    
    return anomalies


def _get_possible_causes(
    metric_type: str, 
    direction: AnomalyDirection, 
    z_score: float
) -> List[str]:
    """
    根据异常情况推测可能的原因
    
    Args:
        metric_type: 指标类型
        direction: 异常方向
        z_score: Z-Score值
    
    Returns:
        可能原因列表
    """
    causes = []
    
    if direction == AnomalyDirection.UNDERPERFORM:
        # 表现比预期差
        if metric_type == "duration_ms":
            causes.extend([
                "JIT编译优化失效",
                "内存压力异常",
                "线程竞争加剧",
                "GC开销增加"
            ])
        elif metric_type in ["gc_stw_time_ms", "max_stw_time_ms"]:
            causes.extend([
                "GC性能退化",
                "堆内存配置不当",
                "对象分配模式变化",
                "GC算法实现问题"
            ])
        elif metric_type == "total_gc_count":
            causes.extend([
                "GC触发频率异常",
                "内存泄漏",
                "对象存活率变化",
                "GC参数配置问题"
            ])
    
    return causes
