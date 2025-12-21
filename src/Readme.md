# src 目录辅助工具说明
本目录包含用于 GC Fuzz 项目的各种辅助工具，主要用于 Java 字节码处理、代码转换和种子程序构建。

## 目录结构

```
src/
├── SeedBuild/          # 种子程序构建工具
│   ├── java_to_seeds.py
│   ├── sampleSeed/     # 示例种子程序
│   └── 种子程序构建规约说明.md
├── tools/              # 代码处理工具
│   ├── LLMWriter.py    # AI 代码修复工具
│   ├── ToJava.py       # 字节码转换工具
│   ├── classdown.py    # 字节码版本降级工具
│   └── sootTest.py     # Soot 测试工具
└── Output/             # 工具输出示例
```

---

## 🛠️ 工具详细说明

### 1. SeedBuild/java_to_seeds.py
**用途**: 将 Java 项目转换为符合种子程序构建规约的种子程序集

**主要功能**:
- 自动扫描 Java 源代码文件
- 筛选包含 main 方法的可执行类
- 使用 JDK 1.8 编译生成 class 文件
- 按包名组织目录结构
- 生成 testcases.txt 和 skipclass.txt 配置文件

**使用方式**:
```bash
python java_to_seeds.py <Java源码目录> <输出目录> [--name 种子集名称]
```

**示例**:
```bash
# 基本用法
python java_to_seeds.py ./src/main/java ./output --name myseeds

# 转换项目到种子程序集
python java_to_seeds.py /path/to/java/project /path/to/output --name seeds
```

**环境要求**:
- 需要安装 jenv 并配置 Java 8
- 所有 Java 文件必须包含 main 方法

---

### 2. tools/LLMWriter.py
**用途**: 使用 AI 模型修复和整理混乱的 Java 代码

**主要功能**:
- 调用 DeepSeek API 进行代码修复
- 将残缺、混乱的中间代码转换为可编译的 Java 文件
- 自动添加必要的 import 语句
- 处理外部依赖（如 GCObj 类的 mock 实现）
- 批量处理多个 Java 文件

**使用方式**:
```bash
python LLMWriter.py <输入目录> [--output 输出目录]
```

**示例**:
```bash
# 处理目录中的所有 Java 文件
python LLMWriter.py ./dataset --output ./fixed_code

# 默认输出到 Output 目录
python LLMWriter.py ./broken_java_files
```

**注意事项**:
- 需要配置有效的 API 密钥
- 工具会自动添加 1 秒延迟避免 API 速率限制
- 支持处理包含语法错误的残缺代码

---

### 3. tools/ToJava.py
**用途**: 将字节码文件转换为 Java 源代码

**主要功能**:
- 使用 Fernflower 反编译 .class 文件
- 手动转换 .jimple 文件为 Java 代码
- 支持复杂的字节码结构转换
- 处理方法调用、类型转换等复杂语法

**使用方式**:
```bash
python ToJava.py <输入目录> [--output 输出目录]
```

**示例**:
```bash
# 转换目录中的所有 .class 和 .jimple 文件
python ToJava.py ./bytecode_files --output ./java_sources

# 默认输出到 Output 目录
python ToJava.py ./compiled_classes
```

**支持的输入格式**:
- `.class` 文件（使用 Fernflower 反编译）
- `.jimple` 文件（手动转换）

---

### 4. tools/classdown.py
**用途**: 降级 Java 字节码版本以确保兼容性

**主要功能**:
- 检测 .class 文件的字节码版本
- 将高版本字节码降级到 Java 8 兼容版本（版本号 52）
- 批量处理目录中的所有 class 文件
- 提供详细的版本统计信息

**使用方式**:
```bash
# 直接运行，使用内置路径配置
python classdown.py
```

**功能特性**:
- 自动识别字节码版本（Java 4-8+）
- 安全的版本降级操作
- 详细的处理结果报告
- 版本兼容性检查

**版本映射**:
- 52: Java 8
- 51: Java 7  
- 50: Java 6
- 49: Java 5
- 48: Java 4

---

### 5. tools/sootTest.py
**用途**: 测试 Soot 框架的基本功能和反编译能力

**主要功能**:
- 测试 Soot 基本功能是否正常
- 验证 Soot 能否正确处理简单的 Java 类
- 测试 .class 文件到 .java 文件的转换
- 依赖管理和 classpath 配置

**使用方式**:
```bash
# 直接运行测试
python sootTest.py
```

**测试内容**:
1. **基本功能测试**: 验证 Soot 能否正常启动
2. **转换测试**: 创建简单 Java 类，编译后用 Soot 反编译

**依赖项**:
- soot-4.1.0.jar
- 相关依赖库（SLF4J, Guava, ASM 等）
- Java 8 运行环境

---

## 📁 输出文件说明

### Output 目录
包含工具运行的示例输出：
- `1.java`, `2.java` 等：由 LLMWriter 或 ToJava 生成的 Java 文件

### sampleSeed 目录
包含符合构建规约的示例种子程序：
- `out/production/sampleSeed/`: 编译后的 class 文件
- `testcases.txt`: 可执行测试用例列表
- `skipclass.txt`: 跳过的类文件列表

---

## 🚀 快速开始

### 1. 构建种子程序集
```bash
cd src/SeedBuild
python java_to_seeds.py /path/to/java/src /path/to/output
```

### 2. 修复混乱代码
```bash
cd src/tools
python LLMWriter.py ./broken_code --output ./fixed_code
```

### 3. 转换字节码
```bash
cd src/tools
python ToJava.py ./class_files --output ./java_files
```

### 4. 确保版本兼容
```bash
cd src/tools
python classdown.py
```

---

## ⚙️ 环境配置

### 必需依赖
- **Python 3.6+**
- **Java 8 (JDK 1.8)**
- **jenv**（用于 Java 版本管理）

### Python 包依赖
```bash
pip install openai httpx pathlib argparse
```

### Java 工具链
- 确保 Java 8 在 PATH 中
- 配置正确的 JAVA_HOME
- 安装 jenv 并添加 Java 8 支持

---

## 📝 注意事项

1. **路径配置**: 确保所有工具中的路径配置正确指向项目 lib 目录
2. **版本一致性**: 所有 Java 代码应使用 JDK 1.8 编译以确保兼容性
3. **API 配置**: LLMWriter 需要有效的 API 密钥才能正常工作
4. **权限问题**: 确保工具有足够的读写权限访问相关目录
5. **内存使用**: 处理大型代码库时注意内存使用情况

---

## 🔗 相关文档

- [种子程序构建规约说明](SeedBuild/种子程序构建规约说明.md)
- [Soot 官方文档](https://github.com/Sable/soot)
- [Fernflower 反编译器](https://github.com/fesh0r/fernflower)

---

**维护者**: Liu  
**最后更新**: 2025年12月  
**版本**: 1.0
