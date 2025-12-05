#!/usr/bin/env python3
"""
差分测试工具 - 在不同JDK版本和JVM参数组合下测试Java类文件
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Any
import json
from datetime import datetime

# 导入ClassFileRunner
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from TestRun import ClassFileRunner


class JDKDifferentialTester:
    # JDK版本和对应的JVM参数组合
    JDK_CONFIGS = {
        "11": [
            ["-XX:+UseSerialGC"],
            ["-XX:+UseParallelGC"],
            ["-XX:+UseParallelOldGC"],
            ["-XX:+UseG1GC"],
            ["-XX:+UnlockExperimentalVMOptions","-XX:+UseShenandoahGC"]
            ,["-XX:+UnlockExperimentalVMOptions", "-XX:+UseEpsilonGC"]
        ],
        "17": [
            ["-XX:+UseSerialGC"],
            ["-XX:+UseParallelGC"],
            ["-XX:+UseG1GC"],
            ["-XX:+UseZGC"],
            ["-XX:+UseShenandoahGC"]
            ,["-XX:+UnlockExperimentalVMOptions","-XX:+UseEpsilonGC"]
        ],
        "21": [
            ["-XX:+UseSerialGC"],
            ["-XX:+UseParallelGC"],
            ["-XX:+UseG1GC"],
            ["-XX:+UseZGC"],
            ["-XX:+UseShenandoahGC"]
            ,["-XX:+UnlockExperimentalVMOptions","-XX:+UseEpsilonGC"]
        ],
        "25": [
            ["-XX:+UseSerialGC"],
            ["-XX:+UseParallelGC"],
            ["-XX:+UseG1GC"],
            ["-XX:+UseZGC"],
            ["-XX:+UseShenandoahGC","-XX:+UnlockExperimentalVMOptions","-XX:ShenandoahGCMode=generational"],
            ["-XX:+UnlockExperimentalVMOptions", "-XX:+UseEpsilonGC"]
        ],
        "26": [
            ["-XX:+UseSerialGC"],
            ["-XX:+UseParallelGC"],
            ["-XX:+UseG1GC"],
            ["-XX:+UseZGC"],
            ["-XX:+UnlockExperimentalVMOptions", "-XX:+UseEpsilonGC"]
        ]
    }

    def __init__(self, timeout_seconds=60):
        self.timeout_seconds = timeout_seconds
        self.runner = ClassFileRunner(timeout_seconds=timeout_seconds)

    def switch_jdk(self, jdk_version: str) -> bool:
        """
        使用jenv切换JDK版本

        Args:
            jdk_version: JDK版本名称，如 "1.8", "11"等

        Returns:
            bool: 切换是否成功
        """
        try:
            result = subprocess.run(
                ["jenv", "local", jdk_version],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print(f"✓ 成功切换到: {jdk_version}")
                return True
            else:
                print(f"✗ 切换失败 {jdk_version}: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            print(f"✗ 切换超时: {jdk_version}")
            return False
        except FileNotFoundError:
            print("✗ 未找到jenv命令，请确保jenv已安装并配置")
            return False
        except Exception as e:
            print(f"✗ 切换异常 {jdk_version}: {e}")
            return False

    def get_current_jdk_version(self) -> str:
        """
        获取当前JDK版本
        """
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # 从版本输出中提取信息
            if "1.8" in result.stderr:
                return "1.8"
            elif "11." in result.stderr:
                return "11"
            elif "17." in result.stderr:
                return "17"
            elif "21." in result.stderr:
                return "21"
            elif "25." in result.stderr:
                return "25"
            elif "26." in result.stderr:
                return "26"
            else:
                return "unknown"
        except Exception as e:
            print(f"获取JDK版本失败: {e}")
            return "unknown"

    def test_class_with_jdk_variants(self, class_file_path: Path, parent_directory: str) -> List[Dict]:
        """
        在所有的JDK版本和JVM参数组合下测试单个类文件

        Returns:
            List[Dict]: 所有测试结果列表
        """
        class_results = []
        original_jdk = self.get_current_jdk_version()

        print(f"\n测试类文件: {class_file_path.name}")
        print("-" * 50)

        for jdk_version, jvm_params_list in self.JDK_CONFIGS.items():
            print(f"\n切换到 {jdk_version}...")

            # 切换JDK版本
            if not self.switch_jdk(jdk_version):
                print(f"  跳过 {jdk_version} 的测试")
                continue

            for jvm_params in jvm_params_list:
                print(f"  使用JVM参数: {' '.join(jvm_params)}")

                try:
                    # 使用ClassFileRunner测试类文件
                    result = self.runner.test_class_file(
                        class_file_path,
                        parent_directory,
                        jvm_args=jvm_params
                    )

                    # 添加JDK和JVM参数信息
                    result["jdk_version"] = jdk_version
                    result["jvm_parameters"] = jvm_params
                    result["test_timestamp"] = datetime.now().isoformat()

                    # 对epsilonGC，仅计入执行成功的情况
                    if "-XX:+UseEpsilonGC" in jvm_params and not result["success"]:
                        print(f"    ⚠ Epsilon GC 测试失败，跳过记录")
                        continue

                    class_results.append(result)

                    status = "✓ 成功" if result["success"] else "✗ 失败"
                    print(f"    {status} | 退出码: {result['exit_code']} | 耗时: {result['duration_ms']}ms")

                except Exception as e:
                    print(f"    ✗ 测试异常: {e}")
                    error_result = {
                        "class_file": str(class_file_path),
                        "package": "",
                        "class_name": class_file_path.stem,
                        "success": False,
                        "output": f"Test execution error: {str(e)}",
                        "exit_code": -1,
                        "duration_ms": 0,
                        "jdk_version": jdk_version,
                        "jvm_parameters": jvm_params,
                        "test_timestamp": datetime.now().isoformat()
                    }
                    # 对epsilonGC，仅计入执行成功的情况
                    if "-XX:+UseEpsilonGC" not in jvm_params:
                        class_results.append(error_result)
                    else:
                        print(f"    ⚠ Epsilon GC 测试异常，跳过记录")

        # 切换回原始JDK
        if original_jdk != "unknown":
            self.switch_jdk(original_jdk)

        return class_results

    def generate_log_content(self, results: List[Dict]) -> str:
        """
        生成.log文件内容（JSON格式）

        Args:
            results: 单个类文件的所有测试结果

        Returns:
            str: .log文件内容（JSON格式）
        """
        # 构建结构化的日志数据
        log_data = {
            "class_file_info": {
                "file_path": results[0]["class_file"] if results else "",
                "package": results[0]["package"] if results else "",
                "class_name": results[0]["class_name"] if results else "",
            },
            "test_summary": {
                "total_tests": len(results),
                "successful_tests": sum(1 for r in results if r["success"]),
                "failed_tests": sum(1 for r in results if not r["success"]),
                "success_rate": round((sum(1 for r in results if r["success"]) / len(results) * 100),
                                      2) if results else 0
            },
            "test_results": []
        }

        # 添加每个测试环境的详细结果
        for result in results:
            test_result = {
                "jdk_version": result["jdk_version"],
                "jvm_parameters": result["jvm_parameters"],
                "success": result["success"],
                "exit_code": result["exit_code"],
                "duration_ms": result["duration_ms"],
                "output": result["output"],
                "test_timestamp": result.get("test_timestamp", "")
            }
            log_data["test_results"].append(test_result)

        # 将JSON数据格式化为易读的字符串
        return json.dumps(log_data, indent=2, ensure_ascii=False)

    def scan_and_test_directory(self, base_dir: str, output_dir: str):
        """
        递归扫描目录并在所有JDK版本下测试所有.class文件

        Args:
            base_dir: 输入目录，包含.class文件
            output_dir: 输出目录，用于保存.log文件
        """
        base_path = Path(base_dir)
        output_path = Path(output_dir)

        print(f"开始扫描目录: {base_dir}")
        print(f"输出目录: {output_dir}")
        print("=" * 60)

        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)

        total_files = 0
        for item in base_path.rglob('*'):
            if item.is_file() and item.suffix == '.class':
                # 获取父目录名
                parent_dir = item.parent.name

                # 跳过以@结尾的目录（可能是临时目录）
                if parent_dir.endswith('@'):
                    continue

                total_files += 1

        print(f"找到 {total_files} 个类文件")
        print("开始差分测试...")

        current_file = 0
        for item in base_path.rglob('*'):
            if item.is_file() and item.suffix == '.class':
                # 获取父目录名
                parent_dir = item.parent.name

                # 跳过以@结尾的目录（可能是临时目录）
                if parent_dir.endswith('@'):
                    continue

                current_file += 1
                print(f"\n[{current_file}/{total_files}] ", end="")

                # 在所有JDK版本和JVM参数组合下测试这个类文件
                class_results = self.test_class_with_jdk_variants(item, parent_dir)

                # 计算相对于基目录的相对路径
                relative_path = item.relative_to(base_path)

                # 构建对应的.log文件路径
                log_file_path = output_path / relative_path.with_suffix('.json')

                # 确保输出目录存在
                log_file_path.parent.mkdir(parents=True, exist_ok=True)

                # 生成并写入.log文件内容
                log_content = self.generate_log_content(class_results)
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)

                print(f"  结果已保存: {log_file_path}")

        print(f"\n测试完成! 共测试 {total_files} 个类文件")
        print(f"结果已保存到: {output_dir}")


def main():
    """
    主函数
    """
    import argparse

    parser = argparse.ArgumentParser(description='Java类文件差分测试工具')
    parser.add_argument('input_dir', help='包含.class文件的输入目录')
    parser.add_argument('output_dir', help='保存log文件的输出目录')
    parser.add_argument('-t', '--timeout', type=int, default=60,
                        help='测试超时时间（秒），默认60秒')


    args = parser.parse_args()

    if not os.path.exists(args.input_dir):
        print(f"错误: 输入目录 '{args.input_dir}' 不存在")
        sys.exit(1)

    # 创建测试器
    tester = JDKDifferentialTester(timeout_seconds=args.timeout)

    try:
        # 执行差分测试
        tester.scan_and_test_directory(args.input_dir, args.output_dir)



    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()