import os
import subprocess
import tempfile
from pathlib import Path

# 获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
SOOT_JAR = os.path.join(project_root, "lib", "soot-4.1.0.jar")  # Soot的JAR路径
lib_dir = os.path.dirname(SOOT_JAR)


def get_java_executable(version="1.8"):
    """使用jenv获取指定版本的Java可执行文件路径"""
    try:
        # 使用jenv获取Java可执行文件路径
        result = subprocess.run(
            ["jenv", "which", "java"], 
            capture_output=True, 
            text=True,
            env={**os.environ, "JENV_VERSION": version}
        )
        
        if result.returncode == 0:
            java_path = result.stdout.strip()
            if java_path and os.path.exists(java_path):
                return java_path
            else:
                print(f"⚠️  jenv返回的路径不存在: {java_path}")
        else:
            print(f"❌ jenv命令执行失败: {result.stderr}")
            
    except FileNotFoundError:
        print("❌ 未找到jenv命令，请确保已安装jenv")
    except Exception as e:
        print(f"❌ 获取Java路径时出错: {e}")
    
    # 回退方案：尝试从PATH获取
    try:
        result = subprocess.run(["which", "java"], capture_output=True, text=True)
        if result.returncode == 0:
            java_path = result.stdout.strip()
            print(f"⚠️  使用PATH中的Java: {java_path}")
            return java_path
    except:
        pass
    
    print("❌ 无法找到Java可执行文件")
    return None


def get_javac_executable(version="1.8"):
    """获取javac可执行文件路径"""
    java_executable = get_java_executable(version)
    if java_executable:
        # 将java替换为javac
        return java_executable.replace("java", "javac")
    return None


def get_rt_jar_path(version="1.8"):
    """获取rt.jar路径"""
    try:
        # 尝试使用jenv获取JDK路径
        result = subprocess.run(
            ["jenv", "prefix", version], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            jdk_path = result.stdout.strip()
            # 尝试多个可能的rt.jar位置
            rt_jar_paths = [
                os.path.join(jdk_path, "jre", "lib", "rt.jar"),
                os.path.join(jdk_path, "lib", "rt.jar"),
                os.path.join(jdk_path, "Contents", "Home", "jre", "lib", "rt.jar"),
                os.path.join(jdk_path, "Contents", "Home", "lib", "rt.jar"),
            ]
            
            for rt_jar_path in rt_jar_paths:
                if os.path.exists(rt_jar_path):
                    return rt_jar_path
            
            print(f"⚠️  在JDK路径中未找到rt.jar: {jdk_path}")
        else:
            print(f"❌ 获取JDK路径失败: {result.stderr}")
            
    except Exception as e:
        print(f"❌ 获取rt.jar路径时出错: {e}")
    
    # 回退方案：尝试常见位置
    common_paths = [
        "/usr/lib/jvm/java-8-openjdk/jre/lib/rt.jar",
        "/usr/lib/jvm/java-8-oracle/jre/lib/rt.jar",
        "/Library/Java/JavaVirtualMachines/openjdk-8.jdk/Contents/Home/jre/lib/rt.jar",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"⚠️  使用常见位置的rt.jar: {path}")
            return path
    
    print("❌ 无法找到rt.jar文件")
    return None


def build_soot_classpath():
    """构建Soot的完整classpath"""
    try:
        all_jars = []
        if os.path.exists(lib_dir):
            for jar_file in os.listdir(lib_dir):
                if jar_file.endswith('.jar'):
                    all_jars.append(os.path.join(lib_dir, jar_file))
        
        if not all_jars:
            print("❌ 未找到任何JAR文件")
            return ""
            
        return ":".join(all_jars)
    except Exception as e:
        print(f"❌ 构建classpath时出错: {e}")
        return ""


def test_soot_basic():
    """测试Soot基本功能"""
    print("🧪 测试Soot基本功能...")
    
    # 获取Java可执行文件
    java_executable = get_java_executable("1.8")
    if not java_executable:
        print("❌ 无法获取Java可执行文件，测试终止")
        return False
    
    # 构建classpath
    full_classpath = build_soot_classpath()
    if not full_classpath:
        print("❌ 无法构建classpath，测试终止")
        return False
    
    print(f"📍 使用Java: {java_executable}")
    print(f"📍 Soot JAR: {SOOT_JAR}")
    
    # 测试Soot是否能正常运行
    cmd = [java_executable, "-cp", full_classpath, "soot.Main", "--help"]

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
    print("🧪 测试Soot处理class文件...")
    
    # 获取Java可执行文件和rt.jar路径
    java_executable = get_java_executable("1.8")
    if not java_executable:
        print("❌ 无法获取Java可执行文件，测试终止")
        return False
    
    javac_executable = get_javac_executable("1.8")
    if not javac_executable:
        print("❌ 无法获取javac可执行文件，测试终止")
        return False
    
    rt_jar = get_rt_jar_path("1.8")
    if not rt_jar:
        print("⚠️  无法找到rt.jar，尝试不使用rt.jar继续测试")
        rt_jar = ""
    
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
        compile_cmd = [javac_executable, java_file]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)

        if compile_result.returncode != 0:
            print("❌ 编译Java文件失败")
            print(f"编译错误: {compile_result.stderr}")
            return False

        # 构建完整的classpath
        full_classpath = build_soot_classpath()
        if rt_jar:
            full_classpath += f":{rt_jar}"
        full_classpath += f":{temp_dir}"
        
        cmd = [
            java_executable,
            "-cp", full_classpath,
            "soot.Main",
            "-cp", temp_dir,  # 类路径
            "-pp",  # 处理路径
            "-f", "J",  # 输出Java
            "-d", temp_dir,
            "SimpleTest"
        ]

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


if __name__ == "__main__":
    print("🚀 开始 Soot 测试...")
    
    # 测试基本功能
    basic_test_result = test_soot_basic()
    if not basic_test_result:
        print("❌ 基本功能测试失败，退出")
        exit(1)
    
    print()
    
    # 测试类文件处理
    class_test_result = test_soot_with_simple_class()
    if class_test_result:
        print("\n🎉 所有测试通过！")
        exit(0)
    else:
        print("\n❌ 类文件处理测试失败")
        exit(1)
