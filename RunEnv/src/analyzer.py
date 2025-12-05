#!/usr/bin/env python3
"""
JSON日志分析器 - 检测差分测试中的异常情况
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


class LogAnalyzer:
    def __init__(self):
        self.anomalies = []

    def analyze_json_file(self, json_file_path: Path) -> List[Dict[str, Any]]:
        """
        分析单个JSON文件，检测异常

        Returns:
            List[Dict]: 检测到的异常列表
        """
        file_anomalies = []

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)

            # 检查必需的字段
            if "test_results" not in log_data:
                return file_anomalies

            test_results = log_data["test_results"]
            if not test_results:
                return file_anomalies

            # 1. 失败分析：检测success=false或exit_code!=0的情况
            failed_tests = []
            for result in test_results:
                if not result.get("success", True) or result.get("exit_code", 0) != 0:
                    failed_tests.append({
                        "jdk_version": result.get("jdk_version", "unknown"),
                        "jvm_parameters": result.get("jvm_parameters", []),
                        "exit_code": result.get("exit_code", -1),
                        "output": result.get("output", ""),
                        "duration_ms": result.get("duration_ms", 0)
                    })

            if failed_tests:
                file_anomalies.append({
                    "type": "test_failure",
                    "file_path": str(json_file_path),
                    "class_info": log_data.get("class_file_info", {}),
                    "failed_tests": failed_tests,
                    "total_tests": len(test_results),
                    "failed_count": len(failed_tests)
                })

            # 2. 异常时间分析：检测执行时间异常的情况
            # 获取所有成功测试的执行时间
            successful_durations = [
                result.get("duration_ms", 0)
                for result in test_results
                if result.get("success", True) and result.get("exit_code", 0) == 0
            ]

            if len(successful_durations) >= 2:  # 至少需要2个成功测试才能进行时间分析
                min_duration = min(successful_durations)
                threshold = min_duration * 10  # 异常阈值：最小时间的10倍

                slow_tests = []
                for result in test_results:
                    duration = result.get("duration_ms", 0)
                    if duration > threshold:
                        slow_tests.append({
                            "jdk_version": result.get("jdk_version", "unknown"),
                            "jvm_parameters": result.get("jvm_parameters", []),
                            "duration_ms": duration,
                            "threshold": threshold,
                            "min_duration": min_duration,
                            "ratio": round(duration / min_duration, 2) if min_duration > 0 else float('inf')
                        })

                if slow_tests:
                    file_anomalies.append({
                        "type": "performance_anomaly",
                        "file_path": str(json_file_path),
                        "class_info": log_data.get("class_file_info", {}),
                        "slow_tests": slow_tests,
                        "min_duration": min_duration,
                        "threshold": threshold
                    })

        except Exception as e:
            # 文件读取或解析异常
            file_anomalies.append({
                "type": "parse_error",
                "file_path": str(json_file_path),
                "error": str(e)
            })

        return file_anomalies

    def scan_and_analyze_directory(self, output_dir: str) -> List[Dict[str, Any]]:
        """
        递归扫描目录并分析所有JSON文件

        Args:
            output_dir: 包含JSON日志文件的目录

        Returns:
            List[Dict]: 所有检测到的异常列表
        """
        output_path = Path(output_dir)
        all_anomalies = []

        # 递归扫描所有JSON文件
        for json_file in output_path.rglob('*.json'):
            file_anomalies = self.analyze_json_file(json_file)
            all_anomalies.extend(file_anomalies)

        return all_anomalies

    def generate_anomaly_report(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成异常报告

        Returns:
            Dict: 结构化的异常报告
        """
        # 按异常类型分类
        by_type = {}
        for anomaly in anomalies:
            anomaly_type = anomaly["type"]
            if anomaly_type not in by_type:
                by_type[anomaly_type] = []
            by_type[anomaly_type].append(anomaly)

        # 统计信息
        stats = {
            "total_anomalies": len(anomalies),
            "anomalies_by_type": {k: len(v) for k, v in by_type.items()},
            "affected_files": len(set(anomaly["file_path"] for anomaly in anomalies))
        }

        report = {
            "summary": stats,
            "details": by_type
        }

        return report


def main():
    """
    主函数：分析JSON日志文件并输出异常
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input_dir', help='包含JSON日志文件的目录')
    # 可选参数：输出文件路径
    parser.add_argument('-o', '--output',
                        default='anomaly_report.json',
                        help='异常报告输出文件，默认anomaly_report.json')

    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"错误: 目录 '{args.input_dir}' 不存在", file=sys.stderr)
        sys.exit(1)  # 用sys.exit退出，而非return（return在函数外无效）

    # 2. 可选：检查输出文件的父目录是否存在，不存在则创建
    output_path = Path(args.output)
    output_dir = output_path.parent
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"提示: 自动创建输出目录 '{output_dir}'")

    # 创建分析器
    analyzer = LogAnalyzer()

    # 扫描和分析目录
    anomalies = analyzer.scan_and_analyze_directory(args.input_dir)

    # 生成异常报告
    report = analyzer.generate_anomaly_report(anomalies)

    # 输出异常报告到文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # 在控制台输出异常信息（按题目要求）
    if anomalies:
        for anomaly in anomalies:
            if anomaly["type"] == "test_failure":
                print(f"测试失败: {anomaly['file_path']}")
                print(f"  失败测试数: {anomaly['failed_count']}/{anomaly['total_tests']}")
                for failed_test in anomaly['failed_tests']:
                    print(
                        f"  - JDK: {failed_test['jdk_version']}, 参数: {' '.join(failed_test['jvm_parameters'])}, 退出码: {failed_test['exit_code']}")

            elif anomaly["type"] == "performance_anomaly":
                print(f"性能异常: {anomaly['file_path']}")
                for slow_test in anomaly['slow_tests']:
                    print(
                        f"  - JDK: {slow_test['jdk_version']}, 参数: {' '.join(slow_test['jvm_parameters'])}, 耗时: {slow_test['duration_ms']}ms (阈值: {slow_test['threshold']}ms, 倍数: {slow_test['ratio']}x)")

            elif anomaly["type"] == "parse_error":
                print(f"解析错误: {anomaly['file_path']}")
                print(f"  错误: {anomaly['error']}")

            print()  # 空行分隔


if __name__ == "__main__":
    main()