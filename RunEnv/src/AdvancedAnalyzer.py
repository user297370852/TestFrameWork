#!/usr/bin/env python3
"""
极简高级预言分析器。

只调用 Test_oracles.ADVANCED_ORACLES，生成面向排查人员阅读的简洁报告。
输出格式与 BasicAnalyzer 完全一致。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from Test_oracles import ADVANCED_ORACLES
except ImportError:
    print("错误: 无法导入 Test_oracles.ADVANCED_ORACLES，请确保该模块存在")
    ADVANCED_ORACLES = []


class AdvancedAnalyzer:
    def __init__(self, oracles: Optional[List[Any]] = None):
        self.oracles = oracles if oracles is not None else ADVANCED_ORACLES

    def analyze_json_file(self, json_file_path: Path) -> List[Dict[str, Any]]:
        file_anomalies = []

        try:
            with json_file_path.open("r", encoding="utf-8") as f:
                log_data = json.load(f)
        except Exception as exc:
            return [{
                "type": "parse_error",
                "file_path": str(json_file_path),
                "score": 1.0,
                "info": [f"测试记录格式异常，JSON解析失败：{exc}"],
            }]

        for oracle in self.oracles:
            try:
                anomaly = oracle(log_data, str(json_file_path))
                if anomaly is not None:
                    file_anomalies.append(anomaly)
            except Exception as exc:
                file_anomalies.append({
                    "type": "oracle_execution_error",
                    "file_path": str(json_file_path),
                    "oracle_name": oracle.__name__,
                    "score": 1.0,
                    "info": [f"测试预言执行异常，{oracle.__name__}执行失败：{exc}"],
                })

        return file_anomalies

    def scan_and_analyze_directory(self, input_dir: str, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
        root = Path(input_dir)
        output_file = Path(output_path).resolve() if output_path else None
        all_anomalies = []

        for json_file in root.rglob("*.json"):
            if "reports" in json_file.parts:
                continue
            if output_file and json_file.resolve() == output_file:
                continue
            all_anomalies.extend(self.analyze_json_file(json_file))

        return all_anomalies

    def generate_report(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        cases = {}

        for anomaly in anomalies:
            file_path = anomaly.get("file_path", "unknown")
            if file_path not in cases:
                cases[file_path] = {
                    "file_path": file_path,
                    "triggered_oracles": [],
                    "info": [],
                    "_score": 0.0,
                }

            oracle_type = anomaly.get("type", "unknown_oracle")
            if oracle_type not in cases[file_path]["triggered_oracles"]:
                cases[file_path]["triggered_oracles"].append(oracle_type)

            cases[file_path]["_score"] += self._extract_score(anomaly)
            cases[file_path]["info"].extend(self._extract_info(anomaly))

        ranked_cases = list(cases.values())
        ranked_cases.sort(key=lambda case: case["_score"], reverse=True)

        for case in ranked_cases:
            del case["_score"]

        return {"ranked_cases": ranked_cases}

    def _extract_score(self, anomaly: Dict[str, Any]) -> float:
        if isinstance(anomaly.get("score"), (int, float)):
            return float(anomaly["score"])

        total_score = 0.0
        for item in self._iter_leaf_anomalies(anomaly):
            score = item.get("score") if isinstance(item, dict) else None
            if isinstance(score, (int, float)):
                total_score += float(score)

        return total_score if total_score > 0 else 1.0

    def _extract_info(self, anomaly: Dict[str, Any]) -> List[str]:
        infos = []

        if isinstance(anomaly.get("info"), str):
            infos.append(anomaly["info"])
        elif isinstance(anomaly.get("info"), list):
            infos.extend(item for item in anomaly["info"] if isinstance(item, str))

        for item in self._iter_leaf_anomalies(anomaly):
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("info"), str):
                infos.append(item["info"])

        if not infos:
            infos.append(self._fallback_info(anomaly, anomaly))

        return infos

    def _iter_leaf_anomalies(self, anomaly: Dict[str, Any]) -> List[Dict[str, Any]]:
        leaves = []

        for key in ("anomalies", "regressions", "failed_tests"):
            value = anomaly.get(key)
            if isinstance(value, list):
                leaves.extend(item for item in value if isinstance(item, dict))

        performance_issues = anomaly.get("performance_issues")
        if isinstance(performance_issues, list):
            for issue in performance_issues:
                if not isinstance(issue, dict):
                    continue
                slow_tests = issue.get("slow_tests")
                if isinstance(slow_tests, list):
                    leaves.extend(item for item in slow_tests if isinstance(item, dict))
                issue_anomalies = issue.get("anomalies")
                if isinstance(issue_anomalies, list):
                    leaves.extend(item for item in issue_anomalies if isinstance(item, dict))

        return leaves

    def _looks_like_triggered_anomaly(self, item: Dict[str, Any]) -> bool:
        return any(key in item for key in ("score", "anomaly_type", "jdk_version", "gc_type", "exit_code"))

    def _fallback_info(self, anomaly: Dict[str, Any], item: Dict[str, Any]) -> str:
        jdk_version = item.get("jdk_version") or item.get("curr_jdk_version") or item.get("to_version") or "unknown"
        gc_type = item.get("gc_type") or item.get("low_latency_gc_type") or "Unknown"
        oracle_type = anomaly.get("type", "unknown_oracle")
        return f"{jdk_version}-{gc_type}: {oracle_type}异常，缺少可读异常说明"


def main() -> None:
    parser = argparse.ArgumentParser(description="高级测试预言极简报告生成器")
    parser.add_argument("input_dir", help="包含JSON测试记录的目录")
    parser.add_argument("-o", "--output", default="advanced_report.json", help="输出报告路径")
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"错误: 目录 '{args.input_dir}' 不存在")
        return

    if not ADVANCED_ORACLES:
        print("错误: 没有可用的高级测试预言，请检查 Test_oracles 模块")
        return

    analyzer = AdvancedAnalyzer()
    anomalies = analyzer.scan_and_analyze_directory(args.input_dir, args.output)
    report = analyzer.generate_report(anomalies)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"高级预言分析完成，共发现 {len(anomalies)} 个触发结果")
    print(f"极简报告已保存至: {output_path}")


if __name__ == "__main__":
    main()
