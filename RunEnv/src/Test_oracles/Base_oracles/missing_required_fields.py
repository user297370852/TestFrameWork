#!/usr/bin/env python3
"""
测试预言: 检测必需字段缺失
规则: JSON文件必须包含基本的测试结果结构
"""
from typing import Dict, Any, Optional


def oracle_missing_required_fields(log_data: Dict[str, Any], file_path: str) -> Optional[Dict[str, Any]]:
    """
    预言3: 检测必需字段缺失
    规则: JSON文件必须包含基本的测试结果结构
    """
    if "test_results" not in log_data:
        #如果不是JSON文件, 则返回None
        if not file_path.endswith(".json"):
            return None
        return {
            "type": "missing_required_fields",
            "file_path": file_path,
            "score": 1.0,
            "info": "测试记录格式异常，缺失test_results字段"
        }

    return None
