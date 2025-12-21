#!/usr/bin/env python3
"""
测试预言: 检测测试失败情况
规则: 测试用例应该成功执行，但过滤掉环境相关的错误
"""
from typing import Dict, Any, Optional


def oracle_test_failure(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言1: 检测测试失败情况
    规则: 测试用例应该成功执行，但过滤掉环境相关的错误
    """
    if "test_results" not in log_data:
        return None

    test_results = log_data["test_results"]
    if not test_results:
        return None

    # 环境相关错误的关键词列表
    ENVIRONMENT_ERRORS = {
        "NoClassDefFoundError",
        "ClassNotFoundException",
        "BootstrapMethodError",
        "UnsupportedClassVersionError",
        "NoSuchMethodError",  # 可能由于版本不兼容
        "NoSuchFieldError",
        "IllegalAccessError",
        "InstantiationError",
        "VerifyError",
        "LinkageError",
        "java.lang.invoke",  # 方法句柄相关错误
        "java.lang.reflect",  # 反射相关错误
        "sun.misc",  # 内部API相关
        "com.sun",  # 内部API相关
    }

    def is_environment_error(output: str) -> bool:
        """判断错误是否是环境相关的"""
        output_upper = output.upper()

        # 检查是否包含环境错误关键词
        for error_keyword in ENVIRONMENT_ERRORS:
            if error_keyword.upper() in output_upper:
                return True

        # 检查特定的错误模式
        error_patterns = [
            "JAVA.LANG.INVOKE.",  # 方法句柄相关
            "JAVA.LANG.REFLECT.",  # 反射相关
            "SUN.MISC.",  # 内部API
            "COM.SUN.",  # 内部API
            "UNSUPPORTED CLASS VERSION",  # 版本不兼容
        ]

        for pattern in error_patterns:
            if pattern in output_upper:
                return True

        return False

    failed_tests = []
    environment_failures = []  # 记录环境相关失败，用于调试

    for result in test_results:
        if not result.get("success", True) or result.get("exit_code", 0) != 0:
            output = result.get("output", "")

            # 过滤环境相关错误
            if is_environment_error(output):
                environment_failures.append({
                    "jdk_version": result.get("jdk_version", "unknown"),
                    "jvm_parameters": result.get("jvm_parameters", []),
                    "exit_code": result.get("exit_code", -1),
                    "error_type": "environment_error",
                    "output_preview": output[:200] + "..." if len(output) > 200 else output
                })
                continue  # 跳过环境错误

            # 真正的程序逻辑错误
            failed_tests.append({
                "jdk_version": result.get("jdk_version", "unknown"),
                "jvm_parameters": result.get("jvm_parameters", []),
                "exit_code": result.get("exit_code", -1),
                "output": output,
                "duration_ms": result.get("duration_ms", 0)
            })

    # 如果有真正的程序逻辑错误，返回异常
    if failed_tests:
        result = {
            "type": "test_failure",
            "file_path": file_path,
            "class_info": log_data.get("class_file_info", {}),
            "failed_tests": failed_tests,
            "total_tests": len(test_results),
            "failed_count": len(failed_tests)
        }

        # 如果需要调试，可以添加环境失败信息
        if environment_failures:
            result["environment_failures_filtered"] = {
                "count": len(environment_failures),
                "samples": environment_failures[:3]  # 只显示前3个样本
            }

        return result

    return None
