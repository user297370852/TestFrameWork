"""
Epsilon GC日志解析器
解析Epsilon GC的日志格式（无GC操作）
"""
import re
from .base_parser import BaseGCParser


class EpsilonGCParser(BaseGCParser):
    """Epsilon GC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        self.committed_heap_size = 0  # EpsilonGC特有的committed大小
        
    def get_gc_type(self) -> str:
        return "EpsilonGC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析Epsilon GC日志行"""
        line = line.strip()
        
        # 解析堆大小信息 - EpsilonGC特有的格式
        # 格式: Resizeable heap; starting at 256M, max: 4096M
        if "Resizeable heap;" in line:
            start_match = re.search(r'starting at (\d+)M', line)
            max_match = re.search(r'max: (\d+)M', line)
            if max_match:
                self.max_heap_capacity = int(max_match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            if start_match:
                start_mb = int(start_match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, start_mb)
            return False
        
        # 解析堆地址信息 - 格式: size: 4096 MB
        if "Heap address:" in line and "size:" in line:
            size_match = re.search(r'size:\s*(\d+)\s*MB', line)
            if size_match:
                self.max_heap_capacity = int(size_match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            return False
        
        # 解析堆使用信息 - 格式: Heap: 4096M reserved, 256M (6.25%) committed, 1809K (0.04%) used
        if "Heap:" in line and "reserved," in line and "committed," in line and "used" in line:
            # 提取committed大小（实际分配的堆大小）
            committed_match = re.search(r'(\d+)M\s*\([^)]+\)\s+committed', line)
            if committed_match:
                committed_mb = int(committed_match.group(1))
                self.committed_heap_size = committed_mb  # 保存committed大小
                self.max_heap_usage = max(self.max_heap_usage, committed_mb)
                self.max_heap_capacity = max(self.max_heap_capacity, committed_mb)
            
            # 提取reserved大小（最大堆容量）
            reserved_match = re.search(r'(\d+)M\s+reserved', line)
            if reserved_match:
                reserved_mb = int(reserved_match.group(1))
                self.max_heap_capacity = max(self.max_heap_capacity, reserved_mb)
            return False
            
        # 解析最大堆容量 - 从初始化日志中提取
        if "Max Capacity:" in line:
            match = re.search(r'Max Capacity:\s*(\d+)M', line)
            if match:
                self.max_heap_capacity = int(match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            return False
            
        # 解析堆大小信息 - 格式: Heap Max Capacity: 4G
        heap_capacity_pattern = r'Heap Max Capacity:\s*(\d+)G'
        heap_g_match = re.search(heap_capacity_pattern, line)
        if heap_g_match:
            self.max_heap_capacity = int(heap_g_match.group(1)) * 1024
            self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            return False
            
        heap_mb_pattern = r'Heap Max Capacity:\s*(\d+)M'
        heap_mb_match = re.search(heap_mb_pattern, line)
        if heap_mb_match:
            self.max_heap_capacity = int(heap_mb_match.group(1))
            self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            return False
            
        # Epsilon GC不会执行GC，但可能有其他暂停事件
        # 解析暂停事件（非GC相关的）
        pause_pattern = r'(pause|stop|safepoint).*?(\d+(?:\.\d+)?)ms'
        pause_match = re.search(pause_pattern, line.lower())
        
        if pause_match:
            pause_type = pause_match.group(1)
            stw_time = float(pause_match.group(2))
            
            # Epsilon GC中的暂停通常不是GC相关的，但我们需要记录为非GC暂停
            # 只有当暂停时间大于某个阈值时才计数
            if stw_time > 0.1:  # 大于0.1ms的暂停才记录
                gc_subtype = f"Non-GC Pause ({pause_type})"
                self.update_gc_stats(gc_subtype, stw_time)
                return True
                
        # 解析堆使用信息
        if "Heap" in line and "used" in line:
            # 格式: Heap used 28M, capacity 256M, max capacity 4096M
            heap_match = re.search(r'max capacity\s+(\d+)M', line)
            if heap_match:
                max_capacity = int(heap_match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, max_capacity)
                self.max_heap_capacity = max(self.max_heap_capacity, max_capacity)
            return False
            
        # 解析Exit时的堆信息
        if "total" in line and "used" in line and "K" in line:
            heap_exit_pattern = r'total\s+(\d+)K,\s+used\s+(\d+)K'
            heap_exit_match = re.search(heap_exit_pattern, line)
            if heap_exit_match:
                capacity = int(heap_exit_match.group(1)) // 1024
                used = int(heap_exit_match.group(2)) // 1024
                self.max_heap_usage = max(self.max_heap_usage, capacity, used)
                self.max_heap_capacity = max(self.max_heap_capacity, capacity)
            return False
            
        return False
    
    def get_result(self):
        """返回解析结果"""
        result = super().get_result()
        
        # Epsilon GC的特性是0次GC
        if self.gc_count == 0:
            result["total_gc_count"] = 0
            result["gc_stw_time_ms"] = 0.0
            result["max_stw_time_ms"] = 0.0
            result["gc_type_breakdown"] = {
                "EpsilonGC": {"count": 0, "stw_time_ms": 0.0}
            }
        
        # 对于Epsilon GC，优先使用committed大小作为max_heap_mb
        if self.committed_heap_size > 0:
            result["max_heap_mb"] = self.committed_heap_size
        elif self.max_heap_usage > 0:
            result["max_heap_mb"] = self.max_heap_usage
        elif self.max_heap_capacity > 0:
            result["max_heap_mb"] = self.max_heap_capacity
            
        return result
