#!/usr/bin/env python3
"""
GC差分测试分析脚本
====================
分析不同GC类型在不同JDK版本下各指标的排名

支持的指标：
- duration_ms: 执行时间（毫秒）
- gc_stw_time_ms: GC暂停时间（毫秒）
- max_stw_time_ms: 最大单次暂停时间（毫秒）
- total_gc_count: GC总次数

功能：
1. 遍历所有测试结果JSON文件
2. 按JDK版本分组，计算每个测试用例中各GC在指定指标上的排名
3. 统计各GC的平均排名、测试次数、标准差

输出：
- results/gc_ranking_analysis_{metric}.json: 详细分析结果
"""

import json
import os
from collections import defaultdict
from pathlib import Path
import statistics
from typing import Dict, List, Any, Callable, Optional
from enum import Enum


class MetricType(Enum):
    """支持的指标类型"""
    DURATION = "duration_ms"           # 执行时间
    GC_STW_TIME = "gc_stw_time_ms"     # GC暂停时间
    MAX_STW_TIME = "max_stw_time_ms"   # 最大单次暂停时间
    TOTAL_GC_COUNT = "total_gc_count"  # GC总次数


# 指标配置：指标名称、描述、单位、是否需要过滤零值
METRIC_CONFIG = {
    MetricType.DURATION: {
        "name": "执行时间",
        "description": "程序总执行时间",
        "unit": "ms",
        "output_suffix": "duration",
        "filter_zero": False  # 执行时间不过滤零值
    },
    MetricType.GC_STW_TIME: {
        "name": "GC暂停时间",
        "description": "GC总暂停时间(STW)",
        "unit": "ms",
        "output_suffix": "gc_stw_time",
        "filter_zero": True  # GC暂停时间需要过滤零值（无GC活动的测试）
    },
    MetricType.MAX_STW_TIME: {
        "name": "最大单次暂停时间",
        "description": "最大单次GC暂停时间",
        "unit": "ms",
        "output_suffix": "max_stw_time",
        "filter_zero": True  # 最大暂停时间需要过滤零值
    },
    MetricType.TOTAL_GC_COUNT: {
        "name": "GC次数",
        "description": "GC总次数",
        "unit": "次",
        "output_suffix": "gc_count",
        "filter_zero": True  # GC次数需要过滤零值
    }
}


def extract_gc_type(gc_parameters: List[str]) -> str:
    """从GC参数中提取GC类型名称"""
    gc_type = None
    for param in gc_parameters:
        if param.startswith("-XX:+Use") and "GC" in param:
            # 提取GC名称，如 -XX:+UseSerialGC -> SerialGC
            gc_type = param.replace("-XX:+Use", "").replace("-XX:+UnlockExperimentalVMOptions", "")
        elif "ShenandoahGCMode=generational" in param:
            gc_type = "ShenandoahGC-Gen"
    return gc_type if gc_type else "Unknown"


def get_metric_value(test: Dict[str, Any], metric: MetricType) -> Optional[float]:
    """
    从测试结果中提取指标值
    
    Args:
        test: 单个测试结果字典
        metric: 指标类型
    
    Returns:
        指标值，如果无法获取则返回None
    """
    if metric == MetricType.DURATION:
        return test.get('duration_ms', None)
    elif metric in [MetricType.GC_STW_TIME, MetricType.MAX_STW_TIME, MetricType.TOTAL_GC_COUNT]:
        gc_analysis = test.get('gc_analysis', {})
        if not gc_analysis:
            return None
        return gc_analysis.get(metric.value, None)
    return None


def analyze_test_results(results_dir: str, metric: MetricType) -> tuple:
    """
    分析所有测试结果
    
    Args:
        results_dir: 测试结果目录
        metric: 要分析的指标类型
    
    Returns:
        (rankings, gc_support, total_files, processed_files)
    """
    results_path = Path(results_dir)
    config = METRIC_CONFIG[metric]
    filter_zero = config.get('filter_zero', False)
    
    # 数据结构：
    # rankings[jdk_version][gc_type] = [rank1, rank2, ...]
    rankings = defaultdict(lambda: defaultdict(list))
    gc_support = defaultdict(set)  # jdk_version -> set of supported GCs
    
    # 统计文件数量
    total_files = 0
    processed_files = 0
    skipped_no_metric = 0
    skipped_all_zero = 0  # 跳过的全零测试用例数
    
    # 遍历所有JSON文件
    for json_file in results_path.rglob("*.json"):
        total_files += 1
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'test_results' not in data:
                continue
            
            # 按JDK版本分组
            jdk_groups = defaultdict(list)
            
            for test in data['test_results']:
                if not test.get('success', False):
                    continue
                
                jdk_version = test.get('jdk_version', 'unknown')
                gc_type = extract_gc_type(test.get('GC_parameters', []))
                
                if gc_type == "Unknown":
                    continue
                
                # 获取指标值
                metric_value = get_metric_value(test, metric)
                if metric_value is None:
                    skipped_no_metric += 1
                    continue
                
                jdk_groups[jdk_version].append({
                    'gc_type': gc_type,
                    'value': metric_value,
                    'file': str(json_file)
                })
                gc_support[jdk_version].add(gc_type)
            
            # 对每个JDK版本内的测试计算排名
            for jdk_version, tests in jdk_groups.items():
                if len(tests) < 2:
                    # 少于2个GC无法排名
                    continue
                
                # 如果需要过滤零值，检查是否所有值都为0
                if filter_zero:
                    all_zero = all(t['value'] == 0 for t in tests)
                    if all_zero:
                        skipped_all_zero += 1
                        continue
                
                # 按指标值排序（值越小排名越靠前）
                sorted_tests = sorted(tests, key=lambda x: x['value'])
                
                # 计算排名（相同值给予相同排名）
                for i, test in enumerate(sorted_tests):
                    # 检查是否有相同的值
                    rank = i + 1
                    for j in range(i):
                        if sorted_tests[j]['value'] == test['value']:
                            rank = j + 1
                            break
                    
                    rankings[jdk_version][test['gc_type']].append(rank)
            
            processed_files += 1
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    print(f"\n统计摘要:")
    print(f"  总文件数: {total_files}")
    print(f"  成功处理: {processed_files}")
    if skipped_no_metric > 0:
        print(f"  缺失指标数据: {skipped_no_metric}")
    if skipped_all_zero > 0:
        print(f"  跳过无GC活动用例: {skipped_all_zero}")
    
    return rankings, gc_support, total_files, processed_files


def calculate_average_rankings(rankings: Dict) -> Dict:
    """计算平均排名"""
    avg_rankings = {}
    
    for jdk_version, gc_ranks in rankings.items():
        avg_rankings[jdk_version] = {}
        for gc_type, ranks in gc_ranks.items():
            if ranks:
                avg_rankings[jdk_version][gc_type] = {
                    'avg_rank': statistics.mean(ranks),
                    'count': len(ranks),
                    'std_dev': statistics.stdev(ranks) if len(ranks) > 1 else 0
                }
    
    return avg_rankings


def calculate_overall_rankings(rankings: Dict) -> Dict:
    """计算所有JDK版本的总排名"""
    overall_rankings = defaultdict(list)
    
    for jdk_version, gc_ranks in rankings.items():
        for gc_type, ranks in gc_ranks.items():
            overall_rankings[gc_type].extend(ranks)
    
    result = {}
    for gc_type, ranks in overall_rankings.items():
        if ranks:
            result[gc_type] = {
                'avg_rank': statistics.mean(ranks),
                'count': len(ranks),
                'std_dev': statistics.stdev(ranks) if len(ranks) > 1 else 0
            }
    
    return result


def print_results(avg_rankings: Dict, overall_rankings: Dict, gc_support: Dict, metric: MetricType):
    """打印结果"""
    config = METRIC_CONFIG[metric]
    
    print("\n" + "="*100)
    print(f"分析指标: {config['name']} ({config['description']})")
    print("="*100)
    
    print("\n" + "-"*100)
    print("各JDK版本支持的GC类型:")
    print("-"*100)
    for jdk in sorted(gc_support.keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
        gc_list = sorted(gc_support[jdk])
        print(f"  JDK {jdk:>2}: {', '.join(gc_list)}")
    
    print("\n" + "-"*100)
    print(f"总体GC平均排名（所有JDK版本综合）:")
    print("-"*100)
    sorted_overall = sorted(overall_rankings.items(), key=lambda x: x[1]['avg_rank'])
    print(f"{'排名':<6} {'GC类型':<20} {'平均排名':<12} {'测试次数':<12} {'标准差':<12}")
    print("-"*80)
    for i, (gc_type, stats) in enumerate(sorted_overall, 1):
        print(f"{i:<6} {gc_type:<20} {stats['avg_rank']:<12.4f} {stats['count']:<12} {stats['std_dev']:<12.4f}")
    
    print("\n" + "-"*100)
    print("各JDK版本GC平均排名:")
    print("-"*100)
    
    for jdk in sorted(avg_rankings.keys(), key=lambda x: int(x) if x.isdigit() else float('inf')):
        print(f"\n{'='*60}")
        print(f"JDK {jdk}:")
        print(f"{'='*60}")
        sorted_gc = sorted(avg_rankings[jdk].items(), key=lambda x: x[1]['avg_rank'])
        print(f"{'排名':<6} {'GC类型':<20} {'平均排名':<12} {'测试次数':<12} {'标准差':<12}")
        print("-"*60)
        for i, (gc_type, stats) in enumerate(sorted_gc, 1):
            print(f"{i:<6} {gc_type:<20} {stats['avg_rank']:<12.4f} {stats['count']:<12} {stats['std_dev']:<12.4f}")


def save_results_to_json(avg_rankings: Dict, overall_rankings: Dict, gc_support: Dict, 
                         metric: MetricType, output_file: Path):
    """保存结果到JSON文件"""
    config = METRIC_CONFIG[metric]
    
    result = {
        'metric_info': {
            'type': metric.value,
            'name': config['name'],
            'description': config['description'],
            'unit': config['unit']
        },
        'gc_support_by_jdk': {k: sorted(list(v)) for k, v in gc_support.items()},
        'overall_rankings': overall_rankings,
        'rankings_by_jdk': avg_rankings
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")


def analyze_metric(results_dir: str, metric: MetricType, output_dir: Path):
    """
    分析单个指标
    
    Args:
        results_dir: 测试结果目录
        metric: 指标类型
        output_dir: 输出目录
    """
    config = METRIC_CONFIG[metric]
    output_suffix = config['output_suffix']
    output_file = output_dir / f"gc_ranking_analysis_{output_suffix}.json"
    
    print(f"\n{'#'*100}")
    print(f"# 开始分析指标: {config['name']} ({metric.value})")
    print(f"{'#'*100}")
    
    # 分析测试结果
    rankings, gc_support, total_files, processed_files = analyze_test_results(results_dir, metric)
    
    # 计算平均排名
    avg_rankings = calculate_average_rankings(rankings)
    overall_rankings = calculate_overall_rankings(rankings)
    
    # 打印结果
    print_results(avg_rankings, overall_rankings, gc_support, metric)
    
    # 保存结果
    save_results_to_json(avg_rankings, overall_rankings, gc_support, metric, output_file)
    
    return avg_rankings, overall_rankings, gc_support


def analyze_all_metrics(results_dir: str, output_dir: Path):
    """分析所有指标"""
    all_results = {}
    
    for metric in MetricType:
        try:
            avg_rankings, overall_rankings, gc_support = analyze_metric(results_dir, metric, output_dir)
            all_results[metric] = {
                'avg_rankings': avg_rankings,
                'overall_rankings': overall_rankings,
                'gc_support': gc_support
            }
        except Exception as e:
            print(f"\n分析指标 {metric.value} 时出错: {e}")
            continue
    
    return all_results


def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    
    # 配置路径
    results_dir = "/Users/yeliu/PycharmProjects/PythonProject/results/20260101"
    output_dir = script_dir / "results"
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"分析目录: {results_dir}")
    print(f"输出目录: {output_dir}")
    
    # 分析所有指标
    analyze_all_metrics(results_dir, output_dir)
    
    print("\n" + "#"*100)
    print("# 所有指标分析完成！")
    print("#"*100)


if __name__ == "__main__":
    main()
