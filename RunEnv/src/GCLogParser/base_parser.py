"""
GC日志解析器基类
定义所有GC解析器的通用接口和基础功能
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Pattern


class BaseGCParser(ABC):
    """GC日志解析器基类"""
    
    def __init__(self):
        self.gc_count = 0
        self.total_stw_time = 0.0
        self.max_stw_time = 0.0
        self.max_heap_usage = 0
        self.gc_type_breakdown = {}
        
    @abstractmethod
    def get_gc_type(self) -> str:
        """返回GC类型名称"""
        pass
    
    @abstractmethod
    def parse_log_line(self, line: str) -> bool:
        """
        解析单行日志，如果是GC相关日志则返回True并更新统计信息
        """
        pass
    
    def extract_heap_size(self, heap_info: str) -> int:
        """
        从堆信息中提取堆大小（MB）
        例如: "4096 MB", "256M", "4G" -> 转换为MB
        """
        if not heap_info:
            return 0
            
        # 移除空格并转换为大写
        heap_str = heap_info.strip().upper()
        
        # 匹配数字和单位的模式
        patterns = [
            r'(\d+(?:\.\d+)?)\s*GB',  # GB单位
            r'(\d+(?:\.\d+)?)\s*G',   # G单位
            r'(\d+(?:\.\d+)?)\s*MB',  # MB单位  
            r'(\d+(?:\.\d+)?)\s*M',   # M单位
            r'(\d+(?:\.\d+)?)\s*KB',  # KB单位
            r'(\d+(?:\.\d+)?)\s*K',   # K单位
            r'(\d+)'                  # 纯数字，默认为MB
        ]
        
        for pattern in patterns:
            match = re.search(pattern, heap_str)
            if match:
                value = float(match.group(1))
                unit = match.group(0).replace(match.group(1), '').strip().upper()
                
                if unit in ['GB', 'G']:
                    return int(value * 1024)
                elif unit in ['MB', 'M'] or unit == '':
                    return int(value)
                elif unit in ['KB', 'K']:
                    return max(1, int(value / 1024))  # 至少1MB
                    
        return 0
    
    def extract_time_from_ms(self, time_str: str) -> float:
        """
        从时间字符串中提取毫秒数
        例如: "0.933ms", "1.2s", "100ns" -> 转换为ms
        """
        if not time_str:
            return 0.0
            
        patterns = [
            r'(\d+(?:\.\d+)?)\s*ms',  # 毫秒
            r'(\d+(?:\.\d+)?)\s*s',   # 秒
            r'(\d+(?:\.\d+)?)\s*seconds?',  # 秒(完整)
            r'(\d+(?:\.\d+)?)\s*us',  # 微秒
            r'(\d+(?:\.\d+)?)\s*ns'   # 纳秒
        ]
        
        for pattern in patterns:
            match = re.search(pattern, time_str.lower())
            if match:
                value = float(match.group(1))
                unit = match.group(0).replace(match.group(1), '').strip().lower()
                
                if unit in ['ms']:
                    return value
                elif unit in ['s', 'seconds', 'second']:
                    return value * 1000
                elif unit in ['us']:
                    return value / 1000
                elif unit in ['ns']:
                    return value / 1000000
                    
        return 0.0
    
    def update_gc_stats(self, gc_subtype: str, stw_time: float, heap_before: int = 0, heap_after: int = 0):
        """更新GC统计信息"""
        self.gc_count += 1
        self.total_stw_time += stw_time
        self.max_stw_time = max(self.max_stw_time, stw_time)
        
        # 更新最大堆使用量
        max_current_heap = max(heap_before, heap_after)
        self.max_heap_usage = max(self.max_heap_usage, max_current_heap)
        
        # 更新GC类型细分统计
        if gc_subtype not in self.gc_type_breakdown:
            self.gc_type_breakdown[gc_subtype] = {
                "count": 0,
                "stw_time_ms": 0.0
            }
        
        self.gc_type_breakdown[gc_subtype]["count"] += 1
        self.gc_type_breakdown[gc_subtype]["stw_time_ms"] += stw_time
    
    def get_result(self) -> Dict[str, Any]:
        """返回解析结果"""
        return {
            "total_gc_count": self.gc_count,
            "gc_stw_time_ms": self.total_stw_time,
            "max_stw_time_ms": self.max_stw_time,
            "max_heap_mb": self.max_heap_usage,
            "gc_type_breakdown": self.gc_type_breakdown
        }
    
    def reset(self):
        """重置解析器状态"""
        self.gc_count = 0
        self.total_stw_time = 0.0
        self.max_stw_time = 0.0
        self.max_heap_usage = 0
        self.gc_type_breakdown = {}
