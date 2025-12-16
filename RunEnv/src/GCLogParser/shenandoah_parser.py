"""
Shenandoah GC日志解析器
解析Shenandoah GC的日志格式
"""
import re
from .base_parser import BaseGCParser


class ShenandoahGCParser(BaseGCParser):
    """Shenandoah GC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        self.gc_cycles = {}  # 记录每个GC周期的所有暂停事件
        
    def get_gc_type(self) -> str:
        return "ShenandoahGC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析Shenandoah GC日志行"""
        line = line.strip()
        
        # 解析最大堆容量 - 从初始化日志中提取
        if "Max Capacity:" in line:
            match = re.search(r'Max Capacity:\s*(\d+)M', line)
            if match:
                self.max_heap_capacity = int(match.group(1))
                self.max_heap_usage = max(self.max_heap_usage, self.max_heap_capacity)
            return False
            
        # 解析完整的GC周期 - 只统计主要的STW暂停事件，避免重复统计GC阶段
        # Shenandoah的主要STW暂停事件：
        # 1. Pause Init Mark (unload classes)
        # 2. Pause Final Mark (unload classes)  
        # 3. Pause Final Roots
        # 这些是真正的STW事件，而不是concurrent阶段
        
        # 匹配STW暂停事件的模式
        stw_pattern = r'GC\((\d+)\)\s+Pause\s+(.+?)\s+([\d.]+)ms$'
        stw_match = re.search(stw_pattern, line)
        
        if stw_match:
            gc_id = stw_match.group(1)
            pause_type = stw_match.group(2)
            stw_time = float(stw_match.group(3))
            
            # 确定GC子类型 - 基于暂停类型
            if "Init Mark" in pause_type:
                gc_subtype = "Init Mark (unload classes)"
            elif "Final Mark" in pause_type:
                gc_subtype = "Final Mark (unload classes)"
            elif "Final Roots" in pause_type:
                gc_subtype = "Final Roots"
            elif "Concurrent" in pause_type:
                gc_subtype = "Concurrent GC"
            else:
                gc_subtype = pause_type.strip()
            
            # 记录这个GC周期的暂停事件
            if gc_id not in self.gc_cycles:
                self.gc_cycles[gc_id] = {
                    'pause_times': {},  # 分别记录每种暂停类型的时间
                    'total_time': 0.0
                }
            
            # 累加特定暂停类型的时间
            if gc_subtype not in self.gc_cycles[gc_id]['pause_times']:
                self.gc_cycles[gc_id]['pause_times'][gc_subtype] = 0.0
            self.gc_cycles[gc_id]['pause_times'][gc_subtype] += stw_time
            
            # 更新这个GC周期的总时间
            self.gc_cycles[gc_id]['total_time'] += stw_time
            
            # 对于Shenandoah，我们只在每个GC周期结束时（检测到新的GC ID时）进行统计
            # 这里先返回True表示这行是GC相关，但暂不更新总体统计
            return True
            
        # 解析堆信息 - 获取堆大小
        # 匹配Shenandoah堆信息的完整格式
        heap_match = re.search(r'(\d+)M\s+max,\s+(\d+)M\s+soft\s+max,\s+(\d+)M\s+committed,\s+(\d+)M\s+used', line)
        if heap_match:
            max_capacity = int(heap_match.group(1))
            soft_max = int(heap_match.group(2))
            committed = int(heap_match.group(3))
            used = int(heap_match.group(4))
            
            # 更新最大堆使用量 - 使用committed和used中的较大值
            self.max_heap_usage = max(self.max_heap_usage, used, committed)
            # 更新最大堆容量
            self.max_heap_capacity = max(self.max_heap_capacity, max_capacity, soft_max)
            return False
            
        # 解析Exit时的堆信息
        if "Heap" in line and "used" in line and "committed" in line:
            heap_match = re.search(r'(\d+)M\s+used,\s+(\d+)M\s+committed', line)
            if heap_match:
                used = int(heap_match.group(1))
                committed = int(heap_match.group(2))
                self.max_heap_usage = max(self.max_heap_usage, used, committed)
            return False
            
        return False
    
    def get_result(self):
        """返回解析结果，包含最大堆容量信息"""
        
        # 在返回结果之前，先统计所有GC周期的信息
        self._finalize_gc_stats()
        
        result = super().get_result()
        
        # 对于ShenandoahGC，优先使用committed/used大小作为max_heap_mb（这代表实际占用的堆大小）
        # 如果没有通过GC事件解析到堆大小，使用初始化时的最大堆容量
        if self.max_heap_usage == 0 and self.max_heap_capacity > 0:
            result["max_heap_mb"] = self.max_heap_capacity
        elif self.max_heap_usage > 0:
            # 确保max_heap_mb反映的是实际使用的堆大小
            result["max_heap_mb"] = self.max_heap_usage
            
        return result
    
    def _finalize_gc_stats(self):
        """最终化GC统计信息，将每个GC周期的总时间统计为一次GC"""
        
        # 重置基类的统计数据，因为我们准备重新计算
        self.gc_count = 0
        self.total_stw_time = 0.0
        self.max_stw_time = 0.0
        self.gc_type_breakdown = {}
        
        # 收集每种暂停类型的准确时间统计和单次暂停时间
        type_stats = {}  # 记录每种暂停类型的统计信息
        all_single_pauses = []  # 记录所有单次暂停时间，用于计算最大值
        
        # 遍历每个GC周期
        for gc_id, cycle_info in self.gc_cycles.items():
            total_cycle_time = cycle_info['total_time']
            pause_times = cycle_info['pause_times']
            
            # 更新总体统计
            self.gc_count += 1
            self.total_stw_time += total_cycle_time
            self.max_stw_time = max(self.max_stw_time, total_cycle_time)
            
            # 统计每种暂停类型的时间和次数
            for pause_type, pause_time in pause_times.items():
                if pause_type not in type_stats:
                    type_stats[pause_type] = {
                        "count": 0,  # 此类型暂停出现的次数
                        "total_time": 0.0  # 此类型暂停的总时间
                    }
                type_stats[pause_type]["count"] += 1
                type_stats[pause_type]["total_time"] += pause_time
                
                # 记录所有单次暂停时间（用于计算最大单次暂停时间）
                all_single_pauses.append(pause_time)
        
        # 计算最大单次暂停时间（这是正确的max_stw_time定义）
        self.max_stw_time = max(all_single_pauses) if all_single_pauses else 0.0
        
        # 构建最终的gc_type_breakdown
        for pause_type, stats in type_stats.items():
            self.gc_type_breakdown[pause_type] = {
                "count": stats["count"],
                "stw_time_ms": stats["total_time"]
            }
    
    def reset(self):
        """重置解析器状态"""
        super().reset()
        self.gc_cycles.clear()  # 清空GC周期记录
