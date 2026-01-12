#!/usr/bin/env python3
"""
测试预言: 检测性能回归
规则: 随JDK版本升级，同一GC下的运行时长应该逐渐下降（允许50%误差）
"""
from typing import Dict, Any, Optional


def oracle_performance_regression(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言4: 检测性能回归
    规则: 随JDK版本升级，同一GC下的运行时长应该逐渐下降（允许100%误差）
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # GC类型分类函数（复用之前的）
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

    # 按GC类型和JDK版本分组，只选择成功执行的结果
    gc_jdk_groups = {}

    for result in test_results:
        # 只处理成功执行的结果
        if not (result.get("success", True) and result.get("exit_code", 0) == 0):
            continue

        jdk_version = result.get("jdk_version", "unknown")
        gc_type = classify_gc(result.get("GC_parameters", []))
        duration = result.get("duration_ms", 0)

        if gc_type not in gc_jdk_groups:
            gc_jdk_groups[gc_type] = {}

        # 如果同一GC+JDK组合有多个结果，取中位数或平均值
        if jdk_version not in gc_jdk_groups[gc_type]:
            gc_jdk_groups[gc_type][jdk_version] = []

        gc_jdk_groups[gc_type][jdk_version].append(duration)

    # 计算每个GC+JDK组合的平均执行时间
    gc_jdk_avg_times = {}
    for gc_type, jdk_versions in gc_jdk_groups.items():
        gc_jdk_avg_times[gc_type] = {}
        for jdk_version, durations in jdk_versions.items():
            if durations:  # 确保有数据
                avg_duration = sum(durations) / len(durations)
                gc_jdk_avg_times[gc_type][jdk_version] = round(avg_duration, 2)

    performance_regressions = []

    # 对每种GC类型分析性能趋势
    for gc_type, jdk_times in gc_jdk_avg_times.items():
        # 至少需要2个不同JDK版本才能分析趋势
        if len(jdk_times) < 2:
            continue

        # 将JDK版本转换为可比较的数值并排序
        try:
            # 处理JDK版本字符串（如 "1.8", "11", "17" 等）
            sorted_versions = sorted(jdk_times.keys(), key=lambda v: float(v) if v.replace('.', '').isdigit() else 0)
        except (ValueError, AttributeError):
            # 如果版本解析失败，跳过这个GC类型
            continue

        # 检查性能趋势
        regressions_in_gc = []

        for i in range(1, len(sorted_versions)):
            current_version = sorted_versions[i]
            previous_version = sorted_versions[i - 1]

            current_time = jdk_times[current_version]
            previous_time = jdk_times[previous_version]

            # 计算性能变化比例（允许50%的误差）
            if previous_time > 0:  # 避免除零
                change_ratio = current_time / previous_time

                # 如果当前版本比前一个版本慢超过100%，认为是性能回归
                if change_ratio > 3:
                    regressions_in_gc.append({
                        "gc_type": gc_type,
                        "from_version": previous_version,
                        "to_version": current_version,
                        "from_time_ms": previous_time,
                        "to_time_ms": current_time,
                        "change_ratio": round(change_ratio, 2),
                        "performance_change": f"变慢 {round((change_ratio - 1) * 100, 1)}%",
                        "threshold": 2
                    })

        if regressions_in_gc:
            performance_regressions.extend(regressions_in_gc)

    if performance_regressions:
        return {
            "type": "performance_regression",
            "file_path": file_path,
            "class_info": log_data.get("class_file_info", {}),
            "regressions": performance_regressions,
        }

    return None
