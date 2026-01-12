#!/usr/bin/env python3
"""
测试预言: 检测GC开销比例异常
规则: 
1. GC次数必须大于10次才认为数据有意义
2. GC_overhead_ratio = gc_stw_time_ms / duration_ms
3. 同一JDK内，某GC的GC_overhead_ratio高于其他GC > 3倍中位数
4. 同一GC版本升级，GC_overhead_ratio显著上升（>50%且绝对值>5%）
"""
from typing import Dict, Any, Optional
import statistics


def oracle_gc_overhead_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言: 检测GC开销比例异常
    规则: 基于GC开销比例的差分测试
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # 识别GC类型的函数
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

    # 收集所有有效的GC结果数据（过滤GC次数<=10的）
    gc_data = []
    for result in test_results:
        gc_analysis = result.get("gc_analysis")
        if not gc_analysis:
            continue
            
        gc_stw_time = gc_analysis.get("gc_stw_time_ms")
        total_gc_count = gc_analysis.get("total_gc_count")
        duration_ms = result.get("duration_ms")
        
        if gc_stw_time is None or total_gc_count is None or duration_ms is None:
            continue
            
        # 只考虑GC次数大于10次的数据
        if total_gc_count <= 10:
            continue
            
        gc_type = classify_gc_type(result)
        jdk_version = result.get("jdk_version", "unknown")
        
        # 计算GC开销比例
        gc_overhead_ratio = gc_stw_time / duration_ms if duration_ms > 0 else 0
        
        gc_data.append({
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "gc_stw_time_ms": gc_stw_time,
            "duration_ms": duration_ms,
            "total_gc_count": total_gc_count,
            "gc_overhead_ratio": gc_overhead_ratio,
            "gc_overhead_percentage": gc_overhead_ratio * 100,  # 转换为百分比
            "gc_parameters": result.get("GC_parameters", []),
            "test_timestamp": result.get("test_timestamp", "unknown")
        })

    if not gc_data:
        return None

    anomalies = []

    # DEBUG: 检测GC开销比例超过100%的明显错误
    debug_anomalies = []
    for data in gc_data:
        if data["gc_overhead_ratio"] > 1.0:  # 超过100%
            debug_anomalies.append({
                "anomaly_type": "debug_gc_overhead_over_100_percent",
                "jdk_version": data["jdk_version"],
                "gc_type": data["gc_type"],
                "gc_overhead_percentage": data["gc_overhead_percentage"],
                "gc_stw_time_ms": data["gc_stw_time_ms"],
                "duration_ms": data["duration_ms"],
                "total_gc_count": data["total_gc_count"],
                "description": f"DEBUG: {data['gc_type']} GC开销比例 ({data['gc_overhead_percentage']:.2f}%) 超过100%，这表明数据有误！",
                "details": {
                    "gc_stw_time_ms": data["gc_stw_time_ms"],
                    "duration_ms": data["duration_ms"],
                    "ratio": data["gc_overhead_ratio"],
                    "gc_count": data["total_gc_count"],
                    "note": "GC暂停时间不应超过程序总运行时间"
                }
            })
    
    if debug_anomalies:
        anomalies.extend(debug_anomalies)

    # 1. 同一JDK内GC开销比例对比异常
    jdk_groups = {}
    for data in gc_data:
        jdk_version = data["jdk_version"]
        if jdk_version not in jdk_groups:
            jdk_groups[jdk_version] = []
        jdk_groups[jdk_version].append(data)

    jdk_comparison_anomalies = []
    for jdk_version, jdk_gc_data in jdk_groups.items():
        # 计算该JDK版本内所有GC的开销比例
        overhead_ratios = [data["gc_overhead_ratio"] for data in jdk_gc_data]
        
        if len(overhead_ratios) < 2:  # 至少需要2个GC才能比较
            continue
            
        # 计算中位数
        median_ratio = statistics.median(overhead_ratios)
        
        # 检查是否有GC的开销比例超过中位数阈值
        for data in jdk_gc_data:
            threshold = 3 
            if data["gc_type"] == "SerialGC":
                threshold = 20
            elif data["gc_type"] == "ParallelGC":
                threshold = 10
            elif data["gc_type"] == "G1GC":
                threshold = 5

            if data["gc_overhead_ratio"] > median_ratio * threshold:
                jdk_comparison_anomalies.append({
                    "anomaly_type": "jdk_internal_overhead_comparison",
                    "jdk_version": jdk_version,
                    "gc_type": data["gc_type"],
                    "gc_overhead_percentage": data["gc_overhead_percentage"],
                    "median_overhead_percentage": median_ratio * 100,
                    "ratio_multiplier": data["gc_overhead_ratio"] / median_ratio,
                    "description": f"{data['gc_type']} GC开销比例 ({data['gc_overhead_percentage']:.2f}%) "
                                  f"是中位数 ({median_ratio * 100:.2f}%) 的 "
                                  f"{data['gc_overhead_ratio'] / median_ratio:.1f} 倍",
                    "details": {
                        "gc_stw_time_ms": data["gc_stw_time_ms"],
                        "duration_ms": data["duration_ms"],
                        "total_gc_count": data["total_gc_count"]
                    }
                })

    if jdk_comparison_anomalies:
        anomalies.extend(jdk_comparison_anomalies)

    # 2. 同一GC类型跨JDK版本开销比例对比异常
    gc_type_groups = {}
    for data in gc_data:
        gc_type = data["gc_type"]
        if gc_type not in gc_type_groups:
            gc_type_groups[gc_type] = []
        gc_type_groups[gc_type].append(data)

    cross_version_anomalies = []
    for gc_type, gc_type_data in gc_type_groups.items():
        # 按JDK版本排序
        sorted_data = sorted(gc_type_data, key=lambda x: float(x["jdk_version"]) if x["jdk_version"].replace('.', '').isdigit() else 0)
        
        # 检查相邻版本之间的开销比例变化
        for i in range(1, len(sorted_data)):
            prev_version = sorted_data[i-1]
            curr_version = sorted_data[i]
            
            prev_jdk = prev_version["jdk_version"]
            curr_jdk = curr_version["jdk_version"]
            prev_overhead = prev_version["gc_overhead_ratio"]
            curr_overhead = curr_version["gc_overhead_ratio"]
            
            # 如果新版本的开销比例比旧版本显著增加（增加超过500%且绝对值增加超过5%）
            overhead_increase = curr_overhead - prev_overhead
            overhead_increase_ratio = overhead_increase / prev_overhead if prev_overhead > 0 else float('inf')
            
            if overhead_increase > 0.05 and overhead_increase_ratio > 5:  # 绝对增加5%且相对增加500%
                cross_version_anomalies.append({
                    "anomaly_type": "cross_version_overhead_regression",
                    "gc_type": gc_type,
                    "prev_jdk_version": prev_jdk,
                    "curr_jdk_version": curr_jdk,
                    "prev_overhead_percentage": prev_overhead * 100,
                    "curr_overhead_percentage": curr_overhead * 100,
                    "increase_percentage": overhead_increase * 100,
                    "increase_ratio": overhead_increase_ratio,
                    "description": f"{gc_type} GC开销比例从 {prev_jdk} ({prev_overhead * 100:.2f}%) "
                                  f"到 {curr_jdk} ({curr_overhead * 100:.2f}%) "
                                  f"增加了 {overhead_increase * 100:.2f}% ({overhead_increase_ratio:.1%})",
                    "prev_details": {
                        "gc_stw_time_ms": prev_version["gc_stw_time_ms"],
                        "duration_ms": prev_version["duration_ms"],
                        "total_gc_count": prev_version["total_gc_count"]
                    },
                    "curr_details": {
                        "gc_stw_time_ms": curr_version["gc_stw_time_ms"],
                        "duration_ms": curr_version["duration_ms"],
                        "total_gc_count": curr_version["total_gc_count"]
                    }
                })

    if cross_version_anomalies:
        anomalies.extend(cross_version_anomalies)

    # 如果发现任何异常，返回结果
    if anomalies:
        # 按异常类型分组统计
        jdk_comparison_count = len([a for a in anomalies if a.get("anomaly_type") == "jdk_internal_overhead_comparison"])
        cross_version_count = len([a for a in anomalies if a.get("anomaly_type") == "cross_version_overhead_regression"])
        debug_over_100_count = len([a for a in anomalies if a.get("anomaly_type") == "debug_gc_overhead_over_100_percent"])
        
        return {
            "type": "gc_overhead_anomaly",
            "file_path": file_path,
            "message": f"检测到{len(anomalies)}个GC开销比例异常（DEBUG超100%:{debug_over_100_count}, 同版本对比:{jdk_comparison_count}, 跨版本对比:{cross_version_count}）",
            "anomalies": anomalies,
            "summary": {
                "total_anomalies": len(anomalies),
                "debug_over_100_percent": debug_over_100_count,
                "jdk_internal_comparisons": jdk_comparison_count,
                "cross_version_regressions": cross_version_count,
                "total_gc_data_points": len(gc_data)
            }
        }

    return None