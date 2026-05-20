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

    def classify_gc_type(result: Dict[str, Any]) -> str:
        gc_params = result.get("GC_parameters", [])
        params_str = " ".join(gc_params).upper()

        if "+USEZGC" in params_str:
            return "ZGC"
        elif "+USESHENANDOAHGC" in params_str:
            return "ShenandoahGC"
        elif "+USEG1GC" in params_str:
            return "G1GC"
        elif "+USEPARALLELGC" in params_str or "+USEPARALLELOLDGC" in params_str:
            return "ParallelGC"
        elif "+USESERIALGC" in params_str:
            return "SerialGC"
        else:
            return "Unknown"

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
        "java.security.AccessControlException",  # 访问控制异常
        "java.lang.UnsupportedOperationException",  # 不支持的操作
        "Unrecognized VM option",  # 未知VM选项
        "Too many open files",  # 打开文件数过多
        "unexpected pattern",  # 预期外的模式
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
    for result in test_results:
        if not result.get("success", True) or result.get("exit_code", 0) != 0:
            output = result.get("output", "")

            # 过滤环境相关错误
            if is_environment_error(output):
                continue  # 跳过环境错误

            # 真正的程序逻辑错误
            output_preview = output[:120].replace("\n", " ")
            if len(output) > 120:
                output_preview += "..."
            failed_tests.append({
                "score": 10.0,
                "info": f"{result.get('jdk_version', 'unknown')}-{classify_gc_type(result)}: 测试执行异常，退出码为{result.get('exit_code', -1)}，错误摘要：{output_preview}"
            })

    # 如果有真正的程序逻辑错误，返回异常
    if failed_tests:
        return {
            "type": "test_failure",
            "file_path": file_path,
            "failed_tests": failed_tests
        }

    return None
