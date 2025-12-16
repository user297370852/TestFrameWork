#!/usr/bin/env python3
"""
GC日志分析器使用示例
演示如何使用GCLogAnalyzer解析不同类型的GC日志
"""
import os
import sys
import json
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from GCLogAnalyzer import GCLogAnalyzer


def analyze_gc_logs():
    """分析所有GC日志文件"""
    analyzer = GCLogAnalyzer()
    gc_logs_dir = Path(__file__).parent.parent.parent / "gclogs"
    
    print("Java GC日志分析示例")
    print("="*60)
    
    if not gc_logs_dir.exists():
        print(f"GC日志目录不存在: {gc_logs_dir}")
        return
    
    # 选择几个代表性的日志文件进行演示
    demo_files = [
        "jdk21-SerialGC.log",
        "jdk17-ParallelGC.log",
        "jdk25-G1GC.log",
        "jdk21-ZGC.log",
        "jdk17-EpsilonGC.log",
        "jdk21-ShenandoahGC.log",
        "jdk25-ShenandoahGC-Gen.log"
    ]
    
    results = {}
    
    for filename in demo_files:
        gc_log_file = gc_logs_dir / filename
        
        if gc_log_file.exists():
            print(f"\n分析文件: {filename}")
            print("-" * 40)
            
            try:
                result = analyzer.parse_gc_log(str(gc_log_file))
                results[filename] = result
                
                # 打印摘要信息
                print(f"GC类型: {list(result['gc_type_breakdown'].keys())[0]}")
                print(f"总GC次数: {result['total_gc_count']}")
                print(f"总暂停时间: {result['gc_stw_time_ms']:.3f}ms")
                print(f"最大暂停时间: {result['max_stw_time_ms']:.3f}ms")
                print(f"最大堆大小: {result['max_heap_mb']}MB")
                
                # 打印详细的GC类型细分
                print("GC类型细分:")
                for gc_type, details in result['gc_type_breakdown'].items():
                    print(f"  - {gc_type}: {details['count']}次, {details['stw_time_ms']:.3f}ms")
                    
            except Exception as e:
                print(f"解析失败: {e}")
        else:
            print(f"文件不存在: {filename}")
    
    # 生成汇总报告
    print(f"\n{'='*60}")
    print("汇总报告")
    print(f"{'='*60}")
    
    total_gcs = sum(result['total_gc_count'] for result in results.values())
    total_pause_time = sum(result['gc_stw_time_ms'] for result in results.values())
    max_heap = max(result['max_heap_mb'] for result in results.values())
    
    print(f"分析文件数: {len(results)}")
    print(f"总GC次数: {total_gcs}")
    print(f"总暂停时间: {total_pause_time:.3f}ms")
    print(f"最大堆大小: {max_heap}MB")
    
    # 保存详细结果到JSON文件
    output_file = Path(__file__).parent / "gc_analysis_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细分析结果已保存到: {output_file}")


def show_gc_type_distribution():
    """展示不同GC类型的分布"""
    gc_logs_dir = Path(__file__).parent.parent.parent / "gclogs"
    
    print(f"\nGC日志文件分布")
    print("-" * 40)
    
    gc_type_counts = {}
    
    for gc_log_file in gc_logs_dir.glob("*.log"):
        filename = gc_log_file.name.lower()
        
        if 'serialgc' in filename:
            gc_type = 'SerialGC'
        elif 'parallelgc' in filename:
            gc_type = 'ParallelGC'
        elif 'g1gc' in filename:
            gc_type = 'G1GC'
        elif 'zgc' in filename:
            gc_type = 'ZGC'
        elif 'shenandoahgc' in filename:
            gc_type = 'ShenandoahGC'
        elif 'epsilongc' in filename:
            gc_type = 'EpsilonGC'
        else:
            gc_type = 'Unknown'
        
        gc_type_counts[gc_type] = gc_type_counts.get(gc_type, 0) + 1
    
    for gc_type, count in sorted(gc_type_counts.items()):
        print(f"{gc_type}: {count}个文件")


if __name__ == "__main__":
    show_gc_type_distribution()
    analyze_gc_logs()
