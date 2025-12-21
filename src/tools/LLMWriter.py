import os
import tempfile
import shutil
import argparse
import re
from openai import OpenAI  # 导入新版本客户端类
from openai import APIError, Timeout  # 导入可能需要的异常类
import time
import httpx

# OpenAI API配置
API_KEY = "******"  # 请替换为您的API密钥


def init_output_dir(output_root):
    """初始化输出目录，若存在则清空"""
    if os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root, exist_ok=True)


def get_relative_path(input_path, input_root):
    """获取文件相对于输入根目录的路径"""
    return os.path.relpath(os.path.dirname(input_path), input_root)


def create_output_dir(output_root, relative_path):
    """在输出目录中创建与输入相对应的目录结构"""
    output_dir = os.path.join(output_root, relative_path)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def extract_java_code(response_content):
    """
    从响应文本中提取Java代码，增强对非标准格式的处理
    """
    if not response_content:
        return None

    # 1. 预处理：移除可能的干扰标记（如示例中的「」）
    cleaned_content = re.sub(r"", "", response_content, flags=re.DOTALL)

    # 2. 多模式匹配代码块：
    # 模式1：标准代码块（```java ... ``` 或 ``` ... ```）
    code_block_pattern = r"```(?:java|java\s*)\n(.*?)\n```"
    matches = re.findall(code_block_pattern, cleaned_content, re.DOTALL)

    if matches:
        # 取第一个匹配的代码块，去除前后空白
        return matches[0].strip()

    # 模式2：如果没有标准代码块，尝试匹配「import java」开头的代码段
    # （适用于模型直接输出代码，未加包裹的情况）
    java_code_pattern = r"(import\s+java\..*?)(?=\n\n|$)"
    matches = re.findall(java_code_pattern, cleaned_content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # 模式3：最后尝试提取所有可能的Java类定义（兜底方案）
    class_pattern = r"(public\s+class\s+\w+.*?)(?=\n\n|$)"
    matches = re.findall(class_pattern, cleaned_content, re.DOTALL)
    if matches:
        return matches[0].strip()

    # 所有模式都匹配失败，返回None（避免写入非代码内容）
    print("⚠️ 未提取到有效Java代码")
    return None


def call_openai_api(java_code):
    """
    调用OpenAI API转换Java代码
    返回转换后的Java代码字符串
    """
    system_prompt = """# 目标——原始Java代码重新整理成可编译的Java代码

## 任务描述
中间代码转换，你需要将提供的乱码、中间代码风格甚至是残缺的Java代码转换为**逻辑完全一致**、**可直接编译运行**的单个Java文件。

## 核心要求

### 🎯 必须保证
1. **逻辑完全不变** - 执行流程、业务逻辑必须与原始代码一致，仅在原始代码因残缺等原因下自行完善
2. **单个文件输出** - 所有类都写在一个.java文件中
3. **直接可编译运行** - 无需额外配置即可编译执行
4. **保留原始测试意图** - 保持原有的测试场景和验证逻辑,尤其是各种变量赋值、对象创建

### 🔧 技术规范
1. **自动添加import语句** - 根据代码内容智能添加所需import,修复那些错误的import，去掉可能是外部依赖的import
2. **处理外部依赖**：
   - 一般外部调用：使用mock思想直接返回合理值
   - **GCObj类**：必须使用以下实现（如用到）：
     ```java
     import java.lang.ref.PhantomReference;
     import java.lang.ref.ReferenceQueue;
     import java.lang.ref.SoftReference;
     import java.lang.ref.WeakReference;

     public class GCObj {
         public GCObj strongReference = null;
         public SoftReference<GCObj> softReference = null;
         public WeakReference<GCObj> weakReference = null;
         public PhantomReference<GCObj> phantomReference = null;
         public byte[] space = null;

         public GCObj(GCObj strongReference, GCObj softReference, GCObj weakReference, GCObj phantomReference, int size) {
             this.strongReference = strongReference;
             this.softReference = new SoftReference<>(softReference);
             this.weakReference = new WeakReference<>(weakReference);
             ReferenceQueue<GCObj> referenceQueue = new ReferenceQueue<>();
             this.phantomReference = new PhantomReference<>(phantomReference, referenceQueue);
             this.space = new byte[size];
         }
     }
     ```
3. **修正语法错误** - 修复所有编译错误
4. **保留代码结构** - 对无意义的中间变量和复杂结构，在不会造成语法错误的情况下保留

### 📝 输出格式
只输出完整的Java代码，不要任何解释或注释。代码必须能够直接编译运行，原始代码大量残缺、无法理解等极端情况下为保证正确性可丢失部分原代码信息"""

    client = OpenAI(
        base_url="https://svip.xty.app/v1",
        api_key="******",
        http_client=httpx.Client(
            base_url="https://svip.xty.app/v1",
            follow_redirects=True,
        ),
    )

    try:
        # 调用API（新版本方法为client.chat.completions.create）
        response = client.chat.completions.create(
            model="deepseek-v3.2-exp",  # 模型名称（确认接口支持该模型）
            messages=[
                {"role": "system", "content": "你是一个负责转换中间代码的工具"},
                {"role": "user", "content": f"{system_prompt}\n"
                                            f"请依据要求转换以下代码，必须返回完整重构后的Java代码，并用```java和```包裹，不要包含任何解释、说明或其他文本。：\n```java\n{java_code}\n```"}
            ],
            temperature=0.1,  # 低温度保证稳定性
            max_tokens=8000,  # 根据代码长度调整
            timeout=120  # 超时时间（秒）
        )

        # 提取原始响应内容
        raw_content = response.choices[0].message.content.strip()

        # 使用优化后的提取函数
        converted_code = extract_java_code(raw_content)

        return converted_code if converted_code else None


    except Exception as e:
        print(f"❌ API调用异常: {e}")
        return None


def save_and_verify_java_code(code, temp_dir, original_filename):
    """
    保存Java代码并验证基本语法
    返回保存的文件路径，如果验证失败返回None
    """
    if not code:
        return None

    # 生成输出文件名
    output_filename = os.path.splitext(original_filename)[0] + "_converted.java"
    output_path = os.path.join(temp_dir, output_filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)

        # 基本语法验证：检查是否有明显的语法问题
        if "class " not in code:
            print(f"⚠️  警告：转换后的代码可能缺少类定义")

        return output_path

    except Exception as e:
        print(f"❌ 保存文件失败: {e}")
        return None


def process_java_file(file_path, temp_dir, original_filename):
    """处理单个Java文件转换"""
    try:
        # 读取原始Java代码
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            original_code = f.read()

        print(f"🔧 正在处理: {file_path}")

        # 调用OpenAI API进行转换
        converted_code = call_openai_api(original_code)

        if not converted_code:
            print(f"❌ 转换失败: {file_path}")
            return None

        # 保存并验证转换后的代码
        output_path = save_and_verify_java_code(converted_code, temp_dir, original_filename)

        if output_path:
            print(f"✅ 转换完成: {file_path}")
            return output_path
        else:
            print(f"❌ 保存验证失败: {file_path}")
            return None

    except Exception as e:
        print(f"❌ 处理文件时出错 {file_path}: {e}")
        return None


def process_file(file_path, input_root, output_root, counter):
    """处理单个文件（.java），返回是否成功"""
    # 获取相对路径，创建输出目录
    relative_path = get_relative_path(file_path, input_root)
    output_dir = create_output_dir(output_root, relative_path)

    # 创建临时目录用于转换
    with tempfile.TemporaryDirectory() as temp_dir:
        java_path = None

        if file_path.endswith(".java"):
            # 处理Java文件转换
            original_filename = os.path.basename(file_path)
            java_path = process_java_file(file_path, temp_dir, original_filename)
        else:
            return False  # 非目标文件

        if not java_path:
            return False

        # 重命名为序号.java并移动到输出目录
        output_java = os.path.join(output_dir, f"{counter[0]}.java")
        shutil.copy2(java_path, output_java)
        print(f"✅ 转换成功：{file_path} → {output_java}")
        counter[0] += 1
        return True


def traverse_directory(current_dir, input_root, output_root, counter):
    """递归遍历目录，处理所有文件"""
    # 列出目录下的所有条目
    entries = [os.path.join(current_dir, e) for e in os.listdir(current_dir)]

    # 区分"目录下全是子目录"还是"全是文件"
    if any(os.path.isdir(e) for e in entries):
        # 全是子目录，递归处理
        for subdir in entries:
            if os.path.isdir(subdir):
                traverse_directory(subdir, input_root, output_root, counter)
    else:
        # 全是文件，筛选并处理目标文件
        for file_path in entries:
            if file_path.endswith(".java"):
                success = process_file(file_path, input_root, output_root, counter)
                if success:
                    # 添加延迟以避免API速率限制
                    time.sleep(1)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="批量转换混乱Java代码为可执行Java文件")
    parser.add_argument("input_dir", help="输入数据集根目录")
    parser.add_argument("--output", default="Output", help="输出目录（默认：Output）")
    args = parser.parse_args()



    input_root = os.path.abspath(args.input_dir)
    output_root = os.path.abspath(args.output)

    # 初始化
    init_output_dir(output_root)
    counter = [1]  # 用列表实现全局自增（避免nonlocal问题）

    # 开始遍历处理
    print(f"开始处理目录：{input_root}")
    traverse_directory(input_root, input_root, output_root, counter)
    print(f"处理完成，共生成{counter[0] - 1}个.java文件，输出目录：{output_root}")


if __name__ == "__main__":
    main()