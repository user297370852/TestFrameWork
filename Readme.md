# Java GC 机制测试框架
一个专门用于 Java 垃圾回收机制测试和兼容性验证的综合性测试框架。

## 📋 项目概述

本项目提供了一套完整的 Java GC 测试解决方案，支持多 JDK 版本、多 GC 算法的差分测试，能够有效发现 GC 相关的兼容性问题和性能异常。

### 核心功能
- **多版本兼容性测试**：支持 JDK 11、17、21、25、26 等多个版本
- **多 GC 算法测试**：覆盖 SerialGC、ParallelGC、G1GC、ZGC、ShenandoahGC 等
- **自动化测试执行**：批量测试、结果过滤、异常检测
- **详细的 GC 日志分析**：提供深度的 GC 性能和兼容性分析

## 🏗️ 项目结构

```
PythonProject/
├── RunEnv/                    # 核心测试环境
│   ├── src/                   # 测试框架源代码
│   │   ├── TestRun.py         # 测试执行器
│   │   ├── Executor.py        # 测试执行引擎
│   │   ├── ResAnalyzer.py     # 结果分析器
│   │   ├── GCLogAnalyzer.py   # GC日志分析器
│   │   └── Test_oracles/      # 测试预言库
│   ├── testcases/             # 测试用例集合
│   │   ├── HotSpot/           # HotSpot 相关测试
│   │   ├── OpenJ9/            # OpenJ9 相关测试
│   │   ├── eclipse/           # Eclipse 框架测试
│   │   ├── fop/               # FOP 框架测试
│   │   └── ...
│   └── GCObj.class            # GC 测试辅助类
├── src/                       # 辅助工具集
│   ├── SeedBuild/              # 种子程序构建工具
│   │   ├── java_to_seeds.py    # Java项目转种子程序集
│   │   └── sampleSeed/        # 示例种子程序
│   └── tools/                  # 代码处理工具
│       ├── LLMWriter.py        # AI 代码修复工具
│       ├── ToJava.py           # 字节码转换工具
│       ├── classdown.py        # 字节码版本降级工具
│       └── sootTest.py         # Soot 测试工具
├── lib/                        # 依赖库
│   ├── soot-4.1.0.jar         # Soot 字节码分析框架
│   ├── fernflower.jar         # Java 反编译器
│   ├── asm-*.jar              # ASM 字节码操作框架
│   └── ...                    # 其他依赖库
├── benchmarks/                 # 基准测试项目
│   ├── eclipse-dacapo/         # Eclipse DACapo 基准
│   └── fop-dacapo/            # FOP DACapo 基准
└── results/                    # 测试结果存储（本地）
```

---

## ⚙️ 环境依赖

### 必需软件
- **Python 3.6+**
- **jenv** - Java 版本管理工具
- **多版本 JDK** - 需要在 jenv 中配置以下版本

### JDK 版本要求
```bash
# 确保以下 JDK 版本已在 jenv 中安装并配置
jenv versions
* 1.8                    # Java 8（编译环境）
  11                     # Java 11（测试环境）
  17                     # Java 17（测试环境）
  21                     # Java 21（测试环境）
  25                     # Java 25（测试环境）
  26                     # Java 26（测试环境）
```

### 安装 jenv 并配置 JDK
```bash
# 安装 jenv（macOS）
brew install jenv

# 添加 JDK 到 jenv
jenv add /usr/libexec/java_home -v 11
jenv add /usr/libexec/java_home -v 17
jenv add /usr/libexec/java_home -v 21
jenv add /usr/libexec/java_home -v 25
jenv add /usr/libexec/java_home -v 26

# 设置全局 Java 版本
jenv global 1.8
```

---

## 🚀 快速开始

### 1. 环境检查
```bash
# 检查 Python 版本
python --version

# 检查 jenv 配置
jenv versions

# 检查必需的 JDK 版本
jenv local 1.8
java -version
```

### 2. 运行基础测试
```bash
cd RunEnv/src

# 测试单个目录的 .class 文件
python TestRun.py ../testcases/HotSpot

# 测试并过滤成功的测试用例
python TestRun.py ../testcases/HotSpot -f ./successful_tests

# 分析测试结果
python ResAnalyzer.py ./successful_tests
```

### 3. 使用辅助工具
```bash
# 构建 Java 项目为种子程序集
cd src/SeedBuild
python java_to_seeds.py /path/to/java/project ./output_seeds

# 修复混乱的 Java 代码
cd ../tools
python LLMWriter.py ./broken_code --output ./fixed_code

# 降级字节码版本
python classdown.py
```

---

## 📁 核心模块说明

### RunEnv/ - 测试框架核心
**主要功能**：Java GC 测试的执行、分析和报告生成

- **TestRun.py**: 测试执行器，支持多 JDK 版本和 GC 算法的差分测试
- **Executor.py**: 测试执行引擎，负责具体的类文件运行和日志收集
- **ResAnalyzer.py**: 结果分析器，基于测试预言自动检测异常模式
- **GCLogAnalyzer.py**: GC 日志分析器，提供深度的 GC 性能分析
- **Test_oracles/**: 测试预言库，包含各种异常检测规则

**支持的测试类型**：
- 基础可运行性测试
- JDK 版本兼容性测试
- GC 算法兼容性测试
- 性能回归测试
- 内存泄漏检测

### src/ - 辅助工具集
**主要功能**：为测试框架提供各种代码处理和转换能力

- **SeedBuild/**: 种子程序构建工具，将 Java 项目转换为标准测试用例
- **tools/**: 代码处理工具集，包含反编译、版本降级、AI 修复等功能

**工具链支持**：
- Java 源码 → 种子程序集转换
- 字节码 → Java 源码反编译
- 高版本字节码 → Java 8 兼容性降级
- 混乱代码 → 可编译代码的 AI 修复

### lib/ - 依赖库
**包含的核心库**：
- Soot: 字节码分析和转换框架
- Fernflower: Java 反编译器
- ASM: 字节码操作和分析框架
- SLF4J + Guava: 基础运行时依赖

### benchmarks/ - 基准测试
**用途**：提供真实世界的 Java 应用作为测试基准
- **eclipse-dacapo**: Eclipse IDE 相关的基准测试
- **fop-dacapo**: Apache FOP（XSL-FO 处理器）基准测试

---

## 🔧 支持的 JDK 版本和 GC 组合

| JDK 版本 | 支持的 GC 算法 |
|---------|----------------|
| **JDK 11** | SerialGC, ParallelGC, G1GC, ShenandoahGC, EpsilonGC |
| **JDK 17** | SerialGC, ParallelGC, G1GC, ZGC, ShenandoahGC, EpsilonGC |
| **JDK 21** | SerialGC, ParallelGC, G1GC, ZGC, ShenandoahGC, EpsilonGC |
| **JDK 25** | SerialGC, ParallelGC, G1GC, ZGC, ShenandoahGC, ShenandoahGC-Gen, EpsilonGC |
| **JDK 26** | SerialGC, ParallelGC, G1GC, ZGC, EpsilonGC |

---

## 📊 测试流程

### 1. 测试用例准备
```bash
# 使用现有的测试用例
ls RunEnv/testcases/

# 或构建新的种子程序集
cd src/SeedBuild
python java_to_seeds.py ./java_sources ./new_testcases
```

### 2. 执行差分测试
```bash
cd RunEnv/src

# 基础测试
python TestRun.py ../testcases/HotSpot ./test_logs

# 带 GC 日志的详细测试
python TestRun.py ../testcases/HotSpot ./gc_analysis_logs --keep-gc-logs -t 120
```

### 3. 结果分析
```bash
# 自动异常检测
python ResAnalyzer.py ./test_logs -o anomaly_report.json

# 查看 GC 性能数据
python GCLogAnalyzer.py ./gc_analysis_logs
```

### 4. 报告生成
测试完成后会生成以下报告文件：
- `class_test_report.json`: 基础测试结果
- `anomaly_report.json`: 异常检测结果
- `gc_performance_*.json`: GC 性能分析报告

---

## 📖 详细文档

- **[RunEnv 使用说明](RunEnv/src/Readme.md)** - 测试框架详细使用指南
- **[辅助工具说明](src/Readme.md)** - 代码处理工具集合文档
- **[种子程序构建规约](src/SeedBuild/种子程序构建规约说明.md)** - 种子程序构建标准

---

## 🎯 使用场景

### 1. JDK 升级验证
在升级 JDK 版本前，使用本框架验证现有应用在新版本下的兼容性：
```bash
python TestRun.py ./production_classes ./upgrade_test_logs
python ResAnalyzer.py ./upgrade_test_logs
```

### 2. GC 算法选择
为特定应用选择最优的 GC 算法：
```bash
python TestRun.py ./app_classes ./gc_comparison_logs --keep-gc-logs
python GCLogAnalyzer.py ./gc_comparison_logs
```

### 3. 性能回归检测
定期运行测试以检测性能回归：
```bash
python TestRun.py ./regression_tests ./nightly_logs
python ResAnalyzer.py ./nightly_logs -o performance_regression.json
```

### 4. 框架兼容性测试
测试特定框架在不同 JDK 和 GC 组合下的行为：
```bash
python TestRun.py ./benchmarks/eclipse-dacapo ./eclipse_compatibility
```

---

## ⚠️ 注意事项

1. **JDK 版本管理**: 确保所有测试所需的 JDK 版本都已正确安装到 jenv 中
2. **内存配置**: 测试大量用例时注意调整 JVM 内存设置
3. **超时设置**: 根据测试用例的复杂程度合理设置超时时间
4. **依赖管理**: 某些测试用例可能需要额外的依赖库（如 Eclipse、FOP）
5. **权限设置**: 确保工具有足够的权限访问相关目录和文件

---

## 🐛 问题排查

### 常见问题
1. **JDK 版本缺失**: 使用 `jenv doctor` 检查并安装缺失的 JDK 版本
2. **依赖库缺失**: 检查 `lib/` 目录是否包含所有必需的 JAR 文件
3. **权限问题**: 使用 `chmod +x` 为脚本文件添加执行权限
4. **内存不足**: 增加 JVM 堆内存设置或分批处理测试用例

### 日志查看
```bash
# 查看详细的测试执行日志
tail -f TestRun.py.log

# 查看 GC 日志
ls -la ./gc_logs/*.log
```

---

## 🤝 贡献指南

1. Fork 项目仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

---

**维护者**: Liu  
**最后更新**: 2025年12月  
**版本**: 1.0  
**项目主页**: [https://github.com/user297370852/TestFrameWork/tree/main]
