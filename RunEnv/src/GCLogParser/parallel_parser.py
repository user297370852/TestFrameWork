"""
Parallel GC日志解析器
解析Parallel GC和ParallelOld GC的日志格式
"""
import re
from .base_parser import BaseGCParser


class ParallelGCParser(BaseGCParser):
    """Parallel GC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        
    def get_gc_type(self) -> str:
        return "ParallelGC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析Parallel GC日志行"""
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
            
        # 解析GC事件 - Parallel GC格式
        # 格式: GC(0) Pause Young (Allocation Failure) 64M->0M(245M) 0.736ms
        # 注意：必须包含Pause关键字，避免匹配到Phase等子阶段
        gc_pattern = r'GC\((\d+)\)\s+Pause\s+(.+?)\s+(\d+)M->(\d+)M\((\d+)M\)\s+([\d.]+)ms'
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
            elif "Old" in gc_type or "Major" in gc_type:
                gc_subtype = "Old GC"
            else:
                gc_subtype = gc_type.strip()
            
            self.update_gc_stats(gc_subtype, stw_time, heap_before, heap_after)
            
            # 更新最大堆容量
            self.max_heap_usage = max(self.max_heap_usage, heap_capacity)
            return True
            
        # 解析堆使用信息 - Parallel GC特有的格式
        # PSYoungGen: 65536K(76288K)->688K(76288K)
        young_gen_pattern = r'PSYoungGen:\s+(\d+)K\((\d+)K\)->(\d+)K\((\d+)K\)'
        young_match = re.search(young_gen_pattern, line)
        
        if young_match:
            used_before = int(young_match.group(1)) // 1024
            capacity_before = int(young_match.group(2)) // 1024
            used_after = int(young_match.group(3)) // 1024
            self.max_heap_usage = max(self.max_heap_usage, capacity_before)
            return False
            
        # ParOldGen: 0K(175104K)->8K(175104K)
        old_gen_pattern = r'ParOldGen:\s+(\d+)K\((\d+)K\)->(\d+)K\((\d+)K\)'
        old_match = re.search(old_gen_pattern, line)
        
        if old_match:
            used_before = int(old_match.group(1)) // 1024
            capacity_before = int(old_match.group(2)) // 1024
            used_after = int(old_match.group(3)) // 1024
            self.max_heap_usage = max(self.max_heap_usage, capacity_before)
            return False
            
        # 解析exit时的堆信息
        if "total" in line and "used" in line and "K" in line:
            heap_exit_pattern = r'total\s+(\d+)K,\s+used\s+(\d+)K'
            heap_exit_match = re.search(heap_exit_pattern, line)
            if heap_exit_match:
                capacity = int(heap_exit_match.group(1)) // 1024
                used = int(heap_exit_match.group(2)) // 1024
                self.max_heap_usage = max(self.max_heap_usage, capacity, used)
                return False
                
        return False
    
    def get_result(self):
        """返回解析结果，包含最大堆容量信息"""
        result = super().get_result()
        
        # 如果没有通过GC事件解析到堆大小，使用初始化时的最大堆容量
        if self.max_heap_usage == 0 and self.max_heap_capacity > 0:
            result["max_heap_mb"] = self.max_heap_capacity
            
        return result
