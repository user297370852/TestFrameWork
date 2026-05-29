#!/usr/bin/env python3
"""
测试预言: 检测GC次数异常
规则: 按GC类型分组，检测GC次数异常高的测试用例

基于前期分析，不同GC类型的稳定性:
serial > G1 >= parallel >= shenandoah > ZGC

阈值设置基于同种GC的中位数和平均数对比
"""
from typing import Dict, Any, Optional
import statistics


def oracle_gc_count_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言: 检测GC次数异常
    规则: 
    1. 过滤成功执行且GC count > 5的数据
    2. 按GC类型分组
    3. 基于GC类型稳定性设置不同阈值，与同种GC的中位数、平均数对比
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # GC类型分类函数
    def classify_gc_type(result: Dict[str, Any]) -> str:
        """根据GC参数识别GC类型"""
        gc_params = result.get("GC_parameters", [])
        params_str = " ".join(gc_params).upper()
        
        if "+USEZGC" in params_str:
            return "ZGC"
        elif "+USESHENANDOAHGC" in params_str:
            return "ShenandoahGC"
        elif "+USEG1GC" in params_str:
            return "G1GC"
        elif "+USEPARALLELGC" in params_str or "+USEPARALLELOLDGC" in params_str:
            return "ParallelGC"
        elif "+USESERIALGC" in params_str:
            return "SerialGC"
        else:
            return "Unknown"

    # 收集有效的GC结果数据（成功执行且GC count > 5）
    gc_data = []
    for result in test_results:
        # 只考虑成功执行的测试
        if not result.get("success", True) or result.get("exit_code", 0) != 0:
            continue
            
        gc_analysis = result.get("gc_analysis")
        if not gc_analysis:
            continue
            
        gc_count = gc_analysis.get("total_gc_count")
        if gc_count is None or gc_count <= 5:
            continue
            
        gc_type = classify_gc_type(result)
        jdk_version = result.get("jdk_version", "unknown")
        
        gc_data.append({
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "total_gc_count": gc_count
        })

    if not gc_data:
        return None

    # 按GC类型分组
    gc_type_groups = {}
    for data in gc_data:
        gc_type = data["gc_type"]
        if gc_type not in gc_type_groups:
            gc_type_groups[gc_type] = []
        gc_type_groups[gc_type].append(data)

    anomalies = []

    # 基于GC类型稳定性设置阈值倍数
    # 稳定性: serial > G1 >= parallel >= shenandoah > ZGC
    stability_thresholds = {
        "SerialGC": 6.0,      # 最稳定，使用较严格的阈值
        "G1GC": 6.0,          # 中等稳定
        "ParallelGC": 6.0,    # 中等稳定
        "ShenandoahGC": 8.0,  # 相对不稳定
        "ZGC": 8.0,           # 最不稳定，使用宽松阈值
        "Unknown": 4.0        # 未知类型使用中等阈值
    }

    # 先做同GC跨JDK的成对比较。该规则不使用当前样本集合的中位数作基线，
    # 避免单个极端GC次数把自身基线抬高而漏检。
    cross_version_anomalies = []
    for gc_type, gc_type_data in gc_type_groups.items():
        if len(gc_type_data) < 2:
            continue

        try:
            sorted_data = sorted(
                gc_type_data,
                key=lambda item: float(item["jdk_version"]) if str(item["jdk_version"]).replace('.', '').isdigit() else 0,
            )
        except (TypeError, ValueError):
            continue

        ratio_threshold = stability_thresholds.get(gc_type, stability_thresholds["Unknown"])
        for i in range(1, len(sorted_data)):
            prev = sorted_data[i - 1]
            curr = sorted_data[i]
            prev_count = prev["total_gc_count"]
            curr_count = curr["total_gc_count"]
            if prev_count <= 0 or curr_count <= 0:
                continue

            low = prev if prev_count <= curr_count else curr
            high = curr if prev_count <= curr_count else prev
            low_count = low["total_gc_count"]
            high_count = high["total_gc_count"]
            ratio = high_count / low_count
            absolute_increase = high_count - low_count

            # 同时要求倍率和绝对差，避免小用例中 1->10 这类无实际意义的波动。
            if ratio > ratio_threshold and absolute_increase >= 50:
                cross_version_anomalies.append({
                    "score": round(ratio, 4),
                    "info": (
                        f"{high['jdk_version']}-{gc_type}: GC次数异常，GC次数（{high_count}次）"
                        f"比JDK{low['jdk_version']}（{low_count}次）高{ratio:.1f}倍"
                    ),
                })

    if cross_version_anomalies:
        anomalies.extend(cross_version_anomalies)

    # 对每种GC类型进行分析
    for gc_type, gc_type_data in gc_type_groups.items():
        if len(gc_type_data) < 2:
            continue  # 至少需要2个数据点才能计算统计值
            
        # 计算该GC类型的统计数据
        gc_counts = [data["total_gc_count"] for data in gc_type_data]
        median_gc_count = statistics.median(gc_counts)
        mean_gc_count = statistics.mean(gc_counts)
        
        # 获取该GC类型的稳定性阈值
        stability_threshold = stability_thresholds.get(gc_type, stability_thresholds["Unknown"])
        
        # 设置检测阈值：基于中位数和平均数的较小值
        base_threshold = min(median_gc_count, mean_gc_count)
        threshold = base_threshold * stability_threshold
        
        # 检测异常高的GC次数
        for data in gc_type_data:
            gc_count = data["total_gc_count"]
            
            if gc_count > threshold:
                # 计算异常程度
                excess_ratio_threshold = (gc_count - threshold) / threshold
                
                anomalies.append({
                    "score": round(excess_ratio_threshold, 4),  # 异常分数：超出阈值的比例
                    "info": f"{data['jdk_version']}-{gc_type}: GC次数异常，GC次数（{gc_count}次）比同GC类型基准（{base_threshold:.2f}次）高{gc_count / base_threshold:.1f}倍"
                })

    # 如果发现异常，返回结果
    if anomalies:
        return {
            "type": "gc_count_anomaly",
            "file_path": file_path,
            "anomalies": anomalies
        }

    return None
