import os
import subprocess
import tempfile
import shutil
import argparse
import re
from pathlib import Path

# 配置转换工具路径（需用户自行修改为实际路径）
FERNFLOWER_JAR = "/Users/yeliu/PycharmProjects/PythonProject/lib/fernflower.jar"  # Fernflower的JAR路径
SOOT_JAR = "/Users/yeliu/PycharmProjects/PythonProject/lib/soot-4.1.0.jar"  # Soot的JAR路径


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


def convert_class_to_java(class_path, temp_dir):
    """用Fernflower将.class文件转为.java文件，返回生成的.java路径"""
    try:
        # 获取GCObj所在的lib目录（与Soot共用同一目录）
        lib_dir = os.path.dirname(SOOT_JAR)  # 假设GCObj.class在该目录下
        class_dir = os.path.dirname(class_path)

        # 调用Fernflower：添加-classpath参数指定依赖目录（包含GCObj.class）
        cmd = [
            "java", "-jar", FERNFLOWER_JAR,
            "-dgs=1",
            "-cp", f"{lib_dir}:{class_dir}",  # 同时包含lib目录和当前class所在目录
            "-log=WARN",
            class_path,
            temp_dir
        ]
        # 后续代码不变...
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ 转换{class_path}失败：{result.stderr}")
            return None

            # 查找生成的.java文件（Fernflower会按包结构生成，取第一个匹配文件）
        java_files = list(Path(temp_dir).rglob("*.java"))
        if not java_files:
            print(f"❌ {class_path}未生成.java文件")
            return None
        return str(java_files[0])
    except Exception as e:
        print(f"❌ 处理{class_path}出错：{str(e)}")
        return None


def convert_jimple_to_java(jimple_path, temp_dir):
    """手动转换Jimple到Java（保持原函数接口）"""
    try:
        # 读取Jimple文件
        with open(jimple_path, 'r', encoding='utf-8') as f:
            jimple_content = f.read()

        # 提取类名

        class_match = re.search(r'public class (\w+)', jimple_content)
        if not class_match:
            class_match = re.search(r'class (\w+)', jimple_path)

        if not class_match:
            print(f"❌ 无法找到类定义")
            return None

        class_name = class_match.group(1)
        print(f"🎯 目标类名: {class_name}")

        # 生成Java代码
        java_code = convert_jimple_content_to_java(jimple_content, class_name)

        # 确保输出目录存在
        os.makedirs(temp_dir, exist_ok=True)

        # 生成Java文件路径
        java_filename = f"{class_name}.java"
        java_file_path = os.path.join(temp_dir, java_filename)

        # 写入Java文件
        with open(java_file_path, 'w', encoding='utf-8') as f:
            f.write(java_code)

        print(f"✅ 手动转换完成: {java_file_path}")
        return java_file_path

    except Exception as e:
        print(f"❌ 处理出错：{str(e)}")
        import traceback
        traceback.print_exc()
        return None


def convert_jimple_content_to_java(jimple_content, class_name):
    """将Jimple内容转换为Java代码"""

    lines = jimple_content.split('\n')
    java_lines = []
    indent_level = 0
    in_method = False
    current_method = ""

    for line in lines:
        original_line = line
        line = line.strip()

        # 跳过注释和空行
        if not line or line.startswith(';'):
            continue

        # 处理类定义
        if line.startswith('public class'):
            # 简化类定义，移除不必要的extends
            if 'extends java.lang.Object' in line:
                java_line = f"public class {class_name}"
            else:
                java_line = line.replace('java.lang.', '')
            java_lines.append(java_line + " {")
            indent_level += 1
            continue

        # 处理静态字段
        elif 'static final' in line and line.endswith(';'):
            java_line = ' ' * (indent_level * 4) + line
            java_lines.append(java_line)
            continue

        # 处理方法开始
        elif re.match(r'^(public|protected|private|static).*\(.*\).*$', line) and not line.endswith(';'):
            method_line = convert_method_declaration(line, class_name)
            java_lines.append(' ' * (indent_level * 4) + method_line + " {")
            in_method = True
            current_method = line
            indent_level += 1
            continue

        # 处理方法体中的语句
        elif in_method and not line.startswith('}'):
            converted_stmt = convert_statement(line, class_name)
            if converted_stmt:
                java_lines.append(' ' * (indent_level * 4) + converted_stmt)
            continue

        # 处理方法结束
        elif line == '}' and in_method:
            indent_level -= 1
            java_lines.append(' ' * (indent_level * 4) + "}")
            in_method = False
            current_method = ""
            continue

        # 处理类结束
        elif line == '}':
            indent_level -= 1
            java_lines.append("}")
            continue

        # 处理其他语句（字段赋值等）
        elif '=' in line and line.endswith(';'):
            java_lines.append(' ' * (indent_level * 4) + line)
            continue

    return '\n'.join(java_lines)


def convert_method_declaration(jimple_method, class_name):
    """转换方法声明"""
    # 处理构造函数
    if '<init>' in jimple_method:
        jimple_method = jimple_method.replace('<init>', class_name)

    # 简化类型名称
    jimple_method = re.sub(r'java\.lang\.(\w+)', r'\1', jimple_method)

    # 清理参数类型
    jimple_method = re.sub(r'\(([^)]*)\)',
                           lambda m: '(' + clean_parameter_list(m.group(1)) + ')',
                           jimple_method)

    return jimple_method


def clean_parameter_list(param_str):
    """清理参数列表"""
    if not param_str:
        return ""

    params = [p.strip() for p in param_str.split(',')]
    cleaned_params = []

    for param in params:
        # 简化参数类型
        if '[]' in param:
            # 处理数组类型
            base_type = param.replace('[]', '').replace('java.lang.', '')
            cleaned_params.append(f"{base_type}[]")
        else:
            # 处理普通类型
            cleaned_param = param.replace('java.lang.', '')
            cleaned_params.append(cleaned_param)

    return ', '.join(cleaned_params)


def convert_statement(jimple_stmt, class_name):
    """转换Jimple语句为Java语句"""
    jimple_stmt = jimple_stmt.strip()

    # 跳过标签和无关语句
    if jimple_stmt.startswith('label') or jimple_stmt.startswith('goto'):
        return None

    # 处理return语句
    if jimple_stmt == 'return' or jimple_stmt == 'return;':
        return "return;"

    # 处理变量赋值
    if ':=' in jimple_stmt:
        return convert_assignment(jimple_stmt, class_name)

    # 处理if语句
    if jimple_stmt.startswith('if'):
        return convert_if_statement(jimple_stmt)

    # 处理方法调用
    if 'invoke' in jimple_stmt:
        return convert_method_invocation(jimple_stmt, class_name)

    # 默认返回原语句（加上分号）
    return jimple_stmt + ';' if not jimple_stmt.endswith(';') else jimple_stmt


def convert_assignment(jimple_assign, class_name):
    """转换赋值语句"""
    parts = jimple_assign.split(':=')
    if len(parts) != 2:
        return jimple_assign + ';'

    left = parts[0].strip()
    right = parts[1].strip()

    # 跳过this参数声明
    if '@this' in right:
        return None

    # 如果右边是方法调用
    if 'invoke' in right:
        method_call = convert_method_invocation(right, class_name)
        if method_call:
            return f"{left} = {method_call};"

    # 普通赋值
    cleaned_right = clean_expression(right)
    return f"{left} = {cleaned_right};"


def convert_method_invocation(jimple_invoke, class_name):
    """转换方法调用"""
    # specialinvoke r0.<java.lang.Object: void <init>()>()
    # virtualinvoke r1.<java.io.PrintStream: void println(java.lang.String)>(r2)

    patterns = [
        r'(specialinvoke|virtualinvoke|staticinvoke) (\w+)\.<([^:]+): ([^>]+)>\(([^)]*)\)',
        r'(\w+) = (@\w+);'  # 简单的参数赋值
    ]

    for pattern in patterns:
        match = re.match(pattern, jimple_invoke)
        if match:
            if len(match.groups()) == 5:
                invoke_type, obj, target_class, method_sig, params = match.groups()
                return build_java_method_call(invoke_type, obj, target_class, method_sig, params, class_name)
            elif len(match.groups()) == 2:
                var, value = match.groups()
                return f"{var} = {value.replace('@', '')};"

    return jimple_invoke + ';'


def build_java_method_call(invoke_type, obj, target_class, method_sig, params, class_name):
    """构建Java方法调用"""
    # 解析方法签名：返回类型 方法名
    sig_parts = method_sig.split()
    if len(sig_parts) < 2:
        return None

    return_type = sig_parts[0]
    method_name = sig_parts[-1]

    # 清理类名和方法名
    target_class = target_class.replace('java.lang.', '')

    # 处理构造函数
    if method_name == '<init>':
        method_name = target_class.split('.')[-1]  # 取简单类名
        if invoke_type == 'specialinvoke' and target_class == 'java.lang.Object':
            return f"super({clean_parameters(params)});"
        else:
            return f"new {method_name}({clean_parameters(params)});"

    # 处理方法调用
    cleaned_params = clean_parameters(params)

    if invoke_type == 'staticinvoke':
        # 静态方法调用
        return f"{target_class}.{method_name}({cleaned_params});"
    else:
        # 实例方法调用
        return f"{obj}.{method_name}({cleaned_params});"


def clean_expression(expr):
    """清理表达式"""
    # 移除@符号
    expr = expr.replace('@', '')

    # 简化类型转换
    expr = re.sub(r'\((\w+)\)', r'(\1)', expr)

    return expr


def clean_parameters(param_str):
    """清理参数列表"""
    if not param_str:
        return ""

    params = [p.strip() for p in param_str.split(',')]
    cleaned_params = []

    for param in params:
        # 移除参数中的类型信息，只保留变量名
        if ':' in param:
            # 格式：变量名:类型
            var_name = param.split(':')[0].strip()
            cleaned_params.append(var_name)
        else:
            # 直接变量名
            cleaned_param = param.replace('@', '')
            cleaned_params.append(cleaned_param)

    return ', '.join(cleaned_params)


def convert_if_statement(jimple_if):
    """转换if语句"""
    # if r1 == null goto label2
    match = re.match(r'if (.*) goto (label\d+)', jimple_if)
    if match:
        condition, label = match.groups()
        # 将Jimple条件转换为Java条件
        java_condition = convert_condition(condition)
        return f"if ({java_condition}) {{ // goto {label}"

    return jimple_if + ';'


def convert_condition(jimple_condition):
    """转换条件表达式"""
    # 替换Jimple操作符为Java操作符
    replacements = {
        '==': '==',
        '!=': '!=',
        '<': '<',
        '>': '>',
        '<=': '<=',
        '>=': '>='
    }

    condition = jimple_condition
    for jimple_op, java_op in replacements.items():
        condition = condition.replace(jimple_op, java_op)

    # 处理null检查
    condition = condition.replace(' null', ' null')

    return condition


def test_jimple_conversion():
    """测试Jimple转换功能"""
    # 创建一个简单的测试Jimple文件
    test_jimple_content = """
public class SimpleTest extends java.lang.Object
{
    public void <init>()
    {
        SimpleTest r0;
        r0 := @this: SimpleTest;
        specialinvoke r0.<java.lang.Object: void <init>()>();
        return;
    }

    public void testMethod()
    {
        SimpleTest r0;
        r0 := @this: SimpleTest;
        return;
    }
}
"""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_jimple_path = os.path.join(temp_dir, "SimpleTest.jimple")
        with open(test_jimple_path, 'w') as f:
            f.write(test_jimple_content)

        print("🧪 测试简单Jimple转换...")
        result = convert_jimple_to_java(test_jimple_path, temp_dir)

        if result:
            print(f"✅ 测试成功！生成的Java文件：{result}")
            # 显示生成的Java内容
            with open(result, 'r') as f:
                print("生成的Java代码：")
                print(f.read())
        else:
            print("❌ 测试失败")

        return result is not None

def process_file(file_path, input_root, output_root, counter):
    """处理单个文件（.class或.jimple），返回是否成功"""
    # 获取相对路径，创建输出目录
    relative_path = get_relative_path(file_path, input_root)
    output_dir = create_output_dir(output_root, relative_path)

    # 创建临时目录用于转换
    with tempfile.TemporaryDirectory() as temp_dir:
        # 根据文件类型调用转换工具
        if file_path.endswith(".class"):
            java_path = convert_class_to_java(file_path, temp_dir)
        elif file_path.endswith(".jimple"):
            java_path = convert_jimple_to_java(file_path, temp_dir)
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

    # 区分“目录下全是子目录”还是“全是文件”
    if any(os.path.isdir(e) for e in entries):
        # 全是子目录，递归处理
        for subdir in entries:
            if os.path.isdir(subdir):
                traverse_directory(subdir, input_root, output_root, counter)
    else:
        # 全是文件，筛选并处理目标文件
        for file_path in entries:
            if file_path.endswith((".class", ".jimple")):
                process_file(file_path, input_root, output_root, counter)


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="批量转换.class和.jimple文件为.java文件")
    parser.add_argument("input_dir", help="输入数据集根目录")
    parser.add_argument("--output", default="Output", help="输出目录（默认：Output）")
    args = parser.parse_args()

    input_root = os.path.abspath(args.input_dir)
    output_root = os.path.abspath(args.output)

    # 初始化
    init_output_dir(output_root)
    counter = [1]  # 用列表实现全局自增（避免nonlocal问题）
    #test_jimple_conversion()
    # 开始遍历处理
    print(f"开始处理目录：{input_root}")
    traverse_directory(input_root, input_root, output_root, counter)
    print(f"处理完成，共生成{counter[0] - 1}个.java文件，输出目录：{output_root}")


if __name__ == "__main__":
    main()