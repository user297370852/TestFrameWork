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
        生成异常报告，按测试预言类型分类，并添加按用例得分排序的部分

        Returns:
            Dict: 结构化的异常报告
        """
        # 按异常类型分类（保持原有逻辑）
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

        # 创建按用例得分排序的部分
        case_score_summary = self._generate_case_score_summary(anomalies)

        report = {
            "summary": stats,
            "details": by_type,
            "case_score_summary": case_score_summary
        }

        return report

    def _generate_case_score_summary(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成按用例得分排序的摘要
        
        Args:
            anomalies: 异常列表
            
        Returns:
            Dict: 包含按得分排序的用例信息的摘要
        """
        # 按文件路径分组，计算每个用例的总得分
        case_scores = {}
        
        for anomaly in anomalies:
            # 跳过执行错误或解析错误的异常
            if anomaly["type"] in ["oracle_execution_error", "parse_error"]:
                continue
                
            file_path = anomaly["file_path"]
            
            # 初始化用例信息（如果不存在）
            if file_path not in case_scores:
                case_scores[file_path] = {
                    "file_path": file_path,
                    "total_score": 0.0,
                    "triggered_oracles": []
                }
            
            # 累加score（如果存在）
            if "anomalies" in anomaly:
                # 某些异常类型包含多个子异常（如stw_anomaly）
                for sub_anomaly in anomaly["anomalies"]:
                    if "score" in sub_anomaly:
                        case_scores[file_path]["total_score"] += sub_anomaly["score"]
            else:
                # 单个异常的情况
                if "score" in anomaly:
                    case_scores[file_path]["total_score"] += anomaly["score"]
            
            # 记录触发的测试预言
            oracle_type = anomaly["type"]
            if oracle_type not in case_scores[file_path]["triggered_oracles"]:
                case_scores[file_path]["triggered_oracles"].append(oracle_type)
        
        # 转换为列表并按得分从大到小排序
        case_score_list = list(case_scores.values())
        case_score_list.sort(key=lambda x: x["total_score"], reverse=True)
        
        # 生成统计信息
        score_stats = {
            "total_cases_with_anomalies": len(case_score_list),
            "single_oracle_cases": len([c for c in case_score_list if len(c["triggered_oracles"]) == 1]),
            "multi_oracle_cases": len([c for c in case_score_list if len(c["triggered_oracles"]) > 1]),
            "max_score": case_score_list[0]["total_score"] if case_score_list else 0.0,
            "min_score": case_score_list[-1]["total_score"] if case_score_list else 0.0,
            "avg_score": sum(c["total_score"] for c in case_score_list) / len(case_score_list) if case_score_list else 0.0
        }
        
        return {
            "statistics": score_stats,
            "ranked_cases": case_score_list
        }


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