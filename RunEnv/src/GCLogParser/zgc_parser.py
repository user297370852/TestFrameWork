"""
ZGC日志解析器
解析ZGC的日志格式
"""
import re
from .base_parser import BaseGCParser


class ZGCParser(BaseGCParser):
    """ZGC日志解析器"""
    
    def __init__(self):
        super().__init__()
        self.max_heap_capacity = 0
        self.gc_cycles = {}  # 记录每个GC周期的所有暂停事件
        
    def get_gc_type(self) -> str:
        return "ZGC"
    
    def parse_log_line(self, line: str) -> bool:
        """解析ZGC日志行"""
        line = line.strip()
        
        # 解析最大堆容量 - 从初始化日志中提取
        if "Max Capacity:" in line:
            # 格式: Max Capacity: 4096M
            match = re.search(r'Max Capacity:\s*(\d+)M', line)
            if match:
                self.max_heap_capacity = int(match.group(1))
                # 注意：这里不更新max_heap_usage，因为ZGC的max_heap_usage应该是实际使用量
            return False
            
        # 解析ZGC的STW暂停事件 - 实际格式：GC(id) Pause Type time ms
        # 格式: GC(0) Pause Mark Start 0.003ms
        zgc_pause_pattern = r'GC\((\d+)\)\s+Pause\s+(.+?)\s+([\d.]+)ms$'
        pause_match = re.search(zgc_pause_pattern, line)
        
        if pause_match:
            gc_id = pause_match.group(1)
            pause_type = pause_match.group(2)
            pause_time = float(pause_match.group(3))
            
            # 确定GC子类型 - 基于暂停类型
            if "Mark Start" in pause_type:
                gc_subtype = "Pause Mark Start"
            elif "Mark End" in pause_type:
                gc_subtype = "Pause Mark End"
            elif "Relocate Start" in pause_type:
                gc_subtype = "Pause Relocate Start"
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
            self.gc_cycles[gc_id]['pause_times'][gc_subtype] += pause_time
            
            # 更新这个GC周期的总时间
            self.gc_cycles[gc_id]['total_time'] += pause_time
            
            return True
                    
        # 解析Exit时的堆信息 - ZHeap信息
        if "ZHeap" in line and "used" in line:
            # 格式: ZHeap           used 782M, capacity 1596M, max capacity 4096M
            # 注意：ZHeap和used之间可能有多个空格
            heap_match = re.search(r'ZHeap\s+used\s+(\d+)M,\s+capacity\s+(\d+)M,\s+max\s+capacity\s+(\d+)M', line)
            if heap_match:
                used = int(heap_match.group(1))
                capacity = int(heap_match.group(2))
                max_capacity = int(heap_match.group(3))
                
                # 对于ZGC，优先使用实际使用的堆大小
                self.max_heap_usage = max(self.max_heap_usage, used)
                self.max_heap_capacity = max(self.max_heap_capacity, max_capacity)
            return False
            
        return False
    
    def get_result(self):
        """返回解析结果，包含最大堆容量信息"""
        
        # 在返回结果之前，先统计所有GC周期的信息
        self._finalize_gc_stats()
        
        result = super().get_result()
        
        # 对于ZGC，优先使用used大小作为max_heap_mb（这代表实际占用的堆大小）
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
