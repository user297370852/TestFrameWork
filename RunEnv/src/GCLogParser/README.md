# GC日志解析器
这是一个用于解析Java GC日志的Python工具库，支持多种GC类型的日志解析，包括Serial GC、Parallel GC、G1GC、ZGC、ShenandoahGC和EpsilonGC。

## 功能特性

- 支持多种GC类型的日志解析
- 提取GC性能指标（唯一GC ID数量、STW暂停时间、最大实际堆占用等）
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
    "total_gc_count": 5,           // 当前日志范围内唯一GC(id)数量
    "gc_stw_time_ms": 12.5,       // GC导致的STW暂停总时长（毫秒）
    "max_stw_time_ms": 3.2,        // 最大单个连续GC暂停子事件时长（毫秒）
    "max_heap_mb": 151,           // 最大实际堆占用（MB），不等于-Xmx或堆容量
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

字段语义说明：

- `total_gc_count` 统计当前日志文件中出现过的唯一 `GC(id)` 数量。例如日志中最大编号是 `GC(101)` 时，只有在 `GC(0)` 到 `GC(101)` 都出现在当前日志范围内时，该值才是 `102`；解析器实际使用唯一 ID 集合计数，而不是直接使用最大 ID。
- `gc_stw_time_ms` 统计 GC 导致的 STW 暂停总时长。Serial GC 中外层 Young GC 内部触发 Full GC 时，内部嵌套暂停不会重复累加到总暂停时间。
- `max_stw_time_ms` 表示最长的单个连续 GC 暂停子事件，不表示单个 `GC(id)` 周期内多个 pause 子事件的总和。
- `max_heap_mb` 表示日志中可观察到的最大实际 Java heap used，占用来源包括 `before->after(capacity)` 中的 before/after used、`Used` 高水位或 `Heap: ... used`。括号中的 capacity、`committed`、`reserved`、`Max Capacity`、`Heap Max Capacity` 和 JVM `-Xmx` 都不计入该字段。
- `EpsilonGC` 不执行垃圾回收，`total_gc_count`、`gc_stw_time_ms`、`max_stw_time_ms` 固定为 0；日志中的非 GC safepoint/pause 不计入 GC 指标。
- `gc_type_breakdown` 是解析器识别到的 GC/暂停子类型明细。对 ZGC 和 ShenandoahGC，明细可能按 pause 子事件类型统计，因此各子项 `count` 之和不保证等于 `total_gc_count`。

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
Heap: 4096M reserved, 3968M committed, 3950M used
```

用于 `max_heap_mb` 的是实际 `used` 值，例如 `69M->1M(247M)` 中的 `69M` 和 `1M`，以及 `Heap: ... 3950M used` 中的 `3950M`。`247M`、`3968M committed`、`4096M reserved` 和 `Heap Max Capacity: 4G` 只表示容量或保留空间，不作为最大堆占用。

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
