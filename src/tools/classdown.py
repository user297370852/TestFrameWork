import os
import struct
from pathlib import Path


class ClassFileVersionDowngrader:
    def __init__(self):
        # Java版本映射: 主版本号 -> Java版本
        self.version_map = {
            52: 'Java 8',
            51: 'Java 7',
            50: 'Java 6',
            49: 'Java 5',
            48: 'Java 4',
            47: 'Java 3',
            46: 'Java 2',
            45: 'Java 1.1'
        }

    def get_class_version(self, class_file_path):
        """读取.class文件的字节码版本"""
        try:
            with open(class_file_path, 'rb') as f:
                # 读取魔数 CAFEBABE
                magic = f.read(4)
                if magic != b'\xCA\xFE\xBA\xBE':
                    return None, "Invalid class file format"

                # 读取次版本号和主版本号
                minor_version = struct.unpack('>H', f.read(2))[0]
                major_version = struct.unpack('>H', f.read(2))[0]

                return major_version, minor_version
        except Exception as e:
            return None, str(e)

    def downgrade_class_version(self, class_file_path, target_major_version=52):
        """将.class文件版本降级到目标版本"""
        try:
            with open(class_file_path, 'rb') as f:
                data = bytearray(f.read())

            # 检查魔数
            if data[:4] != b'\xCA\xFE\xBA\xBE':
                return False, "Invalid class file format"

            # 获取当前版本
            current_major = struct.unpack('>H', data[6:8])[0]

            # 如果已经是目标版本或更低，不需要降级
            if current_major <= target_major_version:
                return True, f"Already compatible (version {current_major})"

            # 修改主版本号
            new_version_bytes = struct.pack('>H', target_major_version)
            data[6:8] = new_version_bytes

            # 写回文件
            with open(class_file_path, 'wb') as f:
                f.write(data)

            return True, f"Downgraded from version {current_major} to {target_major_version}"

        except Exception as e:
            return False, str(e)

    def scan_and_downgrade_directory(self, base_dir, target_version=52):
        """递归扫描目录并降级所有.class文件"""
        base_path = Path(base_dir)
        results = []

        for class_file in base_path.rglob('*.class'):
            # 获取当前版本
            major_version, minor_version = self.get_class_version(class_file)

            if major_version is None:
                print(f"❌ 无法读取: {class_file}")
                continue

            current_version_str = f"{major_version} ({self.version_map.get(major_version, 'Unknown')})"

            if major_version > target_version:
                # 需要降级
                success, message = self.downgrade_class_version(class_file, target_version)
                if success:
                    print(f"✅ 降级成功: {class_file} - {current_version_str} -> {target_version} (Java 8)")
                    results.append({
                        'file': str(class_file),
                        'original_version': major_version,
                        'target_version': target_version,
                        'status': 'downgraded',
                        'message': message
                    })
                else:
                    print(f"❌ 降级失败: {class_file} - {message}")
                    results.append({
                        'file': str(class_file),
                        'original_version': major_version,
                        'target_version': target_version,
                        'status': 'failed',
                        'message': message
                    })
            else:
                print(f"ℹ️  已兼容: {class_file} - 版本 {current_version_str}")
                results.append({
                    'file': str(class_file),
                    'original_version': major_version,
                    'target_version': target_version,
                    'status': 'compatible',
                    'message': f"Already compatible with Java 8"
                })

        return results

    def get_version_statistics(self, base_dir):
        """获取目录中.class文件的版本统计"""
        base_path = Path(base_dir)
        version_count = {}

        for class_file in base_path.rglob('*.class'):
            major_version, _ = self.get_class_version(class_file)
            if major_version is not None:
                version_count[major_version] = version_count.get(major_version, 0) + 1

        return version_count


# 使用示例
def main():
    downgrader = ClassFileVersionDowngrader()

    # 扫描目录并显示版本统计
    base_directory = "/Users/yeliu/PycharmProjects/PythonProject/RunEnv/unittest"
    print("扫描字节码版本...")
    stats = downgrader.get_version_statistics(base_directory)

    print("\n版本统计:")
    for version, count in sorted(stats.items()):
        java_version = downgrader.version_map.get(version, "Unknown")
        print(f"  版本 {version} ({java_version}): {count} 个文件")

    # 执行降级
    print(f"\n开始降级到Java 8兼容版本 (52)...")
    results = downgrader.scan_and_downgrade_directory(base_directory, 52)

    # 统计结果
    downgraded = len([r for r in results if r['status'] == 'downgraded'])
    compatible = len([r for r in results if r['status'] == 'compatible'])
    failed = len([r for r in results if r['status'] == 'failed'])

    print(f"\n降级完成:")
    print(f"  ✅ 降级成功: {downgraded} 个文件")
    print(f"  ℹ️  已兼容: {compatible} 个文件")
    print(f"  ❌ 失败: {failed} 个文件")


if __name__ == "__main__":
    main()