"""
G1 GC日志解析器
解析G1 GC的日志格式
"""
import re
from .base_parser import BaseGCParser


class G1GCParser(BaseGCParser):
    """G1 GC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        
    def get_gc_type(self) -> str:
        return "G1GC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析G1 GC日志行"""
        line = line.strip()
        
        # 解析堆大小信息 - 从初始化日志中提取堆容量
        if "Heap address:" in line:
            # 格式: size: 4096 MB
            heap_mb_match = re.search(r'size:\s*(\d+)\s*MB', line)
            if heap_mb_match:
                self.max_heap_capacity = int(heap_mb_match.group(1))
            return False
        
        # 解析GC事件 - 只解析主要的GC汇总行，避免重复统计GC阶段
        # 格式: GC(0) Pause Young (Normal) (G1 Evacuation Pause) 24M->0M(256M) 0.809ms
        # 注意：这个模式会匹配完整的GC事件行，但排除phase子行
        gc_pattern = r'GC\((\d+)\)\s+Pause\s+(.+?)\s+\d+M->\d+M\(\d+M\)\s+([\d.]+)ms$'
        gc_match = re.search(gc_pattern, line)
        
        if gc_match:
            gc_id = gc_match.group(1)
            gc_type = gc_match.group(2)
            stw_time = float(gc_match.group(3))
            
            # 解析堆使用信息
            heap_pattern = r'(\d+)M->(\d+)M\((\d+)M\)'
            heap_match = re.search(heap_pattern, line)
            if heap_match:
                heap_before = int(heap_match.group(1))
                heap_after = int(heap_match.group(2))
                # max_heap_mb 表示实际堆占用峰值，只使用 GC 前/后的 used 值。
                # 括号内的值是当时堆容量，不计入最大占用。
                self.max_heap_usage = max(self.max_heap_usage, heap_before, heap_after)
            
            # 确定GC子类型
            if "Young (Normal)" in gc_type:
                gc_subtype = "Young GC (Normal)"
            elif "Young (Concurrent Start)" in gc_type:
                gc_subtype = "Young GC (Concurrent Start)"
            elif "Young (Mixed)" in gc_type:
                gc_subtype = "Young GC (Mixed)"
            elif "Full" in gc_type:
                gc_subtype = "Full GC"
            elif "Concurrent Cycle" in gc_type:
                gc_subtype = "Concurrent Cycle"
            else:
                gc_subtype = gc_type.strip()
            
            self.update_gc_stats(gc_subtype, stw_time, heap_before if heap_match else 0, heap_after if heap_match else 0)
            return True
        
        # Eden regions 只描述 G1 分区数量，不代表完整 heap used，不能用于 max_heap_mb。
        if "Eden regions:" in line:
            return False
        
        # 解析Exit时的堆信息 - 获取实际使用的堆大小
        if "garbage-first heap" in line and "total" in line and "used" in line:
            # 格式: total 262144K, used 5714K
            total_match = re.search(r'total\s+(\d+)K', line)
            used_match = re.search(r'used\s+(\d+)K', line)
            if total_match and used_match:
                used_mb = int(used_match.group(1)) // 1024
                self.max_heap_usage = max(self.max_heap_usage, used_mb)
            return False
            
        return False
    
    def get_result(self):
        """返回解析结果，使用实际堆使用量而不是堆容量"""
        result = super().get_result()
        
        result["max_heap_mb"] = self.max_heap_usage
            
        return result
