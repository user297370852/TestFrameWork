#!/usr/bin/env python3
"""
测试预言: 检测性能异常
规则: 按JDK版本分组，在JDK版本内进行GC类型感知的性能分析
"""
from typing import Dict, Any, Optional


def oracle_performance_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言2: 检测性能异常
    规则: 按JDK版本分组，在JDK版本内进行GC类型感知的性能分析
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # GC类型分类
    def classify_gc(jvm_parameters):
        params = [p.upper() for p in jvm_parameters]

        if "-XX:+USEZGC" in params:
            return "ZGC"
        elif "-XX:+USESHENANDOAHGC" in params:
            return "ShenandoahGC"
        elif "-XX:+USEEPSILONGC" in params:
            return "EpsilonGC"
        elif "-XX:+USEG1GC" in params:
            return "G1GC"
        elif "-XX:+USEPARALLELGC" in params or "-XX:+USEPARALLELOLDGC" in params:
            return "ParallelGC"
        elif "-XX:+USESERIALGC" in params:
            return "SerialGC"
        elif "-XX:+USECONCMARKSWEEPGC" in params or "-XX:+USEPARNEWGC" in params:
            return "CMS"
        else:
            return "Unknown"

    # 按JDK版本分组
    jdk_groups = {}
    for result in test_results:
        jdk_version = result.get("jdk_version", "unknown")
        if jdk_version not in jdk_groups:
            jdk_groups[jdk_version] = []
        jdk_groups[jdk_version].append(result)

    slow_tests = []
    performance_anomalies = []

    # 对每个JDK版本组进行性能分析
    for jdk_version, group_results in jdk_groups.items():
        # 获取该JDK版本内所有成功测试
        successful_tests = [
            result for result in group_results
            if result.get("success", True) and result.get("exit_code", 0) == 0
        ]

        # 至少需要2个成功测试才能进行时间分析
        if len(successful_tests) < 2:
            continue

        # 计算该JDK版本内的整体性能基准
        all_durations = [test.get("duration_ms", 0) for test in successful_tests]
        min_duration = min(all_durations)
        median_duration = sorted(all_durations)[len(all_durations) // 2]

        # 根据GC类型设置不同的阈值
        gc_thresholds = {
            "SerialGC": 15,  # SerialGC相对稳定
            "ParallelGC": 15,  # ParallelGC也比较稳定
            "G1GC": 15.0,  # G1GC有一定波动性
            "CMS": 20.0,  # CMS波动较大
            "ZGC": 5.0,  # ZGC是低延迟GC，应该相对稳定
            "ShenandoahGC": 15.0,  # ShenandoahGC也是低延迟GC
            "EpsilonGC": 5.0,  # EpsilonGC不做GC，应该非常稳定
            "Unknown": 15.0
        }

        # 检测该JDK版本内的慢测试
        for test in successful_tests:
            duration = test.get("duration_ms", 0)
            gc_type = classify_gc(test.get("GC_parameters", []))

            threshold_ratio = gc_thresholds.get(gc_type, 15.0)
            threshold = min_duration * threshold_ratio

            # 双重检查：既要超过阈值，也要显著高于中位数
            if duration > threshold and duration > median_duration * 3:
                slow_tests.append({
                    "jdk_version": jdk_version,
                    "gc_type": gc_type,
                    "jvm_parameters": test.get("jvm_parameters", []),
                    "duration_ms": duration,
                    "threshold": round(threshold, 2),
                    "min_duration_in_jdk": min_duration,
                    "median_duration_in_jdk": median_duration,
                    "ratio_to_min": round(duration / min_duration, 2),
                    "ratio_to_median": round(duration / median_duration, 2),
                    "threshold_ratio": threshold_ratio
                })

        # 同JDK版本内，按GC类型分组进行统计分析
        gc_groups = {}
        for test in successful_tests:
            gc_type = classify_gc(test.get("jvm_parameters", []))
            if gc_type not in gc_groups:
                gc_groups[gc_type] = []
            gc_groups[gc_type].append(test.get("duration_ms", 0))

        # 分析相似GC类型之间的性能差异
        gc_types_present = list(gc_groups.keys())

        # 低延迟GC对比
        low_latency_gcs = ["ZGC", "ShenandoahGC"]
        present_low_latency = [gc for gc in low_latency_gcs if gc in gc_types_present]
        if len(present_low_latency) >= 2:
            # 计算每种低延迟GC的中位数性能
            gc_medians = {}
            for gc_type in present_low_latency:
                if len(gc_groups[gc_type]) >= 1:  # 至少有一个数据点
                    gc_medians[gc_type] = sorted(gc_groups[gc_type])[len(gc_groups[gc_type]) // 2]

            if len(gc_medians) >= 2:
                gc_list = list(gc_medians.keys())
                for i in range(len(gc_list)):
                    for j in range(i + 1, len(gc_list)):
                        gc1, gc2 = gc_list[i], gc_list[j]
                        ratio = max(gc_medians[gc1], gc_medians[gc2]) / min(gc_medians[gc1], gc_medians[gc2])
                        if ratio > 5:  # 低延迟GC之间差异不应过大
                            performance_anomalies.append({
                                "type": "low_latency_gc_discrepancy",
                                "jdk_version": jdk_version,
                                "gc1": gc1,
                                "gc2": gc2,
                                "gc1_median_ms": gc_medians[gc1],
                                "gc2_median_ms": gc_medians[gc2],
                                "ratio": round(ratio, 2),
                                "threshold": 5
                            })

        # 吞吐量GC对比
        throughput_gcs = ["SerialGC", "ParallelGC", "G1GC"]
        present_throughput = [gc for gc in throughput_gcs if gc in gc_types_present]
        if len(present_throughput) >= 2:
            gc_medians = {}
            for gc_type in present_throughput:
                if len(gc_groups[gc_type]) >= 1:
                    gc_medians[gc_type] = sorted(gc_groups[gc_type])[len(gc_groups[gc_type]) // 2]

            if len(gc_medians) >= 2:
                gc_list = list(gc_medians.keys())
                for i in range(len(gc_list)):
                    for j in range(i + 1, len(gc_list)):
                        gc1, gc2 = gc_list[i], gc_list[j]
                        ratio = max(gc_medians[gc1], gc_medians[gc2]) / min(gc_medians[gc1], gc_medians[gc2])
                        if ratio > 10.0:  # 吞吐量GC之间允许较大差异
                            performance_anomalies.append({
                                "type": "throughput_gc_discrepancy",
                                "jdk_version": jdk_version,
                                "gc1": gc1,
                                "gc2": gc2,
                                "gc1_median_ms": gc_medians[gc1],
                                "gc2_median_ms": gc_medians[gc2],
                                "ratio": round(ratio, 2),
                                "threshold": 10.0
                            })

    # 组合所有性能异常
    all_performance_issues = []
    if slow_tests:
        all_performance_issues.append({
            "subtype": "slow_tests_within_jdk",
            "slow_tests": slow_tests
        })

    if performance_anomalies:
        all_performance_issues.append({
            "subtype": "cross_gc_comparison",
            "anomalies": performance_anomalies
        })

    if all_performance_issues:
        return {
            "type": "performance_anomaly",
            "file_path": file_path,
            "class_info": log_data.get("class_file_info", {}),
            "performance_issues": all_performance_issues,
            "analysis_note": "基于JDK版本分组和GC类型感知的性能分析"
        }

    return None
