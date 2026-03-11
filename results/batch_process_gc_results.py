#!/usr/bin/env python3
"""
GC测试结果批量处理程序
扫描结果文件夹中所有JSON文件，提取指定GC类型的数据，生成CSV汇总文件
"""

import os
import json
import csv
from pathlib import Path
from datetime import datetime
import re
import argparse
from collections import defaultdict

def detect_gc_type_from_test_result(test_result):
    """从测试结果中检测GC类型"""
    gc_params = test_result.get('GC_parameters', [])
    gc_analysis = test_result.get('gc_analysis', {})
    
    # 从GC参数检测
    for param in gc_params:
        if '-XX:+UseZGC' in param:
            return 'ZGC'
        elif '-XX:+UseG1GC' in param:
            return 'G1GC'
        elif '-XX:+UseParallelGC' in param or '-XX:+UseParallelOldGC' in param:
            return 'Parallel'
        elif '-XX:+UseSerialGC' in param:
            return 'Serial'
        elif '-XX:+UseShenandoahGC' in param:
            return 'Shenandoah'
        elif '-XX:+UseEpsilonGC' in param:
            return 'Epsilon'
    
    # 从GC分析结果检测
    gc_breakdown = gc_analysis.get('gc_type_breakdown', {})
    if gc_breakdown:
        gc_type = list(gc_breakdown.keys())[0] if gc_breakdown else ''
        if 'ZGC' in gc_type:
            return 'ZGC'
        elif 'G1GC' in gc_type:
            return 'G1GC'
        elif 'Parallel' in gc_type:
            return 'Parallel'
        elif 'Serial' in gc_type:
            return 'Serial'
        elif 'Shenandoah' in gc_type:
            return 'Shenandoah'
        elif 'Epsilon' in gc_type:
            return 'Epsilon'
    
    return 'Unknown'

def extract_gc_data(json_file_path, target_gc_type, supported_jdks):
    """从JSON文件提取指定GC类型的测试数据"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"警告: 无法解析JSON文件 {json_file_path}: {e}")
        return None
    
    test_results = data.get('test_results', [])
    extracted_data = {
        'filename': os.path.basename(json_file_path),
        'total_tests': data.get('test_summary', {}).get('total_tests', 0),
        'successful_tests': data.get('test_summary', {}).get('successful_tests', 0),
        'success_rate': data.get('test_summary', {}).get('success_rate', 0.0)
    }
    
    # 为每个支持的JDK版本初始化数据
    raw_data = {}
    for jdk in supported_jdks:
        extracted_data[f'jdk{jdk}_GC_Count'] = ''
        extracted_data[f'jdk{jdk}_Pause_Time_ms'] = ''
        extracted_data[f'jdk{jdk}_Max_Pause_ms'] = ''
        raw_data[jdk] = {
            'GC_Count': None,
            'Pause_Time_ms': None,
            'Max_Pause_ms': None
        }
    
    # 提取匹配的GC类型和JDK版本的数据
    for test_result in test_results:
        jdk_version = test_result.get('jdk_version', '')
        success = test_result.get('success', False)
        
        # 只处理支持的JDK版本和成功的测试
        if jdk_version not in supported_jdks or not success:
            continue
            
        detected_gc_type = detect_gc_type_from_test_result(test_result)
        
        # 如果检测到的是目标GC类型
        if detected_gc_type.lower() == target_gc_type.lower():
            gc_analysis = test_result.get('gc_analysis', {})
            
            # 提取原始数据
            raw_data[jdk_version]['GC_Count'] = gc_analysis.get('total_gc_count', 0)
            raw_data[jdk_version]['Pause_Time_ms'] = gc_analysis.get('gc_stw_time_ms', 0.0)
            raw_data[jdk_version]['Max_Pause_ms'] = gc_analysis.get('max_stw_time_ms', 0.0)
        # 特殊处理Parallel GC（包含ParallelOldGC）
        elif target_gc_type.lower() == 'parallel' and 'Parallel' in detected_gc_type:
            gc_analysis = test_result.get('gc_analysis', {})
            
            # 提取原始数据
            raw_data[jdk_version]['GC_Count'] = gc_analysis.get('total_gc_count', 0)
            raw_data[jdk_version]['Pause_Time_ms'] = gc_analysis.get('gc_stw_time_ms', 0.0)
            raw_data[jdk_version]['Max_Pause_ms'] = gc_analysis.get('max_stw_time_ms', 0.0)
        # 特殊处理Serial GC
        elif target_gc_type.lower() == 'serial' and 'Serial' in detected_gc_type:
            gc_analysis = test_result.get('gc_analysis', {})
            
            # 提取原始数据
            raw_data[jdk_version]['GC_Count'] = gc_analysis.get('total_gc_count', 0)
            raw_data[jdk_version]['Pause_Time_ms'] = gc_analysis.get('gc_stw_time_ms', 0.0)
            raw_data[jdk_version]['Max_Pause_ms'] = gc_analysis.get('max_stw_time_ms', 0.0)
    
    # 检查JDK21的GC次数是否大于10（过滤条件）
    jdk21_gc_count = raw_data.get('21', {}).get('GC_Count')
    if jdk21_gc_count is None or jdk21_gc_count <= 10:
        # 不符合条件，返回None表示跳过此文件
        return None
    
    # 归一化处理：以JDK21为基准值100
    jdk21_pause_time = raw_data.get('21', {}).get('Pause_Time_ms')
    
    # 只有当JDK21有有效数据时才进行归一化
    jdk21_gc_count = raw_data.get('21', {}).get('GC_Count')
    jdk21_max_pause = raw_data.get('21', {}).get('Max_Pause_ms')
    
    if jdk21_pause_time and jdk21_pause_time > 0 and jdk21_gc_count and jdk21_gc_count > 0 and jdk21_max_pause and jdk21_max_pause > 0:
        # 为每个指标计算单独的归一化系数
        gc_count_coefficient = 100.0 / jdk21_gc_count
        pause_time_coefficient = 100.0 / jdk21_pause_time
        max_pause_coefficient = 100.0 / jdk21_max_pause
        
        # 应用归一化到所有JDK版本
        for jdk in supported_jdks:
            if raw_data[jdk]['Pause_Time_ms'] is not None:
                # 每个指标使用其自己的系数
                extracted_data[f'jdk{jdk}_GC_Count'] = raw_data[jdk]['GC_Count'] * gc_count_coefficient
                extracted_data[f'jdk{jdk}_Pause_Time_ms'] = raw_data[jdk]['Pause_Time_ms'] * pause_time_coefficient
                extracted_data[f'jdk{jdk}_Max_Pause_ms'] = raw_data[jdk]['Max_Pause_ms'] * max_pause_coefficient if raw_data[jdk]['Max_Pause_ms'] is not None else 0.0
    else:
        # 如果JDK21没有有效数据，则保留原始数据（或设置为空）
        for jdk in supported_jdks:
            if raw_data[jdk]['Pause_Time_ms'] is not None:
                extracted_data[f'jdk{jdk}_GC_Count'] = raw_data[jdk]['GC_Count']
                extracted_data[f'jdk{jdk}_Pause_Time_ms'] = raw_data[jdk]['Pause_Time_ms']
                extracted_data[f'jdk{jdk}_Max_Pause_ms'] = raw_data[jdk]['Max_Pause_ms']
    
    return extracted_data

def process_results_directory(results_dir, target_gc_type, output_dir=None, supported_jdks=None):
    """处理结果目录中的所有JSON文件"""
    if supported_jdks is None:
        supported_jdks = ['17', '21', '25', '26']
    
    # 默认输出到当前目录下的results目录
    if output_dir is None:
        output_path = Path('./results')
    else:
        output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 找到所有JSON文件
    results_path = Path(results_dir)
    json_files = []
    
    # 递归搜索所有JSON文件
    for json_file in results_path.rglob('*.json'):
        # 跳过报告文件等系统文件
        if 'report.json' not in json_file.name:
            json_files.append(json_file)
    
    print(f"在 {results_dir} 中找到 {len(json_files)} 个JSON文件")
    
    # 处理所有JSON文件
    all_data = []
    processed_count = 0
    valid_run_count = 1  # 用于Run_Number的唯一递增编号
    
    for json_file in json_files:
        extracted_data = extract_gc_data(json_file, target_gc_type, supported_jdks)
        if extracted_data is not None:
            # 添加Run_Number和Timestamp以匹配图表程序期望的格式
            extracted_data['Run_Number'] = valid_run_count
            extracted_data['Timestamp'] = datetime.now().isoformat()
            all_data.append(extracted_data)
            valid_run_count += 1
            processed_count += 1
            
            if processed_count % 1000 == 0:
                print(f"已处理 {processed_count} 个文件... (符合GC次数条件: {valid_run_count-1})")
    
    print(f"成功处理 {processed_count} 个文件 (其中 {len(all_data)} 个符合JDK21 GC次数>10的条件)")
    
    # 生成CSV文件名 (小写GC类型)
    csv_filename = f"{target_gc_type.lower()}_test_summary.csv"
    csv_file_path = output_path / csv_filename
    
    # 准备CSV列（按照图表程序期望的格式）
    csv_columns = ['Run_Number', 'Timestamp']
    for jdk in supported_jdks:
        csv_columns.extend([f'jdk{jdk}_GC_Count', f'jdk{jdk}_Pause_Time_ms', f'jdk{jdk}_Max_Pause_ms'])
    
    # 写入CSV文件
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader()
        
        for data_row in all_data:
            # 只写入需要的字段
            row_data = {k: v for k, v in data_row.items() if k in csv_columns}
            writer.writerow(row_data)
    
    print(f"✓ CSV汇总文件生成完成: {csv_file_path}")
    print(f"总计符合条件的数据行数: {len(all_data)} (JDK21 GC次数 > 10)")
    
    return csv_file_path

def main():
    parser = argparse.ArgumentParser(description='批量处理GC测试结果并生成CSV汇总文件')
    parser.add_argument('results_dir', type=str, help='结果文件夹路径（例如 results/20260101）')
    parser.add_argument('gc_type', type=str, choices=['ZGC', 'G1GC', 'Parallel', 'Serial', 'Shenandoah', 'Epsilon'], 
                       help='要分析的GC类型')
    parser.add_argument('--output_dir', type=str, default=None, 
                       help='输出CSV文件的目录 (默认: ./results)')
    parser.add_argument('--jdks', type=str, default='17,21,25,26', 
                       help='要分析的JDK版本，用逗号分隔 (默认: 17,21,25,26)')
    
    args = parser.parse_args()
    
    # 解析JDK版本
    supported_jdks = args.jdks.split(',')
    
    print(f"开始处理GC测试结果...")
    print(f"结果目录: {args.results_dir}")
    print(f"GC类型: {args.gc_type}")
    print(f"JDK版本: {supported_jdks}")
    print(f"输出目录: {args.output_dir}")
    print("=" * 60)
    
    try:
        csv_file = process_results_directory(args.results_dir, args.gc_type, args.output_dir, supported_jdks)
        
        print("\n" + "=" * 60)
        print(f"✓ 批量处理完成!")
        print(f"CSV汇总文件: {csv_file}")
        print(f"\n接下来可以使用图表生成程序:")
        print(f"python3 generate_charts.py 1 {csv_file.stem.split('_')[0]} {args.gc_type}")
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())