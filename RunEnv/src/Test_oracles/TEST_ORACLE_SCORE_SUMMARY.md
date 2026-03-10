# 测试预言Score字段说明

## 概述

所有支持异常程度量化的测试预言都已添加了`score`字段，用于表示异常的严重程度。score值越大，表示异常越严重。

## 各测试预言的Score计算方式

### 1. gc_count_anomaly (GC次数异常)

**Score计算**: `score = excess_ratio_threshold = (gc_count - threshold) / threshold`

**含义**: 超出阈值的比例，表示GC次数比预期高出多少倍

**示例**: 
- score = 1.0 表示GC次数超出阈值100%
- score = 2.0 表示GC次数超出阈值200%

### 2. stw_anomaly (STW时间异常)

有三种异常类型，每种有不同的score计算方式：

#### 2.1 绝对阈值异常
**Score计算**: `score = (stw_time - threshold) / threshold`

**含义**: 超出阈值的比例

#### 2.2 JDK内GC对比异常
**Score计算**: `score = slower_gc_stw / faster_gc_stw`

**含义**: 慢GC相对于快GC的倍数

#### 2.3 跨版本对比异常
**Score计算**: `score = stw_increase_ratio = (new_stw - old_stw) / old_stw`

**含义**: 新版本相对于旧版本的STW增加比例

### 3. performance_anomaly (性能异常)

有两种异常类型：

#### 3.1 慢测试异常
**Score计算**: `score = duration / threshold`

**含义**: 超出阈值的倍数

#### 3.2 GC间性能差异异常
**Score计算**: `score = faster_gc_median / slower_gc_median`

**含义**: 快GC相对于慢GC的性能倍数

### 4. performance_regression (性能回归)

**Score计算**: `score = change_ratio = new_version_duration / old_version_duration`

**含义**: 新版本相对于旧版本的性能变化比例
- score > 1.0 表示性能变差
- score值越大，性能下降越严重

### 5. gc_overhead_anomaly (GC开销异常)

有三种异常类型：

#### 5.1 DEBUG超100%异常
**Score计算**: `score = gc_overhead_ratio`

**含义**: GC开销比例本身（超过1.0表示超过100%）

#### 5.2 JDK内开销对比异常
**Score计算**: `score = gc_overhead_ratio / median_ratio`

**含义**: 相对于同JDK内GC开销中位数的倍数

#### 5.3 跨版本开销回归异常
**Score计算**: `score = overhead_increase_ratio = (new_overhead - old_overhead) / old_overhead`

**含义**: 新版本相对于旧版本的GC开销增加比例

### 6. missing_required_fields (必需字段缺失)
**Status**: 不需要score字段

**原因**: 布尔检测，只有字段存在/不存在两种状态，没有程度之分

### 7. test_failure (测试失败)
**Status**: 不需要score字段

**原因**: 布尔检测，只有测试通过/失败两种状态，没有程度之分

## Score值解释

- **score = 0**: 表示没有超出阈值（理论上不会有这种情况，因为只有检测到异常才会返回异常数据）
- **score > 0**: 表示异常的严重程度，数值越大越严重
- **score = 1.0**: 表示超出阈值100%，是一个重要的参考点
- **score > 10.0**: 通常表示非常严重的异常，很可能指示实际问题

## 使用建议

1. **排序和筛选**: 可以按score值对异常进行排序，优先处理score值高的异常
2. **阈值设定**: 可以根据score值设置不同的告警级别
   - score < 1.0: 轻微异常，可关注
   - 1.0 ≤ score < 5.0: 中等异常，需要注意
   - score ≥ 5.0: 严重异常，需要立即关注
3. **趋势分析**: 跟踪同一异常类型的score变化趋势，识别恶化情况

## 注意事项

- 不同测试预言的score计算方式不同，不能直接跨类型比较score值
- score值是相对指标，需要结合具体的异常描述和上下文来理解
- 所有score值都保留4位小数以确保精度
