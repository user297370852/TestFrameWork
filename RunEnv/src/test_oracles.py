#!/usr/bin/env python3
"""
测试预言定义文件
每个预言都是一个独立的函数，仅在检测到异常时返回描述信息
"""

from typing import Dict, Any, List, Optional


def oracle_test_failure(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言1: 检测测试失败情况
    规则: 测试用例应该成功执行，但过滤掉环境相关的错误
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # 环境相关错误的关键词列表
    ENVIRONMENT_ERRORS = {
        "NoClassDefFoundError",
        "ClassNotFoundException",
        "BootstrapMethodError",
        "UnsupportedClassVersionError",
        "NoSuchMethodError",  # 可能由于版本不兼容
        "NoSuchFieldError",
        "IllegalAccessError",
        "InstantiationError",
        "VerifyError",
        "LinkageError",
        "java.lang.invoke",  # 方法句柄相关错误
        "java.lang.reflect",  # 反射相关错误
        "sun.misc",  # 内部API相关
        "com.sun",  # 内部API相关
    }

    def is_environment_error(output: str) -> bool:
        """判断错误是否是环境相关的"""
        output_upper = output.upper()

        # 检查是否包含环境错误关键词
        for error_keyword in ENVIRONMENT_ERRORS:
            if error_keyword.upper() in output_upper:
                return True

        # 检查特定的错误模式
        error_patterns = [
            "JAVA.LANG.INVOKE.",  # 方法句柄相关
            "JAVA.LANG.REFLECT.",  # 反射相关
            "SUN.MISC.",  # 内部API
            "COM.SUN.",  # 内部API
            "UNSUPPORTED CLASS VERSION",  # 版本不兼容
        ]

        for pattern in error_patterns:
            if pattern in output_upper:
                return True

        return False

    failed_tests = []
    environment_failures = []  # 记录环境相关失败，用于调试

    for result in test_results:
        if not result.get("success", True) or result.get("exit_code", 0) != 0:
            output = result.get("output", "")

            # 过滤环境相关错误
            if is_environment_error(output):
                environment_failures.append({
                    "jdk_version": result.get("jdk_version", "unknown"),
                    "jvm_parameters": result.get("jvm_parameters", []),
                    "exit_code": result.get("exit_code", -1),
                    "error_type": "environment_error",
                    "output_preview": output[:200] + "..." if len(output) > 200 else output
                })
                continue  # 跳过环境错误

            # 真正的程序逻辑错误
            failed_tests.append({
                "jdk_version": result.get("jdk_version", "unknown"),
                "jvm_parameters": result.get("jvm_parameters", []),
                "exit_code": result.get("exit_code", -1),
                "output": output,
                "duration_ms": result.get("duration_ms", 0)
            })

    # 如果有真正的程序逻辑错误，返回异常
    if failed_tests:
        result = {
            "type": "test_failure",
            "file_path": file_path,
            "class_info": log_data.get("class_file_info", {}),
            "failed_tests": failed_tests,
            "total_tests": len(test_results),
            "failed_count": len(failed_tests)
        }

        # 如果需要调试，可以添加环境失败信息
        if environment_failures:
            result["environment_failures_filtered"] = {
                "count": len(environment_failures),
                "samples": environment_failures[:3]  # 只显示前3个样本
            }

        return result

    return None


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
            "SerialGC": 7.5,  # SerialGC相对稳定
            "ParallelGC": 7.5,  # ParallelGC也比较稳定
            "G1GC": 8.0,  # G1GC有一定波动性
            "CMS": 10.0,  # CMS波动较大
            "ZGC": 6.0,  # ZGC是低延迟GC，应该相对稳定
            "ShenandoahGC": 6.0,  # ShenandoahGC也是低延迟GC
            "EpsilonGC": 3.0,  # EpsilonGC不做GC，应该非常稳定
            "Unknown": 8.0
        }

        # 检测该JDK版本内的慢测试
        for test in successful_tests:
            duration = test.get("duration_ms", 0)
            gc_type = classify_gc(test.get("jvm_parameters", []))

            threshold_ratio = gc_thresholds.get(gc_type, 8.0)
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
                        if ratio > 3.5:  # 低延迟GC之间差异不应过大
                            performance_anomalies.append({
                                "type": "low_latency_gc_discrepancy",
                                "jdk_version": jdk_version,
                                "gc1": gc1,
                                "gc2": gc2,
                                "gc1_median_ms": gc_medians[gc1],
                                "gc2_median_ms": gc_medians[gc2],
                                "ratio": round(ratio, 2),
                                "threshold": 3.5
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
                        if ratio > 6.0:  # 吞吐量GC之间允许较大差异
                            performance_anomalies.append({
                                "type": "throughput_gc_discrepancy",
                                "jdk_version": jdk_version,
                                "gc1": gc1,
                                "gc2": gc2,
                                "gc1_median_ms": gc_medians[gc1],
                                "gc2_median_ms": gc_medians[gc2],
                                "ratio": round(ratio, 2),
                                "threshold": 6.0
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


def oracle_missing_required_fields(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言3: 检测必需字段缺失
    规则: JSON文件必须包含基本的测试结果结构
    """
    if "test_results" not in log_data:
        return {
            "type": "missing_required_fields",
            "file_path": file_path,
            "missing_field": "test_results",
            "message": "JSON文件缺少必需的'test_results'字段"
        }

    return None


def oracle_performance_regression(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言4: 检测性能回归
    规则: 随JDK版本升级，同一GC下的运行时长应该逐渐下降（允许50%误差）
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
        gc_type = classify_gc(result.get("jvm_parameters", []))
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

                # 如果当前版本比前一个版本慢超过50%，认为是性能回归
                if change_ratio > 2:
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
            "analysis_note": "检测JDK版本升级时的性能回归（允许50%误差）",
            "gc_versions_analyzed": {
                gc_type: list(jdk_times.keys())
                for gc_type, jdk_times in gc_jdk_avg_times.items()
            }
        }

    return None


# 测试预言注册表
# 在此添加新的测试预言函数
TEST_ORACLES = [
    oracle_missing_required_fields,
    oracle_test_failure,
    oracle_performance_anomaly,
    oracle_performance_regression,
]