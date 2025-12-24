#!/usr/bin/env python3
"""
GC日志分析器 - 解析Java GC日志文件并提取关键性能指标
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
try:
    from GCLogParser import (
        BaseGCParser,
        SerialGCParser,
        ParallelGCParser,
        G1GCParser,
        ZGCParser,
        ShenandoahGCParser,
        EpsilonGCParser
    )
except ImportError:
    # 如果作为模块导入失败，尝试相对导入
    from .GCLogParser import (
        BaseGCParser,
        SerialGCParser,
        ParallelGCParser,
        G1GCParser,
        ZGCParser,
        ShenandoahGCParser,
        EpsilonGCParser
    )


class GCLogAnalyzer:
    def __init__(self):
        """
        初始化各种实现好的针对某一GC类型的GC日志的解析器
        """
        self.gc_parsers = {
            'serialgc': SerialGCParser(),
            'parallelgc': ParallelGCParser(),
            'paralleloldgc': ParallelGCParser(),  # ParallelOldGC使用ParallelGC的解析器
            'g1gc': G1GCParser(),
            'zgc': ZGCParser(),
            'shenandoahgc': ShenandoahGCParser(),
            'epsilongc': EpsilonGCParser(),
        }
    
    def parse_gc_log(self, gc_log_file: str) -> Dict[str, any]:
        """
        解析GC日志文件，提取GC性能指标
        
        Args:
            gc_log_file: GC日志文件路径
            
        Returns:
            Dict: 包含GC分析结果的字典, 格式如下:
            {
                "total_gc_count": int, #总GC次数
                "gc_stw_time_ms": float, #总GC暂停时长
                "max_stw_time_ms": float, #最大GC暂停时长
                "max_heap_mb": int, #最大堆使用大小
                "gc_type_breakdown": Dict[str, Dict[str, any]] #GC类型细分次数
            }
        """
        # 检查文件是否存在
        if not os.path.exists(gc_log_file):
            raise FileNotFoundError(f"GC日志文件不存在: {gc_log_file}")
        
        # 基于文件名判断GC类型和JDK版本
        gc_log_filename = Path(gc_log_file).name.lower()
        
        # 提取JDK版本
        jdk_version = None
        jdk_match = re.search(r'jdk(\d+)', gc_log_filename)
        if jdk_match:
            jdk_version = int(jdk_match.group(1))
        
        # 检测GC类型
        gc_type = None
        for type_key in self.gc_parsers.keys():
            if type_key in gc_log_filename:
                gc_type = type_key
                break
        
        if gc_type is None:
            raise ValueError(f"无法从文件名 '{gc_log_filename}' 中识别GC类型")
        
        # 获取对应的解析器
        parser = self.gc_parsers[gc_type]
        
        # 如果是ZGC解析器且有JDK版本信息，设置JDK版本
        if gc_type == 'zgc' and jdk_version is not None:
            parser.set_jdk_version(jdk_version)
        
        # 重置解析器状态
        parser.reset()
        
        # 读取并解析日志文件
        try:
            with open(gc_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parser.parse_log_line(line)
        except Exception as e:
            raise RuntimeError(f"读取GC日志文件时发生错误: {e}")
        
        # 返回解析结果
        result = parser.get_result()
        
        # 确保结果符合预期格式
        if "gc_type_breakdown" not in result or not result["gc_type_breakdown"]:
            result["gc_type_breakdown"] = {
                parser.get_gc_type(): {
                    "count": result["total_gc_count"],
                    "stw_time_ms": result["gc_stw_time_ms"]
                }
            }
        
        return result
    
