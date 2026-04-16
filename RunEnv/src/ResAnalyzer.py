#!/usr/bin/env python3
"""
JSON日志分析器 - 基于测试预言的差分测试异常检测

支持两种预言类型:
1. 基础预言(Base_oracles): 基于固定阈值的异常检测
2. 高级预言(Advanced_oracles): 基于统计排名基准模型的异常检测
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

    def _extract_score_from_anomaly(self, anomaly: Dict[str, Any]) -> float:
        """
        从异常记录中提取分数，兼容新旧两种预言格式

        新预言(ranking_anomaly)格式:
        - 顶层有score字段（所有子异常的weighted_z_score之和，使用这个即可）
        - anomalies子列表中每个元素有weighted_z_score字段

        旧预言(base_oracles)格式:
        - 顶层可能有score字段
        - anomalies子列表中每个元素有score字段

        Args:
            anomaly: 单个异常记录

        Returns:
            float: 提取的总分数
        """
        # 新预言格式：顶层score已经是总和，直接返回
        if "score" in anomaly and anomaly["type"] == "ranking_anomaly":
            return anomaly["score"]
        
        total_score = 0.0
        
        # 旧预言格式：需要从anomalies子列表累加
        if "anomalies" in anomaly and isinstance(anomaly["anomalies"], list):
            for sub_anomaly in anomaly["anomalies"]:
                if "score" in sub_anomaly:
                    total_score += sub_anomaly["score"]
        elif "score" in anomaly:
            # 如果没有anomalies子列表，但有顶层score
            total_score = anomaly["score"]

        return total_score

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
                    "triggered_oracles": [],
                    "anomaly_count": 0,
                    # 支持新旧两种severity格式
                    "severity_breakdown": {
                        "high": 0, "medium": 0, "low": 0,  # V2.1格式
                        "severe": 0, "moderate": 0, "none": 0  # V1格式兼容
                    },
                    "descriptions": []  # 收集异常描述用于生成info
                }

            # 提取分数（兼容新旧预言格式）
            score = self._extract_score_from_anomaly(anomaly)
            case_scores[file_path]["total_score"] += score

            # 统计异常数量并收集描述
            if "anomalies" in anomaly:
                case_scores[file_path]["anomaly_count"] += len(anomaly["anomalies"])
                
                # 统计严重程度分布（支持V2.1和V1格式）
                for sub_anomaly in anomaly["anomalies"]:
                    severity = sub_anomaly.get("severity", "none")
                    if severity in case_scores[file_path]["severity_breakdown"]:
                        case_scores[file_path]["severity_breakdown"][severity] += 1
                    # 收集异常描述
                    if "description" in sub_anomaly:
                        case_scores[file_path]["descriptions"].append(sub_anomaly["description"])
            else:
                case_scores[file_path]["anomaly_count"] += 1

            # 记录触发的测试预言
            oracle_type = anomaly["type"]
            if oracle_type not in case_scores[file_path]["triggered_oracles"]:
                case_scores[file_path]["triggered_oracles"].append(oracle_type)

        # 转换为列表并按得分从大到小排序
        case_score_list = list(case_scores.values())
        case_score_list.sort(key=lambda x: x["total_score"], reverse=True)
        
        # 为每个用例生成info字段
        for case in case_score_list:
            case["info"] = self._generate_case_info(case["descriptions"], case["severity_breakdown"])
            # 删除临时的descriptions字段
            del case["descriptions"]

        # 生成统计信息（兼容新旧两种severity格式）
        total_high = sum(c["severity_breakdown"].get("high", 0) for c in case_score_list)
        total_medium = sum(c["severity_breakdown"].get("medium", 0) for c in case_score_list)
        total_low = sum(c["severity_breakdown"].get("low", 0) for c in case_score_list)
        # V1格式兼容
        total_severe = sum(c["severity_breakdown"].get("severe", 0) for c in case_score_list)
        total_moderate = sum(c["severity_breakdown"].get("moderate", 0) for c in case_score_list)
        
        score_stats = {
            "total_cases_with_anomalies": len(case_score_list),
            "single_oracle_cases": len([c for c in case_score_list if len(c["triggered_oracles"]) == 1]),
            "multi_oracle_cases": len([c for c in case_score_list if len(c["triggered_oracles"]) > 1]),
            "max_score": case_score_list[0]["total_score"] if case_score_list else 0.0,
            "min_score": case_score_list[-1]["total_score"] if case_score_list else 0.0,
            "avg_score": sum(c["total_score"] for c in case_score_list) / len(case_score_list) if case_score_list else 0.0,
            # V2.1格式
            "total_high_severity": total_high,
            "total_medium_severity": total_medium,
            "total_low_severity": total_low,
            # V1格式兼容
            "total_severe_anomalies": total_severe + total_high,
            "total_moderate_anomalies": total_moderate + total_medium
        }

        return {
            "statistics": score_stats,
            "ranked_cases": case_score_list
        }

    def _generate_case_info(self, descriptions: List[str], severity_breakdown: Dict[str, int]) -> str:
        """
        根据异常描述生成用例的info字段
        
        Args:
            descriptions: 异常描述列表
            severity_breakdown: 严重程度分布
        
        Returns:
            str: 可读的异常汇总描述
        """
        if not descriptions:
            # 如果没有描述，生成一个简单的统计描述
            high = severity_breakdown.get("high", 0) + severity_breakdown.get("severe", 0)
            medium = severity_breakdown.get("medium", 0) + severity_breakdown.get("moderate", 0)
            low = severity_breakdown.get("low", 0)
            
            parts = []
            if high > 0:
                parts.append(f"{high}处高严重度异常")
            if medium > 0:
                parts.append(f"{medium}处中严重度异常")
            if low > 0:
                parts.append(f"{low}处低严重度异常")
            
            if parts:
                return "检测到" + "、".join(parts)
            return "异常"
        
        # 如果有描述，去重并合并
        unique_descs = list(dict.fromkeys(descriptions))  # 去重保序
        
        # 按 (jdk, gc, metric) 分组，避免重复信息
        groups = {}
        for desc in unique_descs:
            # 解析描述格式: "JDK{jdk_version}的{gc_type}在{metric_name}上{severity_word}：{comparison}"
            if desc.startswith("JDK"):
                try:
                    # 提取关键部分
                    jdk_end = desc.find("的")
                    gc_end = desc.find("在")
                    metric_end = desc.find("上")
                    if jdk_end > 0 and gc_end > 0 and metric_end > 0:
                        jdk = desc[3:jdk_end]
                        gc = desc[jdk_end+1:gc_end]
                        metric = desc[gc_end+1:metric_end]
                        key = (jdk, gc)
                        if key not in groups:
                            groups[key] = []
                        groups[key].append((metric, desc))
                    else:
                        # 无法解析，直接添加
                        if ("_other", "_other") not in groups:
                            groups[("_other", "_other")] = []
                        groups[("_other", "_other")].append(("", desc))
                except Exception:
                    if ("_other", "_other") not in groups:
                        groups[("_other", "_other")] = []
                    groups[("_other", "_other")].append(("", desc))
            else:
                if ("_other", "_other") not in groups:
                    groups[("_other", "_other")] = []
                groups[("_other", "_other")].append(("", desc))
        
        # 生成每组的一句话描述
        parts = []
        for (jdk, gc), items in groups.items():
            if jdk == "_other":
                # 无法分组的描述，直接添加原文
                parts.extend([desc for _, desc in items[:2]])
                continue
            
            # 提取指标名称
            metrics = list(dict.fromkeys([m for m, _ in items]))
            metrics_str = "、".join(metrics[:3])
            if len(metrics) > 3:
                metrics_str += f"等{len(metrics)}个指标"
            
            # 统计严重程度
            high_count = sum(1 for _, desc in items if "显著异常" in desc)
            medium_count = sum(1 for _, desc in items if "异常" in desc and "显著异常" not in desc)
            low_count = sum(1 for _, desc in items if "轻微异常" in desc)
            
            if high_count > 0:
                sev_str = f"{high_count}处高严重度"
            elif medium_count > 0:
                sev_str = f"{medium_count}处中严重度"
            else:
                sev_str = f"{low_count}处低严重度"
            
            parts.append(f"JDK{jdk}的{gc}在{metrics_str}上{sev_str}")
        
        # 合并描述
        if len(parts) == 1:
            return parts[0]
        elif len(parts) <= 3:
            return "；".join(parts)
        else:
            return "；".join(parts[:3]) + f"；共{len(parts)}个组合异常"


def main():
    """
    主函数：分析JSON日志文件并输出异常报告
    """
    import argparse

    parser = argparse.ArgumentParser(description='基于测试预言的差分测试JSON日志分析器')
    parser.add_argument('input_dir', help='包含JSON日志文件的目录')
    parser.add_argument('-o', '--output', default='anomaly_report.json',
                        help='异常报告输出文件，默认anomaly_report.json')
    parser.add_argument('--detail', action='store_true',
                        help='生成详细报告，默认只生成简短的score信息')

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

    if args.detail:
        # 详细模式：生成完整报告
        print("生成详细报告...")
        report = analyzer.generate_anomaly_report(anomalies)

        # 输出详细报告到文件
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"详细分析完成！共检测到 {len(anomalies)} 个异常")
        print(f"详细异常报告已保存至: {args.output}")

        # 在控制台输出简要统计信息
        stats = report["summary"]
        score_stats = report["case_score_summary"]["statistics"]
        print(f"\n异常统计:")
        print(f"  总异常文件数: {stats['total_anomalies']}")
        print(f"  受影响用例数: {stats['affected_files']}")
        print(f"  按类型分布:")
        for anomaly_type, count in stats['anomalies_by_type'].items():
            print(f"    {anomaly_type}: {count}")
        
        # 输出严重程度统计（支持V2.1格式）
        if score_stats.get("total_high_severity", 0) > 0 or score_stats.get("total_medium_severity", 0) > 0:
            print(f"\n严重程度分布:")
            print(f"  高严重度: {score_stats.get('total_high_severity', 0)}")
            print(f"  中严重度: {score_stats.get('total_medium_severity', 0)}")
            print(f"  低严重度: {score_stats.get('total_low_severity', 0)}")
        elif score_stats.get("total_severe_anomalies", 0) > 0 or score_stats.get("total_moderate_anomalies", 0) > 0:
            # V1格式兼容
            print(f"\n严重程度分布:")
            print(f"  严重异常: {score_stats['total_severe_anomalies']}")
            print(f"  中度异常: {score_stats['total_moderate_anomalies']}")
    else:
        # 简短模式：只生成score相关信息
        print("生成简短score报告...")

        # 只生成case_score_summary部分
        case_score_summary = analyzer._generate_case_score_summary(anomalies)

        # 创建简短报告
        brief_report = {
            "summary": {
                "total_anomalies": len(anomalies),
                "total_cases_with_anomalies": case_score_summary["statistics"]["total_cases_with_anomalies"],
                "max_score": case_score_summary["statistics"]["max_score"],
                "avg_score": case_score_summary["statistics"]["avg_score"],
                # V2.1格式
                "total_high_severity": case_score_summary["statistics"].get("total_high_severity", 0),
                "total_medium_severity": case_score_summary["statistics"].get("total_medium_severity", 0),
                "total_low_severity": case_score_summary["statistics"].get("total_low_severity", 0),
                # V1格式兼容
                "total_severe_anomalies": case_score_summary["statistics"]["total_severe_anomalies"],
                "total_moderate_anomalies": case_score_summary["statistics"]["total_moderate_anomalies"]
            },
            "ranked_cases": case_score_summary["ranked_cases"]
        }

        # 输出简短报告到文件
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(brief_report, f, indent=2, ensure_ascii=False)

        print(f"简短分析完成！共检测到 {len(anomalies)} 个异常")
        print(f"简短score报告已保存至: {args.output}")

        # 在控制台输出score排序信息
        stats = case_score_summary["statistics"]
        ranked_cases = case_score_summary["ranked_cases"]
        print(f"\nScore统计:")
        print(f"  异常用例总数: {stats['total_cases_with_anomalies']}")
        print(f"  最高得分: {stats['max_score']:.4f}")
        print(f"  平均得分: {stats['avg_score']:.4f}")
        
        # 输出严重程度统计（支持V2.1格式）
        high_count = stats.get("total_high_severity", 0)
        medium_count = stats.get("total_medium_severity", 0)
        if high_count > 0 or medium_count > 0:
            print(f"  高严重度: {high_count}")
            print(f"  中严重度: {medium_count}")
            print(f"  低严重度: {stats.get('total_low_severity', 0)}")
        elif stats.get("total_severe_anomalies", 0) > 0 or stats.get("total_moderate_anomalies", 0) > 0:
            # V1格式兼容
            print(f"  严重异常数: {stats['total_severe_anomalies']}")
            print(f"  中度异常数: {stats['total_moderate_anomalies']}")

        if ranked_cases:
            print(f"\n前10个最高得分的用例:")
            for i, case in enumerate(ranked_cases[:10]):
                filename = Path(case['file_path']).name
                severity_info = ""
                # V2.1格式
                if case['severity_breakdown'].get('high', 0) > 0:
                    severity_info = f" [高:{case['severity_breakdown']['high']}]"
                if case['severity_breakdown'].get('medium', 0) > 0:
                    severity_info += f" [中:{case['severity_breakdown']['medium']}]"
                if case['severity_breakdown'].get('low', 0) > 0:
                    severity_info += f" [低:{case['severity_breakdown']['low']}]"
                # V1格式兼容
                if not severity_info:
                    if case['severity_breakdown'].get('severe', 0) > 0:
                        severity_info = f" [严重:{case['severity_breakdown']['severe']}]"
                    if case['severity_breakdown'].get('moderate', 0) > 0:
                        severity_info += f" [中度:{case['severity_breakdown']['moderate']}]"
                print(f"  {i+1:2d}. {filename}: {case['total_score']:.4f} (预言: {', '.join(case['triggered_oracles'])}){severity_info}")


if __name__ == "__main__":
    main()
