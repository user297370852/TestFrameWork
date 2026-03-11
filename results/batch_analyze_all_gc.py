#!/usr/bin/env python3
"""
GC测试结果批量分析程序
为所有GC类型生成CSV汇总文件并自动创建统计图表
"""

import os
import sys
import subprocess
from pathlib import Path
import argparse

# 支持的GC类型
SUPPORTED_GC_TYPES = ['ZGC', 'G1GC', 'Parallel', 'Serial', 'Shenandoah', 'Epsilon']

def run_batch_process(results_dir, gc_type, output_dir, jdks):
    """运行单个GC类型的批量处理"""
    cmd = [
        sys.executable, 'batch_process_gc_results.py',
        results_dir,
        gc_type,
        '--output_dir', output_dir,
        '--jdks', jdks
    ]
    
    print(f"处理 {gc_type} 数据...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ {gc_type} 处理完成")
        return True
    else:
        print(f"✗ {gc_type} 处理失败:")
        print(result.stderr)
        return False

def run_chart_generation(output_dir, gc_type, run_start=1, run_end=10000):
    """运行图表生成"""
    # 构造chart生成脚本的正确路径
    current_dir = Path(__file__).parent
    generate_charts_path = current_dir / 'generate_charts.py'
    
    cmd = [
        sys.executable, str(generate_charts_path),
        str(run_start),
        str(run_end),
        gc_type
    ]
    
    print(f"生成 {gc_type} 图表...")
    
    # 不需要切换目录，直接使用正确路径
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ {gc_type} 图表生成完成")
            return True
        else:
            print(f"✗ {gc_type} 图表生成失败:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ {gc_type} 图表生成出错: {e}")
        return False

def check_csv_exists(output_dir, gc_type):
    """检查CSV文件是否存在"""
    csv_file = Path(output_dir) / f"{gc_type.lower()}_test_summary.csv"
    return csv_file.exists()

def main():
    parser = argparse.ArgumentParser(description='批量分析所有GC类型的测试结果')
    parser.add_argument('results_dir', type=str, help='结果文件夹路径（例如 results/20260101）')
    parser.add_argument('--output_dir', type=str, default='results/GCLogParser', 
                       help='输出目录 (默认: results/GCLogParser)')
    parser.add_argument('--jdks', type=str, default='17,21,25,26', 
                       help='要分析的JDK版本，用逗号分隔 (默认: 17,21,25,26)')
    parser.add_argument('--gc_types', type=str, default=','.join(SUPPORTED_GC_TYPES),
                       help=f'要分析的GC类型，用逗号分隔 (默认: {",".join(SUPPORTED_GC_TYPES)})')
    parser.add_argument('--skip_processed', action='store_true',
                       help='跳过已经处理过的GC类型')
    parser.add_argument('--run_start', type=int, default=1,
                       help='运行范围开始 (默认: 1)')
    parser.add_argument('--run_end', type=int, default=10000,
                       help='运行范围结束 (默认: 10000)')
    
    args = parser.parse_args()
    
    # 解析GC类型
    gc_types = args.gc_types.split(',')
    
    print(f"开始批量分析GC测试结果...")
    print(f"结果目录: {args.results_dir}")
    print(f"GC类型: {gc_types}")
    print(f"JDK版本: {args.jdks}")
    print(f"输出目录: {args.output_dir}")
    print(f"运行范围: {args.run_start}-{args.run_end}")
    print("=" * 80)
    
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    successful_count = 0
    
    # 检查目录是否存在
    results_path = Path(args.results_dir)
    if not results_path.exists():
        print(f"错误: 结果目录不存在: {args.results_dir}")
        return 1
    
    for gc_type in gc_types:
        print(f"\n处理 {gc_type}...")
        processed_count += 1
        
        # 检查是否已经处理过
        if args.skip_processed and check_csv_exists(args.output_dir, gc_type):
            print(f"✓ {gc_type} CSV文件已存在，跳过处理")
            successful_count += 1
            continue
        
        # 处理单个GC类型
        success = run_batch_process(args.results_dir, gc_type, args.output_dir, args.jdks)
        
        if success:
            successful_count += 1
            
            # 检查CSV文件是否生成成功
            if check_csv_exists(args.output_dir, gc_type):
                print(f"✓ {gc_type} CSV文件已生成")
                
                # 生成图表
                charts_success = run_chart_generation(args.output_dir, gc_type, args.run_start, args.run_end)
                if charts_success:
                    print(f"✓ {gc_type} 图表已生成")
            else:
                print(f"警告: {gc_type} CSV文件未生成")
        else:
            print(f"✗ {gc_type} 处理失败")
    
    print("\n" + "=" * 80)
    print(f"批量分析完成!")
    print(f"总计处理: {processed_count} 个GC类型")
    print(f"成功处理: {successful_count} 个GC类型")
    print(f"\n输出文件位置: {output_path}")
    print(f"\n可用操作:")
    print(f"1. 查看CSV文件: {output_path}/*.csv")
    print(f"2. 查看图表: {output_path}/charts/*/")
    print(f"3. 手动生成特定图表:")
    print(f"   python3 generate_charts.py <start> <end> [gc_type]")
    
    return 0

if __name__ == "__main__":
    exit(main())