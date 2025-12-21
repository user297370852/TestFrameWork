#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Java项目转种子程序集转换工具

该工具将Java项目转换为符合种子程序构建规约的种子程序集。
生成的种子程序集可用于Fuzz工具的输入。

作者: Fuzz工具开发团队
版本: 1.0
日期: 2025年12月
"""

import os
import shutil
import subprocess
import tempfile
import re
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import sys

class JavaToSeedsConverter:
    """Java项目到种子程序集的转换器"""
    
    def __init__(self, java_src_path: str, output_path: str, seeds_name: str = "seeds"):
        self.java_src_path = os.path.abspath(java_src_path)
        self.output_path = os.path.abspath(output_path)
        self.seeds_name = seeds_name
        self.seeds_dir = os.path.join(self.output_path, seeds_name)
        self.production_dir = os.path.join(self.seeds_dir, "out", "production", seeds_name)
        
        # 配置文件路径
        self.testcases_file = os.path.join(self.seeds_dir, "testcases.txt")
        self.skipclass_file = os.path.join(self.seeds_dir, "skipclass.txt")
        
        # 统计信息
        self.stats = {
            'total_java_files': 0,
            'compilable_files': 0,
            'skipped_files': 0,
            'successful_files': 0,
            'compilation_errors': 0
        }
        
        # JDK配置
        self.target_java_version = "1.8"
        self.target_bytecode_version = "52"
        
        # 创建输出目录
        self._create_directories()
        
    def _create_directories(self):
        """创建输出目录结构"""
        if os.path.exists(self.seeds_dir):
            shutil.rmtree(self.seeds_dir)
            
        os.makedirs(self.production_dir, exist_ok=True)
        print(f"✅ 创建输出目录: {self.production_dir}")
        
    def _check_jenv(self) -> bool:
        """检查jenv是否可用"""
        try:
            result = subprocess.run(['jenv', 'version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ jenv可用: {result.stdout.strip()}")
                return True
            else:
                print("❌ jenv不可用")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("❌ jenv不可用")
            return False
            
    def _set_java_version(self) -> bool:
        """设置Java版本为1.8"""
        if not self._check_jenv():
            return False
            
        try:
            # 设置Java版本
            result = subprocess.run(['jenv', 'local', '1.8'],
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print("✅ Java版本已设置为1.8")
                
                # 验证Java版本
                version_result = subprocess.run(['java', '-version'], 
                                              capture_output=True, text=True, timeout=10)
                if version_result.returncode == 0:
                    version_info = version_result.stderr or version_result.stdout
                    print(f"📍 当前Java版本: {version_info.split()[2] if len(version_info.split()) > 2 else 'unknown'}")
                    return True
                else:
                    print("❌ 无法验证Java版本")
                    return False
            else:
                print(f"❌ 设置Java版本失败: {result.stderr}")
                return False
                
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"❌ 设置Java版本时出错: {e}")
            return False
            
    def _find_java_files(self) -> List[str]:
        """查找所有Java文件"""
        java_files = []
        
        for root, dirs, files in os.walk(self.java_src_path):
            # 跳过target、build等构建目录
            dirs[:] = [d for d in dirs if d not in ['target', 'build', 'out', '.git']]
            
            for file in files:
                if file.endswith('.java'):
                    java_file = os.path.join(root, file)
                    java_files.append(java_file)
                    
        self.stats['total_java_files'] = len(java_files)
        print(f"📄 找到 {len(java_files)} 个Java文件")
        
        return java_files
        
    def _extract_package_and_class(self, java_file: str) -> Tuple[Optional[str], str]:
        """从Java文件中提取包名和类名"""
        try:
            with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 提取包名
            package_match = re.search(r'package\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*;', content)
            package_name = package_match.group(1) if package_match else None
            
            # 提取类名（public class或interface）
            class_match = re.search(r'(?:public\s+)?class\s+([a-zA-Z_][a-zA-Z0-9_]*)', content)
            if not class_match:
                # 尝试匹配interface
                class_match = re.search(r'interface\s+([a-zA-Z_][a-zA-Z0-9_]*)', content)
                
            if class_match:
                class_name = class_match.group(1)
                return package_name, class_name
            else:
                # 使用文件名作为类名
                class_name = os.path.splitext(os.path.basename(java_file))[0]
                return package_name, class_name
                
        except Exception as e:
            print(f"❌ 解析Java文件失败 {java_file}: {e}")
            return None, os.path.splitext(os.path.basename(java_file))[0]
            
    def _has_main_method(self, java_file: str) -> bool:
        """检查Java文件是否包含main方法"""
        try:
            with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 查找main方法
            main_pattern = r'(?:public\s+)?static\s+void\s+main\s*\(\s*String\s*\[\s*\]\s*\w*\s*\)'
            return bool(re.search(main_pattern, content))
            
        except Exception:
            return False
            
    def _compile_java_file(self, java_file: str, package_name: Optional[str], class_name: str) -> bool:
        """编译Java文件"""
        try:
            # 确定输出目录
            if package_name:
                package_dir = os.path.join(self.production_dir, package_name.replace('.', os.sep))
                os.makedirs(package_dir, exist_ok=True)
                output_dir = self.production_dir
            else:
                output_dir = self.production_dir
                
            # 构建编译命令
            cmd = [
                'javac',
                '-source', self.target_java_version,
                '-target', self.target_java_version,
                '-cp', self.production_dir,  # classpath
                '-d', output_dir,  # 输出目录
                java_file
            ]
            
            # 执行编译
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.stats['successful_files'] += 1
                return True
            else:
                print(f"❌ 编译失败 {java_file}: {result.stderr}")
                self.stats['compilation_errors'] += 1
                return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ 编译超时 {java_file}")
            self.stats['compilation_errors'] += 1
            return False
        except Exception as e:
            print(f"❌ 编译出错 {java_file}: {e}")
            self.stats['compilation_errors'] += 1
            return False
            
    def _verify_class_file(self, package_name: Optional[str], class_name: str) -> bool:
        """验证class文件是否存在且可执行"""
        try:
            # 确定class文件路径
            if package_name:
                class_file = os.path.join(self.production_dir, 
                                         package_name.replace('.', os.sep), 
                                         f"{class_name}.class")
            else:
                class_file = os.path.join(self.production_dir, f"{class_name}.class")
                
            # 检查文件是否存在
            if not os.path.exists(class_file):
                return False
                
            # 尝试运行（简单检查）
            full_class_name = f"{package_name}.{class_name}" if package_name else class_name
            
            cmd = ['java', '-cp', self.production_dir, full_class_name]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                # 不管执行结果如何，只要能找到主类就算成功
                return "Error: Main method not found" not in result.stderr and \
                       "Error: Could not find or load main class" not in result.stderr
            except subprocess.TimeoutExpired:
                # 超时说明程序在运行，这也是成功的
                return True
                
        except Exception:
            return False
            
    def _create_testcases_file(self, valid_classes: List[Tuple[Optional[str], str]]):
        """创建testcases.txt文件"""
        try:
            with open(self.testcases_file, 'w', encoding='utf-8') as f:
                for package_name, class_name in valid_classes:
                    if package_name:
                        f.write(f"{package_name}.{class_name}\n")
                    else:
                        f.write(f"{class_name}\n")
                        
            print(f"✅ 创建测试用例文件: {self.testcases_file} ({len(valid_classes)} 个类)")
            
        except Exception as e:
            print(f"❌ 创建testcases.txt失败: {e}")
            
    def _create_skipclass_file(self, skipped_classes: List[Tuple[Optional[str], str]]):
        """创建skipclass.txt文件"""
        try:
            with open(self.skipclass_file, 'w', encoding='utf-8') as f:
                for package_name, class_name in skipped_classes:
                    if package_name:
                        f.write(f"{package_name}.{class_name}\n")
                    else:
                        f.write(f"{class_name}\n")
                        
            print(f"✅ 创建跳过类文件: {self.skipclass_file} ({len(skipped_classes)} 个类)")
            
        except Exception as e:
            print(f"❌ 创建skipclass.txt失败: {e}")
            
    def convert(self):
        """执行转换过程"""
        print("🚀 开始Java项目到种子程序集的转换...")
        
        # 设置Java版本
        if not self._set_java_version():
            print("❌ 无法设置Java版本，转换终止")
            return False
            
        # 查找Java文件
        java_files = self._find_java_files()
        if not java_files:
            print("❌ 未找到Java文件")
            return False
            
        valid_classes = []
        skipped_classes = []
        
        # 处理每个Java文件
        for i, java_file in enumerate(java_files, 1):
            print(f"📝 处理文件 {i}/{len(java_files)}: {os.path.relpath(java_file, self.java_src_path)}")
            
            # 提取包名和类名
            package_name, class_name = self._extract_package_and_class(java_file)
            
            # 检查是否有main方法
            if not self._has_main_method(java_file):
                print(f"⚠️  跳过（无main方法）: {class_name}")
                skipped_classes.append((package_name, class_name))
                self.stats['skipped_files'] += 1
                continue
                
            # 编译Java文件
            if self._compile_java_file(java_file, package_name, class_name):
                # 验证class文件
                if self._verify_class_file(package_name, class_name):
                    valid_classes.append((package_name, class_name))
                    self.stats['compilable_files'] += 1
                    print(f"✅ 成功处理: {class_name}")
                else:
                    print(f"❌ 验证失败: {class_name}")
                    skipped_classes.append((package_name, class_name))
            else:
                skipped_classes.append((package_name, class_name))
                
        # 创建配置文件
        self._create_testcases_file(valid_classes)
        self._create_skipclass_file(skipped_classes)
        
        # 输出统计信息
        self._print_stats()
        
        return True
        
    def _print_stats(self):
        """输出统计信息"""
        print("\n📊 转换统计:")
        print(f"   总Java文件数: {self.stats['total_java_files']}")
        print(f"   可编译文件数: {self.stats['compilable_files']}")
        print(f"   成功转换数: {self.stats['successful_files']}")
        print(f"   跳过文件数: {self.stats['skipped_files']}")
        print(f"   编译错误数: {self.stats['compilation_errors']}")
        
        # 计算成功率
        if self.stats['total_java_files'] > 0:
            success_rate = (self.stats['successful_files'] / self.stats['total_java_files']) * 100
            print(f"   成功率: {success_rate:.1f}%")
            
        print(f"\n📍 输出目录: {self.seeds_dir}")
        print(f"📍 类文件目录: {self.production_dir}")
        print(f"📍 测试用例文件: {self.testcases_file}")
        print(f"📍 跳过类文件: {self.skipclass_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Java项目转种子程序集转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python java_to_seeds.py /path/to/java/src /path/to/output --name seeds
  python java_to_seeds.py ./src/main/java ./output --name myseeds

注意事项:
  1. 需要安装jenv并配置Java 8
  2. Java文件必须包含main方法
  3. 输出将遵循种子程序构建规约
        """
    )
    
    parser.add_argument('java_src', 
                       help='Java源代码目录路径')
    parser.add_argument('output', 
                       help='输出目录路径')
    parser.add_argument('--name', '-n', 
                       default='seeds',
                       help='种子程序集名称 (默认: seeds)')
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='显示详细输出')
    
    args = parser.parse_args()
    
    # 检查输入路径
    if not os.path.exists(args.java_src):
        print(f"❌ 输入路径不存在: {args.java_src}")
        sys.exit(1)
        
    if not os.path.isdir(args.java_src):
        print(f"❌ 输入路径不是目录: {args.java_src}")
        sys.exit(1)
        
    # 创建转换器并执行转换
    converter = JavaToSeedsConverter(args.java_src, args.output, args.name)
    
    try:
        success = converter.convert()
        if success:
            print("\n🎉 转换完成！")
            sys.exit(0)
        else:
            print("\n❌ 转换失败！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  用户中断转换")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 转换过程中出现未预期的错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
