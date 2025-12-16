#!/usr/bin/env python3
"""
Class File Runner - 自动化验证测试集中class文件的可运行性
优化版本：使用流式处理避免内存堆积
"""

import os
import sys
import tempfile
import shutil
import subprocess
import time
import argparse
import json
from pathlib import Path
from sys import stderr
from typing import List, Dict, Tuple


class ClassFileRunner:
    def __init__(self, timeout_seconds=10):
        self.timeout_seconds = timeout_seconds
        # 不再存储所有结果，只存储统计信息
        self.success_count = 0
        self.fail_count = 0
        self.total_duration = 0
        # 用于报告的成功文件列表（只存储路径，不存储完整结果）
        self.successful_files = []

    def extract_package_and_classname(self, directory_name: str, class_file: str) -> Tuple[str, str]:
        """
        从目录名和类文件名中提取包名和类名
        """
        # 根据规约，目录名就是包名+类名（如果存在包的话）
        # 类名是目录名按'.'分割的最后一部分
        if '.' in directory_name:
            parts = directory_name.split('.')
            class_name = parts[-1]
            package_name = '.'.join(parts[:-1])
            return package_name, class_name
        else:
            # 没有包名的情况
            return "", directory_name

    def create_temp_class_structure(self, class_file_path: Path, package_name: str, class_name: str) -> str:
        """
        创建临时的类目录结构并返回临时目录路径
        """
        temp_dir = tempfile.mkdtemp(prefix="class_run_")

        if package_name:
            # 创建包目录结构
            package_path = Path(temp_dir) / package_name.replace('.', '/')
            package_path.mkdir(parents=True, exist_ok=True)
            class_file_dest = package_path / f"{class_name}.class"
        else:
            # 没有包的情况，直接放在根目录
            class_file_dest = Path(temp_dir) / f"{class_name}.class"

        # 复制类文件到正确位置
        shutil.copy2(class_file_path, class_file_dest)

        return temp_dir

    def run_java_class(self, temp_dir: str, package_name: str, class_name: str, jvm_args: List[str] = None, 
                        enable_gc_logging: bool = False, gc_log_file: str = None) -> Tuple[
        bool, str, int, str]:
        """
        运行Java类文件，返回(是否成功, 输出信息, 退出码, 完整命令)

        Args:
            temp_dir: 临时目录路径
            package_name: 包名
            class_name: 类名
            jvm_args: JVM参数列表，例如 ["-XX:+UseParallelGC", "-Xmx512m"]
            enable_gc_logging: 是否启用GC日志记录
            gc_log_file: GC日志文件路径
        """
        # 构建完整的类名
        if package_name:
            full_class_name = f"{package_name}.{class_name}"
        else:
            full_class_name = class_name

        gcobj_dir = "/Users/yeliu/PycharmProjects/PythonProject/RunEnv"
        eclipse_dir = "/Users/yeliu/IdeaProjects/GCFuzz-main/02Benchmarks/eclipse-dacapo"
        fop_dir = "/Users/yeliu/IdeaProjects/GCFuzz-main/02Benchmarks/fop-dacapo"

        if class_name == "EclipseStarter":
            class_path = f"{gcobj_dir}:{temp_dir}:{eclipse_dir}"
        elif package_name == "org.apache.fop.cli":
            class_path = f"{gcobj_dir}:{temp_dir}:{fop_dir}/*:{fop_dir}/lib/*"
        else:
            class_path = f"{gcobj_dir}:{temp_dir}"

        # 如果 jvm_args 为 None，设置为空列表
        if jvm_args is None:
            jvm_args = []

        # 添加GC日志参数
        if enable_gc_logging and gc_log_file:
            # 针对不同JDK版本使用不同的GC日志参数
            # JDK 9+ 使用新的 -Xlog 参数格式，但为了兼容性也支持旧格式
            gc_args = [f"-Xlog:gc*:file={gc_log_file}:time,uptime,level,tags"]

            jvm_args = gc_args + jvm_args

        if package_name == "org.apache.fop.cli":
            # FOP需要更多内存
            jvm_args = [
                           "-Xmx2g",  # 2GB堆内存
                           "-Xms512m",  # 初始512MB
                           "-Dfop.home=" + fop_dir,
                           "-Djava.awt.headless=true",
                           "-Dorg.apache.fop.allow-external-dtd=true"
                       ] + jvm_args

        try:
            # 构建完整的命令：java [JVM参数] -cp class_path full_class_name
            cmd = ["java"] + jvm_args + ["-cp", class_path, full_class_name]

            # 如果是FOP，使用现有的测试文件
            if package_name == "org.apache.fop.cli":
                fop_dir = "/Users/yeliu/IdeaProjects/GCFuzz-main/02Benchmarks/fop-dacapo"

                # 检查文件是否存在
                xml_file = os.path.join(fop_dir, "name.xml")
                xsl_file = os.path.join(fop_dir, "name2fo.xsl")
                pdf_file = os.path.join(fop_dir, "output.pdf")

                if os.path.exists(xml_file) and os.path.exists(xsl_file):
                    # 使用XML + XSL转换模式
                    cmd.extend([
                        "-xml", xml_file,  # 输入XML文件
                        "-xsl", xsl_file,  # XSLT样式表
                        "-pdf", pdf_file  # 输出PDF
                    ])


            # 设置超时
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            try:
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                exit_code = process.returncode
                # 构建完整命令字符串用于返回
                full_cmd = ' '.join(cmd)

                if process.returncode == 0:
                    return True, stdout.strip(), exit_code, full_cmd
                else:
                    error_msg = stderr.strip() if stderr else stdout.strip()
                    return False, error_msg, exit_code, full_cmd

            except subprocess.TimeoutExpired:
                process.kill()
                full_cmd = ' '.join(cmd)
                return False, f"Timeout after {self.timeout_seconds} seconds", -1, full_cmd

        except Exception as e:
            return False, f"Execution error: {str(e)}", -1, ""

    def test_class_file(self, class_file_path: Path, parent_directory: str,
                        jvm_args: List[str] = None, output_dir: str = None,
                        source_base_dir: str = None, enable_gc_logging: bool = False, 
                        gc_log_file: str = None) -> Dict:
        """
        测试单个类文件的可运行性，支持流式输出

        Args:
            class_file_path: 类文件路径
            parent_directory: 父目录名
            jvm_args: JVM参数列表
            output_dir: 如果提供，成功时立即复制文件
            source_base_dir: 源基础目录，用于保持目录结构
            enable_gc_logging: 是否启用GC日志记录
            gc_log_file: GC日志文件路径
        """
        print(f"Testing: {class_file_path}")

        # 提取包名和类名
        package_name, class_name = self.extract_package_and_classname(
            parent_directory, class_file_path.name
        )

        # 创建临时目录结构
        temp_dir = self.create_temp_class_structure(class_file_path, package_name, class_name)

        try:
            # 记录开始时间
            start_time = time.time()

            # 运行测试
            success, output, exit_code, full_cmd = self.run_java_class(
                temp_dir, package_name, class_name, jvm_args, enable_gc_logging, gc_log_file
            )

            # 截断输出，只保留前1024个字符
            if output and len(output) > 1024:
                output = output[:1024]

            # 计算运行时长（毫秒）
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)

            # 更新统计信息
            if success:
                self.success_count += 1
                self.successful_files.append(str(class_file_path))
                # 如果提供了输出目录，立即复制成功文件
                if output_dir and source_base_dir:
                    self._copy_successful_file_immediately(class_file_path, output_dir, source_base_dir)
            else:
                self.fail_count += 1

            self.total_duration += duration_ms

            result = {
                "class_file": str(class_file_path),
                "package": package_name,
                "class_name": class_name,
                "success": success,
                "output": output,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "full_cmd": full_cmd
            }

            status = "✓ SUCCESS" if success else "✗ FAILED"
            full_class_name = f"{package_name}.{class_name}" if package_name else class_name
            print(f"  {status}: {full_class_name} (耗时: {duration_ms}ms)")
            if not success and output:
                print(f"    Error: {output}")

            return result

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _copy_successful_file_immediately(self, source_file: Path, output_dir: str, source_base_dir: str):
        """立即复制成功的文件到输出目录，保持原始目录结构"""
        try:
            # 计算相对于源基础目录的相对路径
            relative_path = source_file.relative_to(source_base_dir)

            # 构建目标文件路径（保持完整的相对路径）
            dest_file = Path(output_dir) / relative_path

            # 确保目标目录存在
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(source_file, dest_file)
            print(f"  ↳ Copied to: {relative_path}")
        except Exception as e:
            print(f"  ↳ Error copying file {source_file}: {e}")

    def scan_and_test_directory(self, base_dir: str, output_dir: str = None):
        """
        递归扫描目录并测试所有.class文件，支持流式输出

        Args:
            base_dir: 基础目录
            output_dir: 如果提供，成功时立即复制文件
        """
        base_path = Path(base_dir)

        for item in base_path.rglob('*'):
            if item.is_file() and item.suffix == '.class':
                # 获取父目录名
                parent_dir = item.parent.name

                # 跳过以@结尾的目录（可能是临时目录）
                if parent_dir.endswith('@'):
                    continue

                # 测试这个类文件，如果output_dir不为None则立即复制成功文件
                result = self.test_class_file(item, parent_dir, output_dir=output_dir, source_base_dir=base_dir)

    def filter_successful_tests(self, source_dir: str, output_dir: str):
        """
        过滤成功的测试用例并输出到指定目录，保留原始目录结构
        注意：此方法现在主要用于批量模式，流式模式下文件已实时复制
        """
        print(f"\nFinal copy: {len(self.successful_files)} successful test cases to: {output_dir}")

        copied_count = 0
        for source_file_path in self.successful_files:
            source_file = Path(source_file_path)

            # 计算相对于源目录的相对路径
            try:
                relative_path = source_file.relative_to(source_dir)
            except ValueError:
                # 如果无法计算相对路径，直接使用文件名
                relative_path = Path(source_file.name)

            # 构建目标文件路径
            dest_file = Path(output_dir) / relative_path

            # 确保目标目录存在
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件（如果尚未复制）
            if not dest_file.exists():
                shutil.copy2(source_file, dest_file)
                copied_count += 1
                print(f"  Copied: {relative_path}")

        print(f"Successfully copied {copied_count} files to {output_dir}")

    def generate_report(self, output_file: str = None):
        """
        生成测试报告
        """
        total = self.success_count + self.fail_count

        print("\n" + "=" * 60)
        print("TEST REPORT")
        print("=" * 60)
        print(f"Total class files tested: {total}")
        print(f"Successful: {self.success_count}")
        print(f"Failed: {self.fail_count}")
        if total > 0:
            success_rate = self.success_count / total * 100
            avg_duration = self.total_duration / total if total > 0 else 0
            print(f"Success rate: {success_rate:.2f}%")
            print(f"Average duration: {avg_duration:.2f}ms")
        else:
            print("Success rate: 0.00%")
            print("Average duration: 0.00ms")

        # 保存简要结果到文件
        if output_file:
            report_data = {
                'summary': {
                    'total': total,
                    'successful': self.success_count,
                    'failed': self.fail_count,
                    'success_rate': self.success_count / total * 100 if total > 0 else 0,
                    'total_duration_ms': self.total_duration,
                    'average_duration_ms': self.total_duration / total if total > 0 else 0
                },
                'successful_files': self.successful_files
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"\nReport saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Test Java class files and filter successful ones')
    parser.add_argument('testcases_dir', help='Directory containing test cases')
    parser.add_argument('-f', '--filter', metavar='OUTPUT_DIR',
                        help='Filter successful test cases to OUTPUT_DIR')
    parser.add_argument('-r', '--report', metavar='REPORT_FILE',
                        default='class_test_report.json',
                        help='Output report file (default: class_test_report.json)')

    args = parser.parse_args()

    testcases_dir = args.testcases_dir
    output_dir = args.filter
    report_file = args.report

    if not os.path.exists(testcases_dir):
        print(f"Error: Directory '{testcases_dir}' does not exist")
        sys.exit(1)

    runner = ClassFileRunner(timeout_seconds=60)

    print(f"Scanning and testing class files in: {testcases_dir}")
    print("This may take a while...\n")

    try:
        # 关键修改：在扫描测试时如果指定了输出目录，就立即复制成功文件
        if output_dir:
            # 确保输出目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            print(f"Streaming successful files to: {output_dir}")
            # 传递 source_base_dir 参数
            runner.scan_and_test_directory(testcases_dir, output_dir=output_dir)
            # 最后再做一次完整性检查，确保所有成功文件都已复制
            runner.filter_successful_tests(testcases_dir, output_dir)
        else:
            # 报告模式：只测试不复制
            runner.scan_and_test_directory(testcases_dir)

        # 生成报告
        runner.generate_report(report_file)

    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        # 即使被中断，也输出当前进度
        if output_dir:
            runner.filter_successful_tests(testcases_dir, output_dir)
        runner.generate_report(f"interrupted_{report_file}")
    except Exception as e:
        print(f"Error during testing: {e}")
        # 发生错误时也尝试输出当前结果
        if output_dir:
            runner.filter_successful_tests(testcases_dir, output_dir)
        runner.generate_report(f"error_{report_file}")
        sys.exit(1)


if __name__ == "__main__":
    main()