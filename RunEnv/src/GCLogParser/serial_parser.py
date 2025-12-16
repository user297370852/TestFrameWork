"""
Serial GC日志解析器
解析Serial GC的日志格式
"""
import re
from .base_parser import BaseGCParser


class SerialGCParser(BaseGCParser):
    """Serial GC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        
    def get_gc_type(self) -> str:
        return "SerialGC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析Serial GC日志行"""
        line = line.strip()
        
        # 解析最大堆容量
        if "Heap Max Capacity:" in line:
            match = re.search(r'Heap Max Capacity:\s*(\d+)G', line)
            if match:
                self.max_heap_capacity = int(match.group(1)) * 1024
            else:
                match = re.search(r'Heap Max Capacity:\s*(\d+)M', line)
                if match:
                    self.max_heap_capacity = int(match.group(1))
            return False
            
        # 解析GC事件 - 格式类似: GC(0) Pause Young (Allocation Failure) 69M->1M(247M) 0.498ms
        gc_pattern = r'GC\((\d+)\)\s+(.+?)\s+(\d+)M->(\d+)M\((\d+)M\)\s+([\d.]+)ms'
        gc_match = re.search(gc_pattern, line)
        
        if gc_match:
            gc_id = gc_match.group(1)
            gc_type = gc_match.group(2)
            heap_before = int(gc_match.group(3))
            heap_after = int(gc_match.group(4))
            heap_capacity = int(gc_match.group(5))
            stw_time = float(gc_match.group(6))
            
            # 确定GC子类型
            if "Young" in gc_type:
                gc_subtype = "Young GC"
            elif "Full" in gc_type:
                gc_subtype = "Full GC"  
            else:
                gc_subtype = gc_type.strip()
            
            self.update_gc_stats(gc_subtype, stw_time, heap_before, heap_after)
            
            # 更新最大堆容量
            self.max_heap_usage = max(self.max_heap_usage, heap_capacity)
            return True
            
        # 解析另一种格式的GC事件 - 没有容量信息
        simple_gc_pattern = r'GC\((\d+)\)\s+(.+?)\s+([\d.]+)ms'
        simple_gc_match = re.search(simple_gc_pattern, line)
        
        if simple_gc_match:
            gc_id = simple_gc_match.group(1)
            gc_type = simple_gc_match.group(2)
            stw_time = float(simple_gc_match.group(3))
            
            # 确定GC子类型
            if "Young" in gc_type:
                gc_subtype = "Young GC"
            elif "Full" in gc_type:
                gc_subtype = "Full GC"
            else:
                gc_subtype = gc_type.strip()
            
            self.update_gc_stats(gc_subtype, stw_time)
            return True
            
        # 解析堆使用信息
        heap_pattern = r'(DefNew|Tenured| eden space| from space| to space| object space)\s+.*?(\d+)K,?\s*(\d+)%?\s*used'
        heap_match = re.search(heap_pattern, line)
        
        if heap_match:
            space_type = heap_match.group(1)
            used_kb = int(heap_match.group(2))
            usage_mb = used_kb // 1024
            self.max_heap_usage = max(self.max_heap_usage, usage_mb)
            return False
            
        return False
    
    def get_result(self):
        """返回解析结果，包含最大堆容量信息"""
        result = super().get_result()
        
        # 如果没有通过GC事件解析到堆大小，使用初始化时的最大堆容量
        if self.max_heap_usage == 0 and self.max_heap_capacity > 0:
            result["max_heap_mb"] = self.max_heap_capacity
            
        return result
