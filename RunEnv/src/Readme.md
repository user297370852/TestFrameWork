
# 说明
自动包名解析：
```根据目录名自动推断包结构，需要符合下面规约：
若目录下有子目录，则该目录下全为子目录
若目录下有文件，则该目录下全为文件
我们只考虑.class文件的运行，可以保证：
.class所在的目录名=包名+'.'+类名
例如目录Bug_triggering_input.Compiler_triggering_input.JDK_4343763.Test2
下有文件Bug_triggering_input.Compiler_triggering_input.JDK_4343763.Test2_0101@1761295864593.class，
则该class的包名为Bug_triggering_input.Compiler_triggering_input.JDK_4343763，主类名为Test2。
注意包名不是一定存在的，例如目录ACCModule52下有文件ACCModule52_xxx.class，
此时说明该class源代码并没有package语句，主类是ACCModule52
```
临时目录：使用临时目录运行，不修改原文件

超时控制：防止卡死的测试用例,在TestRun.py的main函数设置超时值

详细报告：生成成功/失败统计和详细错误信息

递归扫描：自动扫描所有子目录中的.class文件，**注意GCObj默认是该项目目录下**

错误处理：妥善处理各种异常情况

输出示例
text
Testing: Testcases/classHistory/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501-origin.class
  ✓ SUCCESS: Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501
Testing: Testcases/classHistory/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501/Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501_0101@1761296994580.class
  ✓ SUCCESS: Bug_triggering_input.Compiler_triggering_input.JDK_4311383.stmt06501

============================================================
TEST REPORT
============================================================
Total class files tested: 156
Successful: 142
Failed: 14
Success rate: 91.03%

# 依赖类路径说明
在TestRun.py的run_java_class函数中构建执行命令，完成类路径的添加，由于测试用例基于GCFuzz，
因此默认添加了GCObj.class的路径，此外，例如针对eclipse框架下的eclipsestarter类测试，需要添加eclipse的相关依赖，
请自行下载该benchmark并添加相关依赖，fop同理（GCFuzz的02Benchmark中已经有搭建好的eclipse和fop框架，
建议引用这里的依赖类）

# 测试执行/过滤器TestRun.py说明

## 概述
TestRun.py 是一个用于测试 Java 类文件可运行性并过滤成功测试用例的工具。它可以扫描指定目录中的所有 .class 文件，测试它们是否能正常运行，并将成功的测试用例复制到指定目录。

功能特性
批量测试：自动扫描目录及其子目录中的所有 .class 文件

即时过滤：在测试过程中立即将成功的文件复制到输出目录

详细报告：生成 JSON 格式的测试报告，包含每个文件的测试结果

进度跟踪：实时显示测试进度和统计信息

## 基本用法
1. 仅测试模式（不复制文件）
```bash
python TestRun.py /path/to/testcases
```
这将：

扫描 /path/to/testcases 目录中的所有 .class 文件

测试每个文件的可运行性

生成默认报告文件 class_test_report.json

2. 测试并过滤模式（复制成功文件）
```bash
python TestRun.py /path/to/testcases -f /path/to/output_dir
```
这将：

扫描并测试所有 .class 文件

实时复制成功运行的测试用例到 /path/to/output_dir

保持原始目录结构

生成测试报告

3. 自定义报告文件名
```bash
python TestRun.py /path/to/testcases -f /path/to/output_dir -r custom_report.json
```
4. 仅生成报告（不复制）
```bash
python TestRun.py /path/to/testcases -r detailed_report.json
```
命令行参数详解 

| 参数             | 缩写  | 说明                     | 默认值                    |
|:---------------|:----|:-----------------------|:-----------------------|
| testcases_dir	 | -   | 必需：包含测试用例 .class 文件的目录 | 	无                     |
| --filter       | -f  | 可选：成功测试用例的输出目录         | 	无                     |
| --report       | 	-r | 可选：测试报告输出文件名	          | class_test_report.json |


# Java 类文件差分测试工具 - 使用说明

## 概述

JDK Differential Tester（JDK 差分测试工具）是一个用于对 Java 类文件进行差分测试的工具。它通过比较不同 JDK 版本或环境下的运行结果，帮助检测兼容性问题。

## 功能特性

- **批量差分测试**：自动扫描输入目录中的所有 `.class` 文件
- **多环境比较**：支持在不同 JDK 版本或配置下运行测试
- **日志记录**：详细记录每个测试用例的运行结果和差异
- **超时控制**：可配置的测试超时机制，防止长时间阻塞
- **错误处理**：完善的异常处理和中途恢复机制

## 安装要求

### 系统要求
- Python 3.6+
- Java Runtime Environment (JRE) 或多版本 JDK
- 足够的磁盘空间用于存储日志文件

### 依赖检查
执行依赖jenv提供的jdk版本管理，默认jdk11,17,21,25,26这些版本，请确保jenv中存在这些版本
```bash
% jenv versions
  system
* 1.8 (set by /.jenv/version)
  1.8.0.462
  11
  11.0
  11.0.28
  17
  17.0
  17.0.17
  21
  21.0
  21.0.9
  25
  25.0
  25.0.1
  26
  26-ea
  openjdk64-11.0.28
  openjdk64-17.0.17
  openjdk64-21.0.9
  openjdk64-25.0.1
  openjdk64-26-ea
  temurin64-1.8.0.462
```

## 基本用法

### 1. 基本命令格式
```bash
python TestRun.py <input_dir> <output_dir> [options]
```

### 2. 最简单的使用方式
```bash
python TestRun.py ./testcases ./test_logs
```

### 3. 指定超时时间
```bash
python TestRun.py ./testcases ./test_logs -t 30
```

## 命令行参数详解

| 参数 | 缩写 | 必需 | 说明 | 默认值 |
|------|------|------|------|--------|
| `input_dir` | - | **是** | 包含 `.class` 文件的输入目录路径 | 无 |
| `output_dir` | - | **是** | 保存测试日志文件的输出目录路径 | 无 |
| `--timeout` | `-t` | 否 | 单个测试用例的超时时间（秒） | 60 |

## 目录结构要求

### 输入目录结构示例
```
input_dir/
├── com/
│   └── example/
│       ├── TestClass1.class
│       ├── TestClass2.class
│       └── subpackage/
│           └── TestClass3.class
└── another/
    └── TestClass4.class
```

### 输出目录结构（自动生成）
```
output_dir/
├── logs/
│   ├── com.example.TestClass1.log
│   ├── com.example.TestClass2.log
│   ├── com.example.subpackage.TestClass3.log
│   └── another.TestClass4.log
├── summary.json
└── differential_report.html  # 如果支持HTML报告
```

## 详细使用示例

### 示例 1：基础测试
```bash
# 从项目编译目录获取测试用例
python TestRun.py ./target/classes ./test_results
```

### 示例 2：长超时设置
```bash
# 对于需要长时间运行的测试用例
python TestRun.py ./large_testcases ./long_run_logs -t 300
```

### 示例 3：结合其他工具
```bash
# 先编译源代码
javac -d ./compiled src/*.java

# 运行差分测试
python TestRun.py ./compiled ./diff_test_logs -t 120

# 查看测试结果
ls -la ./diff_test_logs/logs/
```

## 测试过程说明

### 测试流程
1. **扫描阶段**：递归扫描输入目录中的所有 `.class` 文件
2. **测试执行**：对每个类文件在不同环境下执行
3. **结果比较**：比较不同环境下的输出结果
4. **日志记录**：将测试结果和差异保存到输出目录
5. **报告生成**：生成汇总报告和统计信息


# JSON日志分析器LogAnalyzer.py - 使用说明

## 概述

Log Analyzer（日志分析器）是一个专门用于分析差分测试生成JSON日志的工具。它基于预定义的测试预言（Test Oracles）自动检测日志中的异常模式，生成详细的异常报告。

## 功能特性

- **自动扫描**：递归扫描目录中的所有JSON日志文件
- **测试预言驱动**：基于预定义的测试规则检测异常
- **异常分类**：自动对检测到的异常进行分类和统计
- **详细报告**：生成结构化的异常报告，便于后续分析
- **多维度统计**：提供异常的类型分布、影响范围等统计信息

## 基本用法

### 1. 基础命令格式
```bash
python LogAnalyzer.py <input_dir> [options]
```

### 2. 最简单的使用方式
```bash
python LogAnalyzer.py ./test_logs
```

### 3. 指定输出文件
```bash
python LogAnalyzer.py ./test_logs -o custom_report.json
```

## 命令行参数详解

| 参数 | 缩写 | 必需 | 说明 | 默认值 |
|------|------|------|------|--------|
| `input_dir` | - | **是** | 包含JSON日志文件的目录路径 | 无 |
| `--output` | `-o` | 否 | 异常报告输出文件路径 | `anomaly_report.json` |

## 输入文件要求
输入文件是Executor.py的执行结果日志所在的文件夹

## 测试预言说明
测试预言都注册在test_oracles.py中








