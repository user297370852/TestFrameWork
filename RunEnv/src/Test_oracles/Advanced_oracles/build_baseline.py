#!/usr/bin/env python3
"""
基于真实测试数据构建 GC 排名基准模型 (V2.1 Schema)

该脚本会：
1. 扫描所有测试结果文件
2. 按 (metric, jdk_version, gc_type) 分组
3. 计算排名分布和regret分布
4. 输出完整的baseline JSON文件
"""
import json
import os
import sys
import math
import statistics
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple


# ============================================================
# 配置
# ============================================================
# 指标参数（来自设计文档第6节）
METRIC_PARAMS = {
    'duration_ms': {'alpha': 1.0, 'tau': 0.05, 'lambda': 1.20, 'filter_zero': False},
    'gc_stw_time_ms': {'alpha': 0.1, 'tau': 0.10, 'lambda': 1.50, 'filter_zero': True},
    'max_stw_time_ms': {'alpha': 0.01, 'tau': 0.10, 'lambda': 1.50, 'filter_zero': True},
    'total_gc_count': {'alpha': 1.0, 'tau': 0.08, 'lambda': 1.30, 'filter_zero': True}
}

METRICS = ['duration_ms', 'gc_stw_time_ms', 'max_stw_time_ms', 'total_gc_count']

# JDK与GC支持的映射
JDK_GC_SUPPORT = {
    "11": ["EpsilonGC", "G1GC", "ParallelGC", "ParallelOldGC", "SerialGC", "ShenandoahGC"],
    "17": ["EpsilonGC", "G1GC", "ParallelGC", "SerialGC", "ShenandoahGC", "ZGC"],
    "21": ["EpsilonGC", "G1GC", "ParallelGC", "SerialGC", "ShenandoahGC", "ZGC"],
    "25": ["EpsilonGC", "G1GC", "ParallelGC", "SerialGC", "ShenandoahGC-Gen", "ZGC"],
    "26": ["EpsilonGC", "G1GC", "ParallelGC", "SerialGC", "ZGC"]
}


# ============================================================
# 工具函数
# ============================================================
def classify_gc_type(result: Dict[str, Any]) -> str:
    """根据GC参数识别GC类型"""
    gc_params = result.get("GC_parameters", [])
    params_str = " ".join(gc_params).upper()
    
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
    """从测试结果中提取指标值"""
    if metric_type == "duration_ms":
        return result.get("duration_ms")
    
    gc_analysis = result.get("gc_analysis")
    if gc_analysis is None:
        return None
    
    if metric_type == "gc_stw_time_ms":
        return gc_analysis.get("gc_stw_time_ms")
    elif metric_type == "max_stw_time_ms":
        return gc_analysis.get("max_stw_time_ms")
    elif metric_type == "total_gc_count":
        return gc_analysis.get("total_gc_count")
    
    return None


def calculate_regret(value: float, best_value: float, alpha: float) -> float:
    """计算regret"""
    if value is None or best_value is None:
        return 0.0
    value = max(0, value)
    best_value = max(0, best_value)
    numerator = value + alpha
    denominator = best_value + alpha
    if denominator <= 0:
        return 0.0
    regret = math.log(numerator / denominator)
    return max(0.0, regret)


def calculate_mad(values: List[float]) -> float:
    """计算MAD (Median Absolute Deviation)"""
    if not values:
        return 0.0
    median_val = statistics.median(values)
    deviations = [abs(v - median_val) for v in values]
    return statistics.median(deviations)


def calculate_quantile(values: List[float], q: float) -> float:
    """计算分位数 (q in [0, 1])"""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * q)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


# ============================================================
# 数据收集
# ============================================================
def collect_test_data(data_dir: str) -> Tuple[Dict, Dict]:
    """
    收集所有测试数据
    
    Returns:
        testcase_data: {testcase_id: {jdk_version: {gc_type: {metric: value}}}}
        raw_data: {(metric, jdk_version, gc_type): [values]}
    """
    testcase_data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    raw_data = defaultdict(list)
    
    # 遍历所有JSON文件
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith('.json'):
                json_files.append(os.path.join(root, f))
    
    print(f"找到 {len(json_files)} 个测试文件...")
    
    processed = 0
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            test_results = data.get('test_results', [])
            if not test_results:
                continue
            
            # 使用文件路径作为testcase_id
            class_info = data.get('class_file_info', {})
            testcase_id = class_info.get('file_path', json_file)
            
            for result in test_results:
                # 只处理成功的测试
                if not result.get('success', True):
                    continue
                if result.get('exit_code', 0) != 0:
                    continue
                
                jdk_version = result.get('jdk_version')
                gc_type = classify_gc_type(result)
                
                if not jdk_version or gc_type == "Unknown":
                    continue
                
                for metric in METRICS:
                    value = get_metric_value(result, metric)
                    if value is not None:
                        testcase_data[testcase_id][jdk_version][gc_type][metric] = value
                        raw_data[(metric, jdk_version, gc_type)].append(value)
            
            processed += 1
            if processed % 1000 == 0:
                print(f"已处理 {processed} 个文件...")
                
        except Exception as e:
            print(f"处理文件 {json_file} 时出错: {e}")
            continue
    
    print(f"完成处理 {processed} 个文件")
    return testcase_data, raw_data


# ============================================================
# 排名和regret计算
# ============================================================
def calculate_rankings_and_regrets(testcase_data: Dict) -> Dict:
    """
    计算每个testcase的排名和regret
    
    Returns:
        rank_data: {(metric, jdk_version, gc_type): [ranks]}
        regret_data: {(metric, jdk_version, gc_type): [regrets]}
    """
    rank_data = defaultdict(list)
    regret_data = defaultdict(list)
    
    for testcase_id, jdk_data in testcase_data.items():
        for jdk_version, gc_data in jdk_data.items():
            for metric in METRICS:
                # 收集该testcase下各GC的指标值
                values_by_gc = {}
                for gc_type, metrics in gc_data.items():
                    if metric in metrics:
                        values_by_gc[gc_type] = metrics[metric]
                
                if len(values_by_gc) < 2:
                    continue
                
                # 找出最优值
                best_value = min(values_by_gc.values())
                
                # 计算排名（升序，值越小排名越靠前）
                sorted_gcs = sorted(values_by_gc.items(), key=lambda x: x[1])
                rank_map = {}
                for rank, (gc, val) in enumerate(sorted_gcs, 1):
                    rank_map[gc] = rank
                
                # 计算每个GC的regret和排名
                alpha = METRIC_PARAMS[metric]['alpha']
                for gc_type, value in values_by_gc.items():
                    rank = rank_map[gc_type]
                    regret = calculate_regret(value, best_value, alpha)
                    
                    rank_data[(metric, jdk_version, gc_type)].append(rank)
                    regret_data[(metric, jdk_version, gc_type)].append(regret)
    
    return rank_data, regret_data


# ============================================================
# 构建baseline
# ============================================================
def build_baseline(rank_data: Dict, regret_data: Dict, raw_data: Dict) -> Dict:
    """构建完整的baseline JSON结构"""
    
    baseline = {
        "version": "2.1",
        "schema_version": "v2",
        "generated_date": "2026-01-22",
        "description": "GC排名基准模型 (V2.1)，基于真实测试数据统计生成",
        "metrics": {},
        "gc_support_by_jdk": JDK_GC_SUPPORT,
        "baselines": {}
    }
    
    # 添加指标信息
    for metric in METRICS:
        params = METRIC_PARAMS[metric]
        baseline["metrics"][metric] = {
            "name": metric.replace('_', ' ').title(),
            "description": f"{metric} 指标",
            "unit": "ms" if "ms" in metric else "次" if "count" in metric else "",
            "filter_zero": params['filter_zero'],
            "alpha": params['alpha'],
            "tau": params['tau'],
            "lambda": params['lambda']
        }
    
    # 初始化baselines结构
    for metric in METRICS:
        baseline["baselines"][metric] = {"by_jdk": {}, "overall": {}}
    
    # 按JDK版本处理
    for jdk_version in JDK_GC_SUPPORT.keys():
        for metric in METRICS:
            baseline["baselines"][metric]["by_jdk"][jdk_version] = {}
    
    # 填充数据
    all_gc_types = set()
    for (metric, jdk_version, gc_type) in rank_data.keys():
        all_gc_types.add(gc_type)
    
    # 处理每个 (metric, jdk, gc) 组合
    for metric in METRICS:
        for jdk_version in JDK_GC_SUPPORT.keys():
            for gc_type in JDK_GC_SUPPORT[jdk_version]:
                key = (metric, jdk_version, gc_type)
                
                ranks = rank_data.get(key, [])
                regrets = regret_data.get(key, [])
                
                if not ranks:
                    continue
                
                entry = {}
                
                # V1字段：排名均值和标准差
                mu = statistics.mean(ranks)
                sigma = statistics.stdev(ranks) if len(ranks) > 1 else 0.0
                entry["mu"] = round(mu, 4)
                entry["sigma"] = round(sigma, 4)
                entry["n"] = len(ranks)
                
                # V2字段：排名直方图
                rank_hist = defaultdict(int)
                for r in ranks:
                    rank_hist[int(r)] += 1
                entry["rank_hist"] = {str(k): v for k, v in sorted(rank_hist.items())}
                
                # V2字段：regret分布
                if regrets:
                    entry["regret_median"] = round(statistics.median(regrets), 4)
                    entry["regret_mad"] = round(calculate_mad(regrets), 4)
                    entry["regret_q90"] = round(calculate_quantile(regrets, 0.90), 4)
                    entry["regret_q95"] = round(calculate_quantile(regrets, 0.95), 4)
                    entry["regret_q99"] = round(calculate_quantile(regrets, 0.99), 4)
                else:
                    entry["regret_median"] = 0.0
                    entry["regret_mad"] = 0.0
                    entry["regret_q90"] = 0.0
                    entry["regret_q95"] = 0.0
                    entry["regret_q99"] = 0.0
                
                baseline["baselines"][metric]["by_jdk"][jdk_version][gc_type] = entry
    
    # 计算overall（跨JDK版本聚合）
    for metric in METRICS:
        all_gc_types_overall = set()
        for jdk_version in JDK_GC_SUPPORT.keys():
            for gc_type in JDK_GC_SUPPORT[jdk_version]:
                all_gc_types_overall.add(gc_type)
        
        for gc_type in all_gc_types_overall:
            # 聚合所有JDK版本的数据
            all_ranks = []
            all_regrets = []
            
            for jdk_version in JDK_GC_SUPPORT.keys():
                key = (metric, jdk_version, gc_type)
                all_ranks.extend(rank_data.get(key, []))
                all_regrets.extend(regret_data.get(key, []))
            
            if not all_ranks:
                continue
            
            entry = {}
            mu = statistics.mean(all_ranks)
            sigma = statistics.stdev(all_ranks) if len(all_ranks) > 1 else 0.0
            entry["mu"] = round(mu, 4)
            entry["sigma"] = round(sigma, 4)
            
            # V2字段
            rank_hist = defaultdict(int)
            for r in all_ranks:
                rank_hist[int(r)] += 1
            entry["rank_hist"] = {str(k): v for k, v in sorted(rank_hist.items())}
            
            if all_regrets:
                entry["regret_median"] = round(statistics.median(all_regrets), 4)
                entry["regret_mad"] = round(calculate_mad(all_regrets), 4)
                entry["regret_q90"] = round(calculate_quantile(all_regrets, 0.90), 4)
                entry["regret_q95"] = round(calculate_quantile(all_regrets, 0.95), 4)
                entry["regret_q99"] = round(calculate_quantile(all_regrets, 0.99), 4)
            else:
                entry["regret_median"] = 0.0
                entry["regret_mad"] = 0.0
                entry["regret_q90"] = 0.0
                entry["regret_q95"] = 0.0
                entry["regret_q99"] = 0.0
            
            baseline["baselines"][metric]["overall"][gc_type] = entry
    
    # 统计样本数
    total_samples = sum(len(v) for v in rank_data.values())
    baseline["sample_count"] = total_samples
    
    return baseline


# ============================================================
# 主函数
# ============================================================
def main():
    if len(sys.argv) < 2:
        data_dir = "/Users/yeliu/PycharmProjects/PythonProject/results/20260112"
    else:
        data_dir = sys.argv[1]
    
    output_file = "/Users/yeliu/PycharmProjects/PythonProject/RunEnv/src/Test_oracles/Advanced_oracles/gc_ranking_baseline.json"
    
    print("=" * 60)
    print("GC排名基准模型构建工具 (V2.1)")
    print("=" * 60)
    print(f"数据目录: {data_dir}")
    print(f"输出文件: {output_file}")
    print()
    
    # 1. 收集测试数据
    print("步骤 1: 收集测试数据...")
    testcase_data, raw_data = collect_test_data(data_dir)
    
    # 2. 计算排名和regret
    print("\n步骤 2: 计算排名和regret...")
    rank_data, regret_data = calculate_rankings_and_regrets(testcase_data)
    
    # 3. 构建baseline
    print("\n步骤 3: 构建baseline...")
    baseline = build_baseline(rank_data, regret_data, raw_data)
    
    # 4. 保存结果
    print(f"\n步骤 4: 保存结果到 {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2)
    
    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)
    print(f"总样本数: {baseline['sample_count']}")
    print(f"JDK版本: {list(JDK_GC_SUPPORT.keys())}")
    
    # 打印一些统计信息
    print("\n各指标的baseline条目数:")
    for metric in METRICS:
        by_jdk_count = sum(len(baseline["baselines"][metric]["by_jdk"][jdk]) 
                          for jdk in JDK_GC_SUPPORT.keys())
        overall_count = len(baseline["baselines"][metric]["overall"])
        print(f"  {metric}: by_jdk={by_jdk_count}, overall={overall_count}")
    
    # 示例输出
    print("\n示例 (JDK 17, G1GC, gc_stw_time_ms):")
    example = baseline["baselines"]["gc_stw_time_ms"]["by_jdk"]["17"].get("G1GC")
    if example:
        print(f"  mu: {example['mu']}, sigma: {example['sigma']}")
        print(f"  regret_median: {example['regret_median']}, regret_q99: {example['regret_q99']}")
        print(f"  n: {example['n']}")


if __name__ == '__main__':
    main()
