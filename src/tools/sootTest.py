import os
from pathlib import Path

SOOT_JAR = "/Users/yeliu/PycharmProjects/PythonProject/lib/soot-4.1.0.jar"  # Soot的JAR路径

def test_soot_basic():
    """测试Soot基本功能"""
    import tempfile
    import subprocess

    lib_dir = os.path.dirname(SOOT_JAR)
    java8_executable = "/Users/yeliu/IdeaProjects/GCFuzz-main/01JVMS/macOSx64/openjdk8/Contents/Home/bin/java"

    # 测试Soot是否能正常运行
    cmd = [java8_executable, "-cp", SOOT_JAR, "soot.Main", "--help"]

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

        # 使用Soot处理class文件（这应该是最可靠的）
        classpath = f"{SOOT_JAR}:{lib_dir}/*:{rt_jar}:{temp_dir}"
        cmd = [
            java8_executable,
            "-cp", classpath,
            "soot.Main",
            "-cp", temp_dir,  # 类路径
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

        return len(java_files) > 0
test_soot_with_simple_class()