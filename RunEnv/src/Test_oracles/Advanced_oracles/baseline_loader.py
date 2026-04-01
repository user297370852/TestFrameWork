#!/usr/bin/env python3
"""
基准模型加载器
加载和管理GC排名基准模型
"""
import json
import os
from typing import Dict, Any, Optional, Tuple


class BaselineLoader:
    """GC排名基准模型加载器"""
    
    _instance = None
    _baseline = None
    
    def __new__(cls):
        """单例模式，确保基准模型只加载一次"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化加载器"""
        if self._baseline is None:
            self._load_baseline()
    
    def _load_baseline(self) -> None:
        """加载基准模型文件"""
        baseline_path = os.path.join(
            os.path.dirname(__file__), 
            'gc_ranking_baseline.json'
        )
        
        with open(baseline_path, 'r', encoding='utf-8') as f:
            self._baseline = json.load(f)
    
    def get_baseline(self) -> Dict[str, Any]:
        """获取完整的基准模型"""
        return self._baseline
    
    def get_metric_info(self, metric_type: str) -> Optional[Dict[str, Any]]:
        """获取指标信息"""
        return self._baseline.get('metrics', {}).get(metric_type)
    
    def get_gc_types_for_jdk(self, jdk_version: str) -> list:
        """获取指定JDK版本支持的GC类型"""
        return self._baseline.get('gc_support_by_jdk', {}).get(jdk_version, [])
    
    def get_baseline_params(
        self, 
        metric_type: str, 
        jdk_version: str, 
        gc_type: str
    ) -> Optional[Tuple[float, float, int]]:
        """
        获取基准参数 (μ, σ, n)
        
        Args:
            metric_type: 指标类型 (duration_ms, gc_stw_time_ms, etc.)
            jdk_version: JDK版本
            gc_type: GC类型
        
        Returns:
            (mu, sigma, n) 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['by_jdk'][jdk_version][gc_type]
            return (
                baseline['mu'],
                baseline['sigma'],
                baseline['n']
            )
        except KeyError:
            return None
    
    def get_overall_baseline_params(
        self, 
        metric_type: str, 
        gc_type: str
    ) -> Optional[Tuple[float, float]]:
        """
        获取整体基准参数 (μ, σ)，不区分JDK版本
        
        Args:
            metric_type: 指标类型
            gc_type: GC类型
        
        Returns:
            (mu, sigma) 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['overall'][gc_type]
            return (baseline['mu'], baseline['sigma'])
        except KeyError:
            return None
    
    def should_filter_zero(self, metric_type: str) -> bool:
        """检查该指标是否需要过滤零值"""
        metric_info = self.get_metric_info(metric_type)
        if metric_info:
            return metric_info.get('filter_zero', False)
        return False
    
    def get_supported_metrics(self) -> list:
        """获取所有支持的指标类型"""
        return list(self._baseline.get('metrics', {}).keys())
    
    def get_supported_jdk_versions(self) -> list:
        """获取所有支持的JDK版本"""
        return list(self._baseline.get('gc_support_by_jdk', {}).keys())


# 全局加载器实例
_loader = None

def get_baseline_loader() -> BaselineLoader:
    """获取基准模型加载器实例"""
    global _loader
    if _loader is None:
        _loader = BaselineLoader()
    return _loader
