#!/usr/bin/env python3
"""
测试预言: 基于 V2.1 三通道鲁棒检测的异常检测

通道A (主信号): 自基线退化 (Self-Regret)
通道B (辅助信号): 排名尾概率 (Rank Tail Probability) + 幅度门控
通道C (极端值信号): log 尺度鲁棒离群分数

支持两种模式:
- hybrid_v2: 三通道鲁棒检测（需要V2字段）
- legacy_v1: 旧版排名Z-Score检测（向后兼容）
"""
from typing import Dict, Any, Optional, List, Tuple
import statistics
from .baseline_loader import get_baseline_loader
from .ranking_utils import (
    MetricType,
    calculate_rankings,
    calculate_z_score,
    classify_anomaly,
    calculate_confidence,
    is_all_zero_for_metric,
    AnomalySeverity,
    AnomalyDirection,
    # V2.1 新增函数
    calculate_regret,
    robust_z,
    calculate_log_tail_score,
    calculate_rank_tail_prob_from_hist,
    calculate_rank_surprise_score,
    calculate_gate_factor,
)


# ============================================================
# 检测模式配置
# ============================================================
# 可选值: "hybrid_v2" | "legacy_v1"
# hybrid_v2: 三通道鲁棒检测（优先使用V2字段，缺失时回退到V1）
# legacy_v1: 旧版排名Z-Score检测
DETECTION_MODE = "hybrid_v2"

# ============================================================
# V1 配置（旧版兼容）
# ============================================================
Z_SCORE_THRESHOLD_MODERATE = 2.5
Z_SCORE_THRESHOLD_SEVERE = 3.5
DETECT_OVERPERFORM = False

# 绝对值阈值配置（用于减少误报）
ABSOLUTE_THRESHOLD_STW_MS = 1.0
ABSOLUTE_THRESHOLD_GC_COUNT_DIFF = 5
ENABLE_ABSOLUTE_THRESHOLD_CHECK = True

# 指标权重
METRIC_WEIGHTS = {
    "gc_stw_time_ms": 1.0,
    "max_stw_time_ms": 1.0,
    "total_gc_count": 1.0,
}

# 是否检测执行时间异常
DETECT_DURATION_ANOMALY = False

# ============================================================
# V2.1 配置（三通道检测）
# ============================================================
# 三通道权重（见设计文档第4.1节）
CHANNEL_WEIGHTS = {
    "w_self": 0.60,   # 通道A：自基线退化
    "w_rank": 0.15,   # 通道B：排名尾概率
    "w_tail": 0.15,   # 通道C：极端值
}

# 触发规则阈值（见设计文档第4.2节）
TRIGGER_THRESHOLDS = {
    "z_self_threshold": 3.0,      # Z_self > 此值触发
    "z_tail_threshold": 4.5,      # Z_tail > 此值触发（需配合lambda条件）
    "s_rank_threshold": 2.0,      # S_rank > 此值触发（需配合Z_self条件）
    "z_self_with_rank": 1.5,      # S_rank触发时的Z_self辅助条件
}

# 综合分数阈值（见设计文档第4.3节）
SEVERITY_THRESHOLDS = {
    "high_s": 4.5,      # S >= 此值为高严重度
    "medium_s": 3.0,    # S >= 此值为中等严重度
    "low_s": 2.0,       # S >= 此值为低严重度
}

# 多指标聚合权重（见设计文档第4.4节）
METRIC_BETA_WEIGHTS = {
    "gc_stw_time_ms": 1.0,
    "max_stw_time_ms": 1.0,
    "total_gc_count": 0.8,
    "duration_ms": 0.4,
}


def oracle_ranking_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言: 基于 V2.1 三通道鲁棒检测的异常检测
    
    检测逻辑:
    1. 按JDK版本分组
    2. 计算各指标下各GC的排名
    3. 使用三通道检测框架：
       - 通道A: 自基线退化 (regret + robust Z)
       - 通道B: 排名尾概率 (经验分布 + 门控)
       - 通道C: log尺度极端值检测
    4. 综合评分与触发规则判断异常
    
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
        jdk_anomalies, _note = _analyze_jdk_version(
            test_results, 
            jdk_version, 
            loader,
            file_path
        )
        all_anomalies.extend(jdk_anomalies)
    
    if not all_anomalies:
        return None
    
    # 计算综合异常分数（从每个 anomaly 的 score 字段汇总）
    total_score = 0.0
    for a in all_anomalies:
        s = a.get("score")
        if isinstance(s, (int, float)):
            total_score += float(s)
    
    # 构建顶层 info 列表（与基础预言输出格式一致）
    info_list = [a["info"] for a in all_anomalies if "info" in a]

    return {
        "type": "ranking_anomaly",
        "file_path": file_path,
        "score": round(total_score, 4),
        "info": info_list,
        "anomalies": all_anomalies,
    }


def _analyze_jdk_version(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    loader,
    file_path: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    分析单个JDK版本下的排名异常
    
    Args:
        test_results: 测试结果列表
        jdk_version: JDK版本
        loader: 基准模型加载器
        file_path: 文件路径
    
    Returns:
        (异常列表, 分析说明)
    """
    anomalies = []
    analysis_note = None
    
    # 检查该JDK版本是否在基准模型中
    supported_jdks = loader.get_supported_jdk_versions()
    if jdk_version not in supported_jdks:
        return anomalies, f"JDK {jdk_version} 不在基准模型中"
    
    # 判断是否有V2字段（用于决定检测模式）
    has_v2 = False
    for metric_type in loader.get_supported_metrics():
        for gc_type in loader.get_gc_types_for_jdk(jdk_version):
            if loader.has_v2_fields(metric_type, jdk_version, gc_type):
                has_v2 = True
                break
        if has_v2:
            break
    
    # 根据配置和字段可用性决定检测模式
    use_v2 = DETECTION_MODE == "hybrid_v2" and has_v2
    if DETECTION_MODE == "hybrid_v2" and not has_v2:
        analysis_note = "缺少V2字段，回退到legacy_v1模式"
    
    # 分析每个指标
    for metric_type in loader.get_supported_metrics():
        # 跳过执行时间指标（波动大、受非GC因素影响）
        if metric_type == "duration_ms" and not DETECT_DURATION_ANOMALY:
            continue
        
        if use_v2:
            metric_anomalies = _analyze_metric_v2(
                test_results,
                jdk_version,
                metric_type,
                loader
            )
        else:
            metric_anomalies = _analyze_metric_v1(
                test_results,
                jdk_version,
                metric_type,
                loader
            )
        anomalies.extend(metric_anomalies)
    
    return anomalies, analysis_note


def _analyze_metric_v1(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    metric_type: str,
    loader
) -> List[Dict[str, Any]]:
    """
    V1模式：基于排名Z-Score的异常检测（旧版兼容）
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
        
        # 跳过sigma=0的情况
        if sigma == 0:
            continue
        
        # 计算Z-Score
        z_score = calculate_z_score(actual_rank, mu, sigma)
        
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

        # 绝对值阈值检查
        if ENABLE_ABSOLUTE_THRESHOLD_CHECK:
            if _is_within_absolute_threshold(metric_type, actual_value, rankings):
                continue

        # 计算置信度
        confidence = calculate_confidence(z_score)
        
        # 获取权重
        weight = METRIC_WEIGHTS.get(metric_type, 0.5)
        
        # 获取最优值用于生成描述
        best_value = min(r.get("value", actual_value) for r in rankings.values()) if rankings else actual_value
        
        # 生成可读描述（V1模式）
        severity_map = {"severe": "high", "moderate": "medium", "none": "low"}
        v2_severity = severity_map.get(severity.value, severity.value)
        description = _generate_anomaly_description(
            metric_type, jdk_version, gc_type, actual_value, best_value,
            v2_severity, [f"z_score_{direction.value}"], metric_info
        )
        
        # 构建异常记录（与基础预言输出格式对齐）
        anomaly = {
            "metric": metric_type,
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "actual_value": round(actual_value, 4),
            "actual_rank": round(actual_rank, 2),
            "z_score": round(z_score, 4),
            "severity": severity.value if hasattr(severity, 'value') else severity,
            "detection_mode": "legacy_v1",
            "score": round(z_score * weight, 4),
            "info": description,
        }
        
        anomalies.append(anomaly)
    
    return anomalies


def _analyze_metric_v2(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    metric_type: str,
    loader
) -> List[Dict[str, Any]]:
    """
    V2模式：三通道鲁棒检测
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
    
    # 获取指标参数
    tau = loader.get_metric_tau(metric_type)
    lambda_m = loader.get_metric_lambda(metric_type)
    
    # 找出组内最优值和中位数
    values_by_gc = {gc: data["value"] for gc, data in rankings.items()}
    best_value = min(values_by_gc.values()) if values_by_gc else 0
    values_list = sorted(list(values_by_gc.values()))
    median_value = statistics.median(values_list) if values_list else 0
    
    # 计算通道C：log尺度尾部分数（对所有GC一起计算）
    tail_scores = calculate_log_tail_score(values_by_gc)
    
    # 对每个GC检测异常
    for gc_type, rank_data in rankings.items():
        actual_rank = rank_data["rank"]
        actual_value = rank_data["value"]
        
        # 获取基线参数
        baseline_params = loader.get_baseline_params(metric_type, jdk_version, gc_type)
        regret_baseline = loader.get_regret_baseline(metric_type, jdk_version, gc_type)
        rank_hist = loader.get_rank_hist(metric_type, jdk_version, gc_type)
        
        # 如果没有V2字段，尝试回退到整体基线
        if regret_baseline is None:
            regret_baseline = loader.get_overall_regret_baseline(metric_type, gc_type)
        if rank_hist is None:
            rank_hist = loader.get_overall_rank_hist(metric_type, gc_type)
        
        # 如果仍然没有V2字段，回退到V1
        if regret_baseline is None and rank_hist is None:
            return _analyze_metric_v1_fallback(
                test_results, jdk_version, metric_type, loader, 
                rankings, gc_type, rank_data, baseline_params
            )
        
        # ============ 通道A：自基线退化 ============
        regret = calculate_regret(actual_value, best_value)
        
        z_self = 0.0
        regret_q99 = None
        regret_median = None
        regret_mad = None
        
        if regret_baseline:
            regret_median = regret_baseline.get('regret_median')
            regret_mad = regret_baseline.get('regret_mad')
            regret_q99 = regret_baseline.get('regret_q99')
            
            if regret_median is not None and regret_mad is not None:
                z_self = robust_z(regret, regret_median, regret_mad)
        
        # 只取退化方向
        z_self_positive = max(0, z_self)
        
        # ============ 通道B：排名尾概率 ============
        p_rank = 0.5
        s_rank_raw = 0.0
        gate = 0.0
        s_rank = 0.0
        
        if rank_hist:
            p_rank = calculate_rank_tail_prob_from_hist(actual_rank, rank_hist)
            s_rank_raw = calculate_rank_surprise_score(p_rank)
            gate = calculate_gate_factor(regret, tau)
            s_rank = s_rank_raw * gate
        
        # ============ 通道C：log尺度极端值 ============
        z_tail = 0.0
        
        if gc_type in tail_scores:
            z_tail = tail_scores[gc_type]["z_tail"]
        
        # 只取退化方向
        z_tail_positive = max(0, z_tail)
        
        # ============ 综合评分 ============
        w = CHANNEL_WEIGHTS
        s_metric = (w["w_self"] * z_self_positive + 
                   w["w_rank"] * s_rank + 
                   w["w_tail"] * z_tail_positive)
        
        # ============ 触发规则判断 ============
        trigger_rules = []
        is_anomaly = False
        severity = "low"
        
        # 规则1: regret > regret_q99
        if regret_q99 is not None and regret > regret_q99:
            trigger_rules.append("regret_exceeds_q99")
            is_anomaly = True
        
        # 规则2: Z_self > 3.0
        if z_self_positive > TRIGGER_THRESHOLDS["z_self_threshold"]:
            trigger_rules.append("z_self_exceeds_threshold")
            is_anomaly = True
        
        # 规则3: Z_tail > 4.5 且 x > lambda * x_mid
        if (z_tail_positive > TRIGGER_THRESHOLDS["z_tail_threshold"] and 
            actual_value > lambda_m * median_value):
            trigger_rules.append("z_tail_extreme_with_gap")
            is_anomaly = True
            severity = "high"
        
        # 规则4: S_rank > 2.0 且 Z_self > 1.5
        if (s_rank > TRIGGER_THRESHOLDS["s_rank_threshold"] and 
            z_self_positive > TRIGGER_THRESHOLDS["z_self_with_rank"]):
            trigger_rules.append("rank_surprise_with_self_degradation")
            is_anomaly = True
        
        # 综合分数触发
        if s_metric >= SEVERITY_THRESHOLDS["high_s"]:
            severity = "high"
            is_anomaly = True
            if "s_metric_high" not in trigger_rules:
                trigger_rules.append("s_metric_high")
        elif s_metric >= SEVERITY_THRESHOLDS["medium_s"]:
            if severity != "high":
                severity = "medium"
            is_anomaly = True
            if "s_metric_medium" not in trigger_rules:
                trigger_rules.append("s_metric_medium")
        elif s_metric >= SEVERITY_THRESHOLDS["low_s"]:
            if severity not in ["high", "medium"]:
                severity = "low"
            is_anomaly = True
        
        if not is_anomaly:
            continue
        
        # 绝对值阈值检查（减少误报）
        if ENABLE_ABSOLUTE_THRESHOLD_CHECK:
            if _is_within_absolute_threshold(metric_type, actual_value, rankings):
                continue
        
        # 获取权重
        beta = METRIC_BETA_WEIGHTS.get(metric_type, 0.5)
        
        # 生成可读描述
        description = _generate_anomaly_description(
            metric_type, jdk_version, gc_type, actual_value, best_value,
            severity, trigger_rules, metric_info
        )
        
        # 构建异常记录（与基础预言输出格式对齐）
        anomaly = {
            "metric": metric_type,
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "actual_value": round(actual_value, 4),
            "actual_rank": round(actual_rank, 2),
            "s_metric": round(s_metric, 4),
            "severity": severity,
            "detection_mode": "hybrid_v2",
            "score": round(s_metric * beta, 4),
            "info": description,
        }
        
        anomalies.append(anomaly)
    
    return anomalies


def _analyze_metric_v1_fallback(
    test_results: List[Dict[str, Any]],
    jdk_version: str,
    metric_type: str,
    loader,
    rankings: Dict[str, Dict[str, Any]],
    gc_type: str,
    rank_data: Dict[str, Any],
    baseline_params
) -> List[Dict[str, Any]]:
    """
    V2模式中单个GC回退到V1模式的处理
    """
    anomalies = []
    metric_info = loader.get_metric_info(metric_type)
    
    actual_rank = rank_data["rank"]
    actual_value = rank_data["value"]
    
    if baseline_params is None:
        overall_params = loader.get_overall_baseline_params(metric_type, gc_type)
        if overall_params is None:
            return anomalies
        mu, sigma = overall_params
    else:
        mu, sigma, n = baseline_params
    
    if sigma == 0:
        return anomalies
    
    z_score = calculate_z_score(actual_rank, mu, sigma)
    if z_score is None:
        return anomalies
    
    severity, direction = classify_anomaly(
        z_score, 
        Z_SCORE_THRESHOLD_MODERATE,
        Z_SCORE_THRESHOLD_SEVERE,
        detect_overperform=DETECT_OVERPERFORM
    )
    
    if severity == AnomalySeverity.NONE:
        return anomalies
    
    if ENABLE_ABSOLUTE_THRESHOLD_CHECK:
        if _is_within_absolute_threshold(metric_type, actual_value, rankings):
            return anomalies
    
    confidence = calculate_confidence(z_score)
    weight = METRIC_WEIGHTS.get(metric_type, 0.5)
    
    # 获取最优值用于生成描述
    best_value = min(r.get("value", actual_value) for r in rankings.values()) if rankings else actual_value
    
    # 生成可读描述（V1 fallback模式）
    severity_map = {"severe": "high", "moderate": "medium", "none": "low"}
    v2_severity = severity_map.get(severity.value, severity.value)
    description = _generate_anomaly_description(
        metric_type, jdk_version, gc_type, actual_value, best_value,
        v2_severity, [f"z_score_{direction.value}"], metric_info
    )
    
    anomaly = {
        "metric": metric_type,
        "jdk_version": jdk_version,
        "gc_type": gc_type,
        "actual_value": round(actual_value, 4),
        "actual_rank": round(actual_rank, 2),
        "z_score": round(z_score, 4),
        "severity": severity.value if hasattr(severity, 'value') else severity,
        "detection_mode": "legacy_v1_fallback",
        "score": round(z_score * weight, 4),
        "info": description,
    }
    
    anomalies.append(anomaly)
    return anomalies


def _is_within_absolute_threshold(
    metric_type: str,
    actual_value: float,
    rankings: Dict[str, Dict[str, Any]]
) -> bool:
    """
    检查指标绝对值是否在合理范围内（用于减少误报）
    """
    # STW时间绝对值检查
    if metric_type in ["gc_stw_time_ms", "max_stw_time_ms"]:
        if actual_value < ABSOLUTE_THRESHOLD_STW_MS:
            return True
    
    # GC次数差异检查
    if metric_type == "total_gc_count":
        min_gc_count = float('inf')
        for gc_type, rank_data in rankings.items():
            gc_count = rank_data.get("value", 0)
            if gc_count < min_gc_count:
                min_gc_count = gc_count
        
        gc_count_diff = actual_value - min_gc_count
        if gc_count_diff < ABSOLUTE_THRESHOLD_GC_COUNT_DIFF:
            return True
    
    return False


def _generate_anomaly_description(
    metric_type: str,
    jdk_version: str,
    gc_type: str,
    actual_value: float,
    best_value: float,
    severity: str,
    trigger_rules: List[str],
    metric_info: Optional[Dict[str, Any]]
) -> str:
    """
    生成人类可读的异常描述
    
    Args:
        metric_type: 指标类型
        jdk_version: JDK版本
        gc_type: GC类型
        actual_value: 实际值
        best_value: 最优值
        severity: 严重程度
        trigger_rules: 触发规则
        metric_info: 指标信息
    
    Returns:
        可读的异常描述字符串
    """
    # 指标名称映射
    metric_names = {
        "gc_stw_time_ms": "GC暂停时间",
        "max_stw_time_ms": "最大单次暂停时间",
        "total_gc_count": "GC次数",
        "duration_ms": "执行时间"
    }
    
    metric_name = metric_names.get(metric_type, metric_type)
    
    # 计算与最优值的比较
    if best_value > 0:
        ratio = actual_value / best_value
    else:
        ratio = 1.0
    
    # 格式化值和倍数
    if actual_value >= 1000:
        value_str = f"{actual_value:.0f}"
    elif actual_value >= 1:
        value_str = f"{actual_value:.3f}"
    else:
        value_str = f"{actual_value:.4f}"
    
    if best_value >= 1000:
        best_str = f"{best_value:.0f}"
    elif best_value >= 1:
        best_str = f"{best_value:.3f}"
    else:
        best_str = f"{best_value:.4f}"
    
    # 获取指标单位
    unit = ""
    if metric_type in ("gc_stw_time_ms", "max_stw_time_ms", "duration_ms"):
        unit = "ms"
    elif metric_type == "total_gc_count":
        unit = "次"
    
    # 构建描述（与基础预言格式对齐："{jdk}-{gc}: {指标}异常，..."）
    if ratio > 1.1:
        desc = f"{jdk_version}-{gc_type}: {metric_name}异常，{metric_name}（{value_str}{unit}）比组内最优（{best_str}{unit}）高{ratio:.1f}倍"
    else:
        desc = f"{jdk_version}-{gc_type}: {metric_name}异常，{metric_name}（{value_str}{unit}）接近组内最优但触发了统计检测"
    
    # 添加所有触发原因（用分号分隔）
    reasons = []
    if "regret_exceeds_q99" in trigger_rules:
        reasons.append("超过历史99分位")
    if "z_self_exceeds_threshold" in trigger_rules:
        reasons.append("相对自身历史退化明显")
    if "z_tail_extreme_with_gap" in trigger_rules:
        reasons.append("极端离群值")
    if "rank_surprise_with_self_degradation" in trigger_rules:
        reasons.append("排名异常且幅度退化")
    if "s_metric_high" in trigger_rules:
        reasons.append("综合分数高")
    if "s_metric_medium" in trigger_rules:
        reasons.append("综合分数中")
    if reasons:
        desc += "（" + "；".join(reasons) + "）"
    
    return desc


def generate_summary_description(anomalies: List[Dict[str, Any]]) -> str:
    """
    为一组异常生成汇总描述
    
    Args:
        anomalies: 异常列表
    
    Returns:
        汇总描述字符串
    """
    if not anomalies:
        return ""
    
    # 按 (jdk_version, gc_type) 分组
    groups = {}
    for a in anomalies:
        key = (a.get("jdk_version", "?"), a.get("gc_type", "?"))
        if key not in groups:
            groups[key] = []
        groups[key].append(a)
    
    # 生成每组的一句话描述
    parts = []
    for (jdk, gc), group_anomalies in groups.items():
        metrics = [a.get("metric", "?") for a in group_anomalies]
        # 简化指标名称
        metric_short_names = {
            "gc_stw_time_ms": "暂停时间",
            "max_stw_time_ms": "最大暂停",
            "total_gc_count": "GC次数",
            "duration_ms": "执行时间"
        }
        short_metrics = [metric_short_names.get(m, m) for m in metrics]
        unique_metrics = list(dict.fromkeys(short_metrics))  # 去重保序
        
        severity_count = {"high": 0, "medium": 0, "low": 0}
        for a in group_anomalies:
            sev = a.get("severity", "low")
            if sev in severity_count:
                severity_count[sev] += 1
        
        # 构建描述
        if severity_count["high"] > 0:
            sev_str = f"{severity_count['high']}处高严重度"
        elif severity_count["medium"] > 0:
            sev_str = f"{severity_count['medium']}处中严重度"
        else:
            sev_str = f"{severity_count['low']}处低严重度"
        
        metrics_str = "、".join(unique_metrics[:3])  # 最多显示3个指标
        if len(unique_metrics) > 3:
            metrics_str += f"等{len(unique_metrics)}个指标"
        
        parts.append(f"JDK{jdk}的{gc}在{metrics_str}上{sev_str}")
    
    # 合并描述
    if len(parts) == 1:
        return parts[0]
    elif len(parts) <= 3:
        return "；".join(parts)
    else:
        return "；".join(parts[:3]) + f"；共{len(parts)}个组合异常"