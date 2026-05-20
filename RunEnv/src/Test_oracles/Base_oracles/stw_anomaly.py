#!/usr/bin/env python3
"""
测试预言: 检测STW时间异常（差分测试版本）
规则: 
1. 绝对阈值监测：不同GC类型有不同的STW时间阈值
2. 同版本JDK内GC对比：G1GC不应比SerialGC更长，ZGC/ShenandoahGC应比其他GC更低
3. 同GC类型跨JDK版本对比：版本提升不应导致STW显著增加
"""
from typing import Dict, Any, Optional


def oracle_stw_anomaly(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言: 检测STW时间异常（差分测试版本）
    规则: 结合绝对阈值、同版本JDK内GC对比、同GC类型跨版本对比
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # 不同GC类型的STW时间阈值（毫秒）
    STW_THRESHOLDS = {
        "ZGC": 5,           # ZGC应该是极低延迟
        "ShenandoahGC": 1000,  # ShenandoahGC也是低延迟GC
        "G1GC": 2000,         # G1GC中等延迟
        "ParallelGC": 3000,   # ParallelGC可能会有较长暂停
        "SerialGC": 5000,    # SerialGC是单线程，暂停可能较长
        "Unknown": 3000       # 未知GC类型使用默认阈值
    }

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

    # 收集所有有效的GC结果数据
    gc_data = []
    for result in test_results:
        gc_analysis = result.get("gc_analysis")
        if not gc_analysis:
            continue
            
        gc_count = gc_analysis.get("total_gc_count")
        if gc_count is None or gc_count < 10:
            continue
            
        max_stw_time = gc_analysis.get("max_stw_time_ms")
        if max_stw_time is None:
            continue
            
        gc_type = classify_gc_type(result)
        jdk_version = result.get("jdk_version", "unknown")
        
        gc_data.append({
            "jdk_version": jdk_version,
            "gc_type": gc_type,
            "max_stw_time_ms": max_stw_time
        })

    if not gc_data:
        return None

    anomalies = []

    # 1. 绝对阈值监测
    threshold_anomalies = []
    for data in gc_data:
        gc_type = data["gc_type"]
        threshold = STW_THRESHOLDS.get(gc_type, STW_THRESHOLDS["Unknown"])
        
        if data["max_stw_time_ms"] > threshold:
            excess_ratio = (data["max_stw_time_ms"] - threshold) / threshold
            threshold_anomalies.append({
                "score": round(excess_ratio, 4),  # 异常分数：超出阈值的比例
                "info": f"{data['jdk_version']}-{gc_type}: STW时间异常，STW时间（{data['max_stw_time_ms']:.3f}ms）超过阈值（{threshold:.3f}ms）{data['max_stw_time_ms'] / threshold:.1f}倍"
            })

    if threshold_anomalies:
        anomalies.extend(threshold_anomalies)

    # 2. 同版本JDK内GC类型对比异常
    jdk_groups = {}
    for data in gc_data:
        jdk_version = data["jdk_version"]
        if jdk_version not in jdk_groups:
            jdk_groups[jdk_version] = []
        jdk_groups[jdk_version].append(data)

    jdk_comparison_anomalies = []
    for jdk_version, jdk_gc_data in jdk_groups.items():
        # 创建GC类型到STW时间的映射
        gc_stw_map = {}
        for data in jdk_gc_data:
            gc_stw_map[data["gc_type"]] = data["max_stw_time_ms"]
        
        # 检查逻辑：G1GC不应比SerialGC更长
        if "G1GC" in gc_stw_map and "SerialGC" in gc_stw_map:
            if gc_stw_map["SerialGC"]>1 and gc_stw_map["G1GC"] > gc_stw_map["SerialGC"]*20:
                score = gc_stw_map["G1GC"] / gc_stw_map["SerialGC"]  # G1GC相对于SerialGC的倍数
                jdk_comparison_anomalies.append({
                    "info": f"{jdk_version}-G1GC: STW时间异常，STW时间（{gc_stw_map['G1GC']:.3f}ms）比同版本的SerialGC（{gc_stw_map['SerialGC']:.3f}ms）高{score:.1f}倍",
                    "score": round(score, 4)  # 异常分数：G1GC相对于SerialGC的倍数
                })
        
        # 检查逻辑：ZGC/ShenandoahGC应比所有其他GC更低
        low_latency_gcs = []
        other_gcs = []
        
        for data in jdk_gc_data:
            if data["gc_type"] in ["ZGC", "ShenandoahGC"]:
                low_latency_gcs.append(data)
            else:
                other_gcs.append(data)
        
        for low_latency_gc in low_latency_gcs:
            for other_gc in other_gcs:
                if low_latency_gc["gc_type"] == "ShenandoahGC":
                    if other_gc["max_stw_time_ms"]>0.1 and low_latency_gc["max_stw_time_ms"] > other_gc["max_stw_time_ms"]*20:
                        score = low_latency_gc["max_stw_time_ms"] / other_gc["max_stw_time_ms"]  # 低延迟GC相对于其他GC的倍数
                        jdk_comparison_anomalies.append({
                        "info": f"{jdk_version}-{low_latency_gc['gc_type']}: STW时间异常，STW时间（{low_latency_gc['max_stw_time_ms']:.3f}ms）比同版本的{other_gc['gc_type']}（{other_gc['max_stw_time_ms']:.3f}ms）高{score:.1f}倍",
                        "score": round(score, 4)  # 异常分数：低延迟GC相对于其他GC的倍数
                    })
                else:
                    if other_gc["max_stw_time_ms"]>0.1 and low_latency_gc["max_stw_time_ms"] > other_gc["max_stw_time_ms"]:
                        score = low_latency_gc["max_stw_time_ms"] / other_gc["max_stw_time_ms"]  # 低延迟GC相对于其他GC的倍数
                        jdk_comparison_anomalies.append({
                        "info": f"{jdk_version}-{low_latency_gc['gc_type']}: STW时间异常，STW时间（{low_latency_gc['max_stw_time_ms']:.3f}ms）比同版本的{other_gc['gc_type']}（{other_gc['max_stw_time_ms']:.3f}ms）高{score:.1f}倍",
                        "score": round(score, 4)  # 异常分数：低延迟GC相对于其他GC的倍数
                    })

    if jdk_comparison_anomalies:
        anomalies.extend(jdk_comparison_anomalies)

    # 3. 同GC类型跨JDK版本对比异常
    gc_type_groups = {}
    for data in gc_data:
        gc_type = data["gc_type"]
        if gc_type not in gc_type_groups:
            gc_type_groups[gc_type] = []
        gc_type_groups[gc_type].append(data)

    cross_version_anomalies = []
    for gc_type, gc_type_data in gc_type_groups.items():
        # 按JDK版本排序（假设版本号是数字，可以转换为整数比较）
        sorted_data = sorted(gc_type_data, key=lambda x: float(x["jdk_version"]) if x["jdk_version"].replace('.', '').isdigit() else 0)
        
        # 检查相邻版本之间的STW变化
        for i in range(1, len(sorted_data)):
            prev_version = sorted_data[i-1]
            curr_version = sorted_data[i]
            
            prev_jdk = prev_version["jdk_version"]
            curr_jdk = curr_version["jdk_version"]
            prev_stw = prev_version["max_stw_time_ms"]
            curr_stw = curr_version["max_stw_time_ms"]
            
            if prev_stw <0.001:
                continue
            
            # 如果新版本的STW比旧版本显著增加（比如增加超过50%或绝对值增加超过5ms）
            stw_increase = curr_stw - prev_stw
            stw_increase_ratio = stw_increase / prev_stw if prev_stw > 0 else float('inf')
            
            if gc_type == "ShenandoahGC":
                if stw_increase > 5 and stw_increase_ratio > 20:  # 绝对增加0.1ms且相对增加1000%
                    cross_version_anomalies.append({
                    "score": round(stw_increase_ratio, 4),  # 异常分数：STW增加的比例
                    "info": f"{curr_jdk}-{gc_type}: STW时间异常，STW时间（{curr_stw:.3f}ms）比JDK{prev_jdk}（{prev_stw:.3f}ms）高{curr_stw / prev_stw:.1f}倍"
                })
            elif gc_type == "ZGC":
                if stw_increase > 0.1 and stw_increase_ratio > 5:  # 绝对增加0.1ms且相对增加500%
                    cross_version_anomalies.append({
                    "score": round(stw_increase_ratio, 4),  # 异常分数：STW增加的比例
                    "info": f"{curr_jdk}-{gc_type}: STW时间异常，STW时间（{curr_stw:.3f}ms）比JDK{prev_jdk}（{prev_stw:.3f}ms）高{curr_stw / prev_stw:.1f}倍"
                })
            else:
                if stw_increase > 50 and stw_increase_ratio > 20:  # 绝对增加1ms且相对增加2000%
                    cross_version_anomalies.append({
                    "score": round(stw_increase_ratio, 4),  # 异常分数：STW增加的比例
                    "info": f"{curr_jdk}-{gc_type}: STW时间异常，STW时间（{curr_stw:.3f}ms）比JDK{prev_jdk}（{prev_stw:.3f}ms）高{curr_stw / prev_stw:.1f}倍"
                })

    if cross_version_anomalies:
        anomalies.extend(cross_version_anomalies)

    # 如果发现任何异常，返回结果
    if anomalies:
        return {
            "type": "stw_anomaly",
            "file_path": file_path,
            "anomalies": anomalies
        }

    return None
