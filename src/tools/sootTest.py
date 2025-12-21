import os
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
SOOT_JAR = os.path.join(current_dir, "..", "..", "lib", "soot-4.1.0.jar")  # Soot的JAR路径  

def test_soot_basic():
    """测试Soot基本功能"""
    import tempfile
    import subprocess

    lib_dir = os.path.dirname(SOOT_JAR)
    java8_executable = "/Users/yeliu/IdeaProjects/GCFuzz-main/01JVMS/macOSx64/openjdk8/Contents/Home/bin/java"
    
    # 构建完整的classpath，包含所有必需的JAR文件
    all_jars = []
    for jar_file in os.listdir(lib_dir):
        if jar_file.endswith('.jar'):
            all_jars.append(os.path.join(lib_dir, jar_file))
    full_classpath = ":".join(all_jars)

    # 测试Soot是否能正常运行
    cmd = [java8_executable, "-cp", full_classpath, "soot.Main", "--help"]

    print("🧪 测试Soot基本功能...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Soot基本功能正常")
        return True
    else:
        print("❌ Soot无法运行")
        print(f"错误: {result.stderr}")
        return False

test_soot_basic()

def test_soot_with_simple_class():
    """用最简单的类测试Soot"""
    import tempfile
    import subprocess

    lib_dir = os.path.dirname(SOOT_JAR)
    java8_executable = "/Users/yeliu/IdeaProjects/GCFuzz-main/01JVMS/macOSx64/openjdk8/Contents/Home/bin/java"
    rt_jar = "/Users/yeliu/IdeaProjects/GCFuzz-main/01JVMS/macOSx64/openjdk8/Contents/Home/jre/lib/rt.jar"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建一个最简单的Java类文件
        java_code = """
public class SimpleTest {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}
"""
        java_file = os.path.join(temp_dir, "SimpleTest.java")
        with open(java_file, 'w') as f:
            f.write(java_code)

        # 编译Java文件
        compile_cmd = [java8_executable.replace('java', 'javac'), java_file]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)

        if compile_result.returncode != 0:
            print("❌ 编译Java文件失败")
            return False

        # 构建完整的classpath，包含所有必需的JAR文件
        all_jars = []
        for jar_file in os.listdir(lib_dir):
            if jar_file.endswith('.jar'):
                all_jars.append(os.path.join(lib_dir, jar_file))
        full_classpath = ":".join(all_jars) + f":{rt_jar}:{temp_dir}"
        
        cmd = [
            java8_executable,
            "-cp", full_classpath,
            "soot.Main",
            "-cp", temp_dir,  # 类路径
            "-pp",  # 处理路径
            "-f", "J",  # 输出Java
            "-d", temp_dir,
            "SimpleTest"
        ]

        print("🧪 测试Soot处理class文件...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)

        print(f"返回码: {result.returncode}")
        print(f"输出: {result.stdout}")
        if result.stderr:
            print(f"错误: {result.stderr}")

        # 检查输出
        java_files = list(Path(temp_dir).rglob("*.java"))
        print(f"生成的Java文件: {[f.name for f in java_files]}")
        
        # 显示生成的Java文件内容
        for java_file in java_files:
            print(f"\n📄 {java_file.name} 内容:")
            print("-" * 40)
            with open(java_file, 'r') as f:
                print(f.read())

        return len(java_files) > 0
test_soot_with_simple_class()