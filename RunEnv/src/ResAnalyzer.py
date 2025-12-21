#!/usr/bin/env python3
"""
JSON日志分析器 - 基于测试预言的差分测试异常检测
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 导入测试预言
try:
    from Test_oracles import TEST_ORACLES
except ImportError:
    print("错误: 无法导入 Test_oracles 模块，请确保该目录存在")
    TEST_ORACLES = []


class ResAnalyzer:
    def __init__(self):
        self.anomalies = []

    def analyze_json_file(self, json_file_path: Path) -> List[Dict[str, Any]]:
        """
        分析单个JSON文件，使用所有测试预言进行检测

        Returns:
            List[Dict]: 检测到的异常列表
        """
        file_anomalies = []

        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)

            # 使用所有测试预言进行检测
            for oracle in TEST_ORACLES:
                try:
                    anomaly = oracle(log_data, str(json_file_path))
                    if anomaly is not None:
                        file_anomalies.append(anomaly)
                except Exception as e:
                    # 单个预言执行失败，记录错误但继续执行其他预言
                    file_anomalies.append({
                        "type": "oracle_execution_error",
                        "file_path": str(json_file_path),
                        "oracle_name": oracle.__name__,
                        "error": str(e)
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
        生成异常报告，按测试预言类型分类

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
            "affected_files": len(set(anomaly["file_path"] for anomaly in anomalies)),
            "active_oracles": len(TEST_ORACLES)
        }

        report = {
            "summary": stats,
            "details": by_type
        }

        return report


def main():
    """
    主函数：分析JSON日志文件并输出异常报告
    """
    import argparse

    parser = argparse.ArgumentParser(description='基于测试预言的差分测试JSON日志分析器')
    parser.add_argument('input_dir', help='包含JSON日志文件的目录')
    parser.add_argument('-o', '--output', default='anomaly_report.json',
                        help='异常报告输出文件，默认anomaly_report.json')

    args = parser.parse_args()

    if not Path(args.input_dir).exists():
        print(f"错误: 目录 '{args.input_dir}' 不存在")
        return

    if not TEST_ORACLES:
        print("错误: 没有可用的测试预言，请检查 Test_oracles 模块")
        return

    print(f"加载了 {len(TEST_ORACLES)} 个测试预言")

    # 创建分析器
    analyzer = ResAnalyzer()

    # 扫描和分析目录
    print("正在扫描和分析JSON日志文件...")
    anomalies = analyzer.scan_and_analyze_directory(args.input_dir)

    # 生成异常报告
    report = analyzer.generate_anomaly_report(anomalies)

    # 输出异常报告到文件
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"分析完成！共检测到 {len(anomalies)} 个异常")
    print(f"异常报告已保存至: {args.output}")

    # 在控制台输出简要统计信息
    stats = report["summary"]
    print(f"\n异常统计:")
    print(f"  总异常数: {stats['total_anomalies']}")
    print(f"  受影响文件: {stats['affected_files']}")
    print(f"  按类型分布:")
    for anomaly_type, count in stats['anomalies_by_type'].items():
        print(f"    {anomaly_type}: {count}")


if __name__ == "__main__":
    main()