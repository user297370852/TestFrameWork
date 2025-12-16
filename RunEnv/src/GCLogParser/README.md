# GC日志解析器
这是一个用于解析Java GC日志的Python工具库，支持多种GC类型的日志解析，包括Serial GC、Parallel GC、G1GC、ZGC、ShenandoahGC和EpsilonGC。

## 功能特性

- 支持多种GC类型的日志解析
- 提取GC性能指标（次数、暂停时间、堆使用等）
- 支持JDK 11、17、21、25、26版本的GC日志格式
- 完整的单元测试覆盖
- 易于扩展的架构设计

## 支持的GC类型

1. **SerialGC** - 串行垃圾收集器
2. **ParallelGC** - 并行垃圾收集器
3. **G1GC** - G1垃圾收集器
4. **ZGC** - Z垃圾收集器（低延迟）
5. **ShenandoahGC** - Shenandoah垃圾收集器
6. **EpsilonGC** - Epsilon垃圾收集器（无GC操作）

## 安装和使用

### 基本使用

```python
from GCLogAnalyzer import GCLogAnalyzer

# 创建分析器实例
analyzer = GCLogAnalyzer()

# 解析GC日志文件
result = analyzer.parse_gc_log("path/to/gc.log")

# 查看结果
print(f"总GC次数: {result['total_gc_count']}")
print(f"总暂停时间: {result['gc_stw_time_ms']}ms")
print(f"最大暂停时间: {result['max_stw_time_ms']}ms")
print(f"最大堆大小: {result['max_heap_mb']}MB")

# 查看GC类型细分
for gc_type, details in result['gc_type_breakdown'].items():
    print(f"{gc_type}: {details['count']}次, {details['stw_time_ms']}ms")
```

### 结果格式

解析结果包含以下字段：

```json
{
    "total_gc_count": 5,           // 总GC次数
    "gc_stw_time_ms": 12.5,       // 总GC暂停时长（毫秒）
    "max_stw_time_ms": 3.2,        // 最大单次GC暂停时长（毫秒）
    "max_heap_mb": 4096,          // 最大堆使用大小（MB）
    "gc_type_breakdown": {         // GC类型细分统计
        "Young GC": {
            "count": 3,           // 该类型GC的次数
            "stw_time_ms": 8.5    // 该类型GC的总暂停时间
        },
        "Full GC": {
            "count": 2,
            "stw_time_ms": 4.0
        }
    }
}
```

## 文件命名规则

GC日志文件应按照以下格式命名：
- `jdk11-G1GC.log` - JDK 11的G1GC日志
- `jdk17-ParallelGC.log` - JDK 17的ParallelGC日志
- `jdk25-ZGC.log` - JDK 25的ZGC日志

系统会自动从文件名中识别GC类型并选择相应的解析器。

## 测试

### 运行所有测试

```bash
# 运行完整测试套件
python3 src/GCLogParser/test_parsers.py

# 运行单元测试
python3 src/GCLogParser/test_all_parsers.py
```

### 运行示例

```bash
# 运行示例分析
python3 src/GCLogParser/example_usage.py
```

## 解析器架构

### 基类 (BaseGCParser)

所有解析器的基类，提供：
- 基础数据结构
- 工具方法（堆大小提取、时间提取等）
- 结果格式化

### 具体解析器

每个GC类型都有对应的专门解析器：
- `SerialGCParser` - 解析Serial GC日志
- `ParallelGCParser` - 解析Parallel GC日志
- `G1GCParser` - 解析G1GC日志
- `ZGCParser` - 解析ZGC日志
- `ShenandoahGCParser` - 解析ShenandoahGC日志
- `EpsilonGCParser` - 解析EpsilonGC日志

## 扩展新的GC类型

要添加新的GC类型解析器：

1. 继承`BaseGCParser`类
2. 实现`get_gc_type()`和`parse_log_line()`方法
3. 在`GCLogAnalyzer`中注册新的解析器
4. 添加相应的测试用例

示例：

```python
from .base_parser import BaseGCParser

class NewGCParser(BaseGCParser):
    def get_gc_type(self):
        return "NewGC"
    
    def parse_log_line(self, line: str) -> bool:
        # 实现具体的日志解析逻辑
        if "NewGC Pattern" in line:
            # 解析GC事件
            self.update_gc_stats("New GC Event", stw_time, heap_before, heap_after)
            return True
        return False
```

## 日志格式支持

解析器支持以下常见的GC日志格式：

### GC事件格式
```
GC(0) Pause Young (Allocation Failure) 69M->1M(247M) 0.498ms
GC(1) Pause Full 100M->80M(500M) 2.5ms
```

### 堆信息格式
```
Heap Max Capacity: 4G
ZHeap used 28M, capacity 256M, max capacity 4096M
```

### 时间格式
- 毫秒(ms): `0.498ms`
- 秒(s): `1.5s`
- 微秒(us): `500us`
- 纳秒(ns): `1000000ns`

## 性能特性

- 内存效率：逐行解析，不将整个日志文件加载到内存
- 时间复杂度：O(n)，其中n是日志行数
- 可扩展性：支持大型GC日志文件（GB级别）

## 故障排除

### 常见问题

1. **无法识别GC类型**
   - 检查文件名是否包含正确的GC类型标识符
   - 确认文件名格式为`jdk{version}-{GCType}.log`

2. **解析结果为空**
   - 确认GC日志文件格式正确
   - 检查文件编码是否为UTF-8

3. **堆大小为0**
   - 某些GC类型（如ZGC）可能没有明显的GC事件
   - 检查初始化日志中的堆信息

### 调试模式

启用详细日志输出：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

analyzer = GCLogAnalyzer()
result = analyzer.parse_gc_log("gc.log")
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 添加测试用例
4. 确保所有测试通过
5. 提交Pull Request

## 许可证

本项目采用MIT许可证。
