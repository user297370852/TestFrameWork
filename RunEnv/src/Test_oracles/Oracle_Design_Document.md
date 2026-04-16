# GC异常检测预言设计文档（V2.1）

## 1. 文档目标

本文档用于替换旧版设计，目标是给出一套可实现、可解释、可复用现有代码结构的 GC 异常检测方案。

本版聚焦两件事：

1. 指标数据应如何建模（不再强依赖单一正态假设）
2. 相对排名如何升级为更鲁棒的多信号检测

---

## 2. 原方案简述与问题总结

### 2.1 原方案思路（简述）

旧方案以「排名基线」为核心：

- 按 `(metric, jdk_version, gc_type)` 统计历史排名均值和方差
- 在线检测时计算 `Z = (rank - mu) / sigma`
- 用固定阈值判断异常，并做多指标聚合

该思路的优点是：

- 比经验阈值更数据驱动
- 对不同 JDK 与 GC 的差异有基础建模

### 2.2 已验证的问题（简述）

实测后确认了 3 个结构性问题：

1. **微小差异放大**：数值很接近时，名次波动会造成误报
2. **极端值弱化**：排名只保序，不体现异常幅度，容易漏掉重尾异常
3. **弱势 GC 盲区**：长期排名靠后的 GC，继续退化也可能不触发

结论：仅用排名 Z-Score 不足以支撑稳定检测。

---

## 3. 新方案总览：V2.1 三通道鲁棒检测

### 3.1 设计原则

1. 保留排名信息，但不再让其主导判定
2. 主判据改为「相对自身历史退化」
3. 对极端值单独建模，增强 bug 检出能力
4. 兼容当前代码与 baseline 文件，支持渐进上线

### 3.2 三通道定义

对单个 testcase `c`、指标 `m`、JDK `v`、GC `g`：

- 原始值：`x(c,m,g)`（当前指标均按“越小越好”处理）
- 组内最优：`x_best(c,m) = min_g x(c,m,g)`
- 组内排名：`r(c,m,g)`

通道 A（主信号）：**自基线退化（Self-Regret）**

\[
regret(c,m,g)=\log\left(\frac{x(c,m,g)+\alpha_m}{x_{best}(c,m)+\alpha_m}\right)
\]

\[
Z_{self}(c,m,g)=\frac{regret-\text{median\_regret}(m,v,g)}{1.4826\cdot\text{mad\_regret}(m,v,g)+\epsilon}
\]

只取退化方向：`Z_self^+ = max(0, Z_self)`。

通道 B（辅助信号）：**排名尾概率（Rank Tail Probability）+ 幅度门控**

不再假设排名正态，而是用历史离散分布：

\[
p_{rank}=P(R\ge r_{obs} \mid m,v,g)
\]

\[
S_{rank}^{raw}=-\log_{10}(p_{rank}+\epsilon)
\]

\[
gate=\min\left(1,\frac{regret}{\tau_m}\right), \quad S_{rank}=S_{rank}^{raw}\cdot gate
\]

通道 C（极端值信号）：**log 尺度鲁棒离群分数**

\[
y(c,m,g)=\log(x(c,m,g)+\alpha_m)
\]

\[
Z_{tail}(c,m,g)=\frac{y-\text{median}_g(y)}{1.4826\cdot MAD_g(y)+\epsilon},\quad Z_{tail}^+=\max(0, Z_{tail})
\]

---

## 4. 综合评分与触发规则

### 4.1 单指标综合分数

\[
S(c,m,g)=w_1\cdot Z_{self}^+ + w_2\cdot S_{rank} + w_3\cdot Z_{tail}^+
\]

推荐默认权重：

- `w1 = 0.60`（主信号）
- `w2 = 0.15`（辅助顺序证据）
- `w3 = 0.25`（极端值增强）

### 4.2 触发规则（单侧，仅退化）

满足任一即告警：

1. `regret > regret_q99`
2. `Z_self > 3.0`
3. `Z_tail > 4.5` 且 `x > lambda_m * x_best`
4. `S_rank > 2.0` 且 `Z_self > 1.5`

### 4.3 严重度分层

- `high`: 满足规则 3，或 `S >= 4.5`
- `medium`: `S >= 3.0` 或 `Z_self > 3.0`
- `low`: `S >= 2.0`

### 4.4 多指标聚合（同一 testcase + gc）

\[
S_{agg}(c,g)=\sum_m \beta_m\cdot S(c,m,g)
\]

推荐 `beta`：

- `gc_stw_time_ms: 1.0`
- `max_stw_time_ms: 1.0`
- `total_gc_count: 0.8`
- `duration_ms: 0.4`（辅助）

---

## 5. 基准模型（Schema v2）

在当前 `gc_ranking_baseline.json` 的基础上扩展，兼容旧字段：

```json
{
  "mu": 3.576,
  "sigma": 1.104,
  "n": 5,
  "rank_hist": {"1": 120, "2": 340, "3": 500, "4": 240, "5": 80},
  "regret_median": 0.213,
  "regret_mad": 0.071,
  "regret_q95": 0.462,
  "regret_q99": 0.701,
  "alpha": 1.0
}
```

### 5.1 兼容策略

1. 若缺少 `rank_hist` 与 `regret_*` 字段：回退到旧版排名 Z-Score 模式
2. 若 `regret_mad == 0`：使用 `max(iqr/1.349, min_scale)`
3. 若某 JDK 样本不足：回退 `overall` 基线并降低置信权重

---

## 6. 参数默认值（可直接实现）

### 6.1 平滑参数 `alpha_m`

- `duration_ms: 1.0`
- `gc_stw_time_ms: 0.1`
- `max_stw_time_ms: 0.01`
- `total_gc_count: 1.0`

### 6.2 排名门控参数 `tau_m`

- `duration_ms: 0.05`
- `gc_stw_time_ms: 0.10`
- `max_stw_time_ms: 0.10`
- `total_gc_count: 0.08`

### 6.3 tail 实际差距阈值 `lambda_m`

- `duration_ms: 1.20`
- `gc_stw_time_ms: 1.50`
- `max_stw_time_ms: 1.50`
- `total_gc_count: 1.30`

---

## 7. 输出与可解释性

每条异常建议输出以下字段（供报告与调试）：

- 基础信息：`metric`, `jdk_version`, `gc_type`, `actual_value`, `actual_rank`
- 通道 A：`regret`, `regret_median`, `regret_q99`, `z_self`
- 通道 B：`rank_tail_prob`, `rank_surprise`, `rank_gate`, `s_rank`
- 通道 C：`z_tail`, `tail_ratio_to_best`
- 综合：`s_metric`, `severity`, `trigger_rules`

建议在报告中使用三段式解释：

1. 相对自身历史：是否超过历史高分位/稳健 z
2. 相对同组排名：本次差排名在历史上多罕见
3. 相对同 testcase：是否属于极端慢值

---

## 8. 参考实现计划（面向现有代码）

以下计划可直接交给 code agent 实施。

### 8.1 目标文件

- `RunEnv/src/Test_oracles/Advanced_oracles/baseline_loader.py`
- `RunEnv/src/Test_oracles/Advanced_oracles/ranking_utils.py`
- `RunEnv/src/Test_oracles/Advanced_oracles/ranking_anomaly.py`
- `RunEnv/src/Test_oracles/Advanced_oracles/gc_ranking_baseline.json`（扩展字段）

### 8.2 阶段 P0：无 schema 变更的最小可用改造

目标：先在现有 baseline 下实现三通道框架，缺失字段时回退。

1. 在 `ranking_utils.py` 新增函数：
   - `calculate_regret(value, best, alpha)`
   - `robust_z(value, median, mad, eps=1e-9)`
   - `calculate_log_tail_score(values_by_gc, alpha)`
   - `calculate_rank_tail_prob_from_hist(rank, rank_hist, smoothing=1.0)`
2. 在 `ranking_anomaly.py`：
   - 重构 `_analyze_metric`，增加三通道分数计算
   - 兼容旧逻辑：无新字段时走现有 Z-Score 分支
   - 返回增强字段（见第 7 节）
3. 保持 `oracle_ranking_anomaly` 接口不变，避免影响调用方。

### 8.3 阶段 P1：baseline schema v2 落地

目标：让通道 A/B 真正使用历史分布。

1. 扩展 `gc_ranking_baseline.json`：新增 `rank_hist`, `regret_*`, `alpha`
2. 在 `baseline_loader.py` 新增读取方法：
   - `get_rank_hist(metric, jdk, gc)`
   - `get_regret_baseline(metric, jdk, gc)`
   - `get_metric_alpha(metric)`
3. 兼容 `overall` 回退逻辑与旧字段读取。

### 8.4 阶段 P2：评估与阈值校准

目标：形成可上线参数集。

1. 离线回放对比 V1/V2.1：
   - 每千用例告警数
   - Top-K 命中率
   - 人工审查通过率
2. 三类专项回归：
   - 微差场景（应降误报）
   - 极端值场景（应增检出）
   - 弱势 GC 场景（应补盲区）
3. 固化默认参数（`w`, `tau`, `lambda`）。

---

## 9. Code Agent 执行清单（可直接照做）

1. 在 `ranking_utils.py` 添加三通道所需工具函数，不改现有函数签名
2. 在 `baseline_loader.py` 增加 v2 字段读取接口，并保留旧接口
3. 在 `ranking_anomaly.py` 增加 `DETECTION_MODE = "hybrid_v2" | "legacy_v1"`
4. 在 `hybrid_v2` 模式中输出 `z_self/s_rank/z_tail/s_metric/trigger_rules`
5. 若 baseline 缺少 v2 字段，自动降级到 legacy 并记录 `analysis_note`
6. 用 `RunEnv/src/Test_oracles/example_result.json` 做一次端到端运行验证
7. 提供一份简短对比报告：V1 与 V2.1 的告警数量与样例差异

---

## 10. 预期收益

1. 误报降低：减少“数值接近但名次波动”的误判
2. 漏报降低：极端慢值更容易被捕获
3. 盲区修复：低基准排名 GC 的自退化可被识别
4. 可解释性提升：每条告警都可拆解为三类证据

本方案是对旧版排名模型的演进，不是推倒重来；可依托现有代码分阶段实施。
