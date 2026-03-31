#!/usr/bin/env python3
"""
测试脚本：验证analyze_gc_ranking.py的正确性
"""

import json
import tempfile
import os
from pathlib import Path
import sys

# 导入被测试模块
sys.path.insert(0, str(Path(__file__).parent))
from analyze_gc_ranking import (
    extract_gc_type,
    get_metric_value,
    analyze_test_results,
    calculate_average_rankings,
    calculate_overall_rankings,
    MetricType
)


def create_test_data():
    """创建测试数据"""
    return {
        "class_file_info": {
            "file_path": "test.class",
            "package": "test",
            "class_name": "Test"
        },
        "test_summary": {
            "total_tests": 6,
            "successful_tests": 6,
            "failed_tests": 0,
            "success_rate": 100.0
        },
        "test_results": [
            # JDK 21 测试 - 6种GC
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseSerialGC"],
                "success": True,
                "duration_ms": 50,  # 执行时间排名1
                "gc_analysis": {
                    "total_gc_count": 5,
                    "gc_stw_time_ms": 1.5,    # STW排名1
                    "max_stw_time_ms": 0.5,    # Max STW排名1
                }
            },
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseParallelGC"],
                "success": True,
                "duration_ms": 70,  # 执行时间排名2
                "gc_analysis": {
                    "total_gc_count": 7,
                    "gc_stw_time_ms": 3.0,    # STW排名2
                    "max_stw_time_ms": 1.5,    # Max STW排名2
                }
            },
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseG1GC"],
                "success": True,
                "duration_ms": 80,  # 执行时间排名3
                "gc_analysis": {
                    "total_gc_count": 3,
                    "gc_stw_time_ms": 5.0,    # STW排名3
                    "max_stw_time_ms": 3.0,    # Max STW排名3
                }
            },
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseZGC"],
                "success": True,
                "duration_ms": 100,  # 执行时间排名4
                "gc_analysis": {
                    "total_gc_count": 2,
                    "gc_stw_time_ms": 0.5,    # STW排名更低更好，所以是排名1
                    "max_stw_time_ms": 0.3,    # Max STW排名更低更好
                }
            },
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseShenandoahGC"],
                "success": True,
                "duration_ms": 110,  # 执行时间排名5
                "gc_analysis": {
                    "total_gc_count": 4,
                    "gc_stw_time_ms": 0.8,    # STW排名2
                    "max_stw_time_ms": 0.4,    # Max STW排名2
                }
            },
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UnlockExperimentalVMOptions", "-XX:+UseEpsilonGC"],
                "success": True,
                "duration_ms": 60,  # 执行时间排名2 (与ParallelGC相同时间)
                "gc_analysis": {
                    "total_gc_count": 0,
                    "gc_stw_time_ms": 0.0,    # STW排名1 (最低)
                    "max_stw_time_ms": 0.0,    # Max STW排名1 (最低)
                }
            },
            # 失败的测试 - 应该被忽略
            {
                "jdk_version": "21",
                "GC_parameters": ["-XX:+UseSerialGC"],
                "success": False,
                "duration_ms": 30,
                "gc_analysis": {
                    "total_gc_count": 0,
                    "gc_stw_time_ms": 0.0,
                    "max_stw_time_ms": 0.0,
                }
            },
        ]
    }


def test_extract_gc_type():
    """测试GC类型提取"""
    print("\n" + "="*60)
    print("测试 extract_gc_type()")
    print("="*60)
    
    test_cases = [
        (["-XX:+UseSerialGC"], "SerialGC"),
        (["-XX:+UseParallelGC"], "ParallelGC"),
        (["-XX:+UseG1GC"], "G1GC"),
        (["-XX:+UseZGC"], "ZGC"),
        (["-XX:+UseShenandoahGC"], "ShenandoahGC"),
        (["-XX:+UnlockExperimentalVMOptions", "-XX:+UseEpsilonGC"], "EpsilonGC"),
        (["-XX:+UseShenandoahGC", "-XX:+UnlockExperimentalVMOptions", "-XX:ShenandoahGCMode=generational"], "ShenandoahGC-Gen"),
        ([], "Unknown"),
    ]
    
    all_passed = True
    for params, expected in test_cases:
        result = extract_gc_type(params)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} {params} -> {result} (期望: {expected})")
    
    return all_passed


def test_get_metric_value():
    """测试指标值提取"""
    print("\n" + "="*60)
    print("测试 get_metric_value()")
    print("="*60)
    
    test = {
        "duration_ms": 100,
        "gc_analysis": {
            "total_gc_count": 5,
            "gc_stw_time_ms": 2.5,
            "max_stw_time_ms": 1.0,
        }
    }
    
    test_cases = [
        (MetricType.DURATION, 100),
        (MetricType.GC_STW_TIME, 2.5),
        (MetricType.MAX_STW_TIME, 1.0),
        (MetricType.TOTAL_GC_COUNT, 5),
    ]
    
    all_passed = True
    for metric, expected in test_cases:
        result = get_metric_value(test, metric)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} {metric.name}: {result} (期望: {expected})")
    
    # 测试缺失gc_analysis的情况
    test_no_gc = {"duration_ms": 50}
    result = get_metric_value(test_no_gc, MetricType.GC_STW_TIME)
    status = "✓" if result is None else "✗"
    if result is not None:
        all_passed = False
    print(f"  {status} 缺失gc_analysis时返回None: {result}")
    
    return all_passed


def test_duration_ranking():
    """测试执行时间排名计算"""
    print("\n" + "="*60)
    print("测试执行时间排名计算")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.json")
        
        with open(test_file, 'w') as f:
            json.dump(create_test_data(), f)
        
        rankings, _, _, _ = analyze_test_results(tmpdir, MetricType.DURATION)
        
        print(f"\nJDK 21 各GC执行时间排名详情:")
        for gc_type, ranks in rankings.get('21', {}).items():
            print(f"  {gc_type}: {ranks}")
        
        # 验证预期排名
        # SerialGC: duration=50, rank=1
        # EpsilonGC: duration=60, rank=2 (与ParallelGC相同时间，但EpsilonGC在排序后位于ParallelGC之前)
        # ParallelGC: duration=70, rank=2
        # G1GC: duration=80, rank=4
        # ZGC: duration=100, rank=5
        # ShenandoahGC: duration=110, rank=6
        
        expected_ranks = {
            'SerialGC': [1],
            'EpsilonGC': [2],
            'ParallelGC': [3],  # 因为EpsilonGC和ParallelGC时间不同(60 vs 70)
            'G1GC': [4],
            'ZGC': [5],
            'ShenandoahGC': [6],
        }
        
        print("\n验证预期结果:")
        all_passed = True
        for gc_type, expected in expected_ranks.items():
            actual = rankings['21'].get(gc_type, [])
            status = "✓" if actual == expected else "✗"
            if actual != expected:
                all_passed = False
            print(f"  {status} {gc_type}: {actual} (期望: {expected})")
        
        return all_passed


def test_gc_stw_time_ranking():
    """测试GC暂停时间排名计算"""
    print("\n" + "="*60)
    print("测试GC暂停时间排名计算")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.json")
        
        with open(test_file, 'w') as f:
            json.dump(create_test_data(), f)
        
        rankings, _, _, _ = analyze_test_results(tmpdir, MetricType.GC_STW_TIME)
        
        print(f"\nJDK 21 各GC STW时间排名详情:")
        for gc_type, ranks in rankings.get('21', {}).items():
            print(f"  {gc_type}: {ranks}")
        
        # 验证预期排名（STW时间越低排名越靠前）
        # EpsilonGC: 0.0, rank=1
        # ZGC: 0.5, rank=2
        # ShenandoahGC: 0.8, rank=3
        # SerialGC: 1.5, rank=4
        # ParallelGC: 3.0, rank=5
        # G1GC: 5.0, rank=6
        
        expected_ranks = {
            'EpsilonGC': [1],
            'ZGC': [2],
            'ShenandoahGC': [3],
            'SerialGC': [4],
            'ParallelGC': [5],
            'G1GC': [6],
        }
        
        print("\n验证预期结果:")
        all_passed = True
        for gc_type, expected in expected_ranks.items():
            actual = rankings['21'].get(gc_type, [])
            status = "✓" if actual == expected else "✗"
            if actual != expected:
                all_passed = False
            print(f"  {status} {gc_type}: {actual} (期望: {expected})")
        
        return all_passed


def test_max_stw_time_ranking():
    """测试最大单次暂停时间排名计算"""
    print("\n" + "="*60)
    print("测试最大单次暂停时间排名计算")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.json")
        
        with open(test_file, 'w') as f:
            json.dump(create_test_data(), f)
        
        rankings, _, _, _ = analyze_test_results(tmpdir, MetricType.MAX_STW_TIME)
        
        print(f"\nJDK 21 各GC Max STW时间排名详情:")
        for gc_type, ranks in rankings.get('21', {}).items():
            print(f"  {gc_type}: {ranks}")
        
        # 验证预期排名（Max STW时间越低排名越靠前）
        # EpsilonGC: 0.0, rank=1
        # ZGC: 0.3, rank=2
        # ShenandoahGC: 0.4, rank=3
        # SerialGC: 0.5, rank=4
        # ParallelGC: 1.5, rank=5
        # G1GC: 3.0, rank=6
        
        expected_ranks = {
            'EpsilonGC': [1],
            'ZGC': [2],
            'ShenandoahGC': [3],
            'SerialGC': [4],
            'ParallelGC': [5],
            'G1GC': [6],
        }
        
        print("\n验证预期结果:")
        all_passed = True
        for gc_type, expected in expected_ranks.items():
            actual = rankings['21'].get(gc_type, [])
            status = "✓" if actual == expected else "✗"
            if actual != expected:
                all_passed = False
            print(f"  {status} {gc_type}: {actual} (期望: {expected})")
        
        return all_passed


def test_failed_tests_ignored():
    """测试失败的测试用例是否被正确忽略"""
    print("\n" + "="*60)
    print("测试失败用例是否被忽略")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.json")
        
        # 只包含失败测试的数据
        data = {
            "test_results": [
                {
                    "jdk_version": "21",
                    "GC_parameters": ["-XX:+UseSerialGC"],
                    "success": False,
                    "duration_ms": 30,
                    "gc_analysis": {
                        "total_gc_count": 0,
                        "gc_stw_time_ms": 0.0,
                        "max_stw_time_ms": 0.0,
                    }
                },
            ]
        }
        
        with open(test_file, 'w') as f:
            json.dump(data, f)
        
        rankings, _, _, _ = analyze_test_results(tmpdir, MetricType.DURATION)
        
        if '21' in rankings and rankings['21']:
            print("  ✗ 错误: 失败的测试用例没有被忽略")
            return False
        else:
            print("  ✓ 失败的测试用例被正确忽略")
            return True


def main():
    """运行所有测试"""
    print("="*60)
    print("开始验证 analyze_gc_ranking.py 的正确性")
    print("="*60)
    
    tests = [
        ("GC类型提取", test_extract_gc_type),
        ("指标值提取", test_get_metric_value),
        ("执行时间排名", test_duration_ranking),
        ("GC暂停时间排名", test_gc_stw_time_ranking),
        ("最大暂停时间排名", test_max_stw_time_ranking),
        ("失败用例忽略", test_failed_tests_ignored),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ✗ 测试 '{name}' 发生异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✓ 所有测试通过！")
    else:
        print("\n✗ 部分测试失败！")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
