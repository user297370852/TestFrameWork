#!/usr/bin/env python3
"""
基准模型加载器
加载和管理GC排名基准模型

V2.1 扩展：支持读取 rank_hist, regret_*, alpha 等新字段
"""
import json
import os
from typing import Dict, Any, Optional, Tuple, List


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
    
    # ============================================================
    # V2.1 新增方法：读取 schema v2 字段
    # ============================================================
    
    def get_rank_hist(
        self, 
        metric_type: str, 
        jdk_version: str, 
        gc_type: str
    ) -> Optional[Dict[str, int]]:
        """
        获取历史排名直方图
        
        Args:
            metric_type: 指标类型
            jdk_version: JDK版本
            gc_type: GC类型
        
        Returns:
            排名频数字典 {"1": 120, "2": 340, ...} 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['by_jdk'][jdk_version][gc_type]
            return baseline.get('rank_hist')
        except KeyError:
            return None
    
    def get_regret_baseline(
        self, 
        metric_type: str, 
        jdk_version: str, 
        gc_type: str
    ) -> Optional[Dict[str, float]]:
        """
        获取 regret 的历史基线参数
        
        Args:
            metric_type: 指标类型
            jdk_version: JDK版本
            gc_type: GC类型
        
        Returns:
            {
                'median': regret_median,
                'mad': regret_mad,
                'q90': regret_q90,
                'q95': regret_q95,
                'q99': regret_q99
            } 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['by_jdk'][jdk_version][gc_type]
            result = {}
            for key in ['regret_median', 'regret_mad', 'regret_q90', 'regret_q95', 'regret_q99']:
                if key in baseline:
                    result[key] = baseline[key]
            
            if not result:
                return None
            return result
        except KeyError:
            return None
    
    def get_metric_alpha(self, metric_type: str) -> float:
        """
        获取指标的平滑参数 alpha
        
        Args:
            metric_type: 指标类型
        
        Returns:
            alpha 值（默认值见设计文档第6节）
        """
        # 默认alpha值（来自设计文档第6.1节）
        default_alphas = {
            'duration_ms': 1.0,
            'gc_stw_time_ms': 0.1,
            'max_stw_time_ms': 0.01,
            'total_gc_count': 1.0
        }
        
        # 尝试从baseline中获取
        try:
            metric_info = self._baseline['metrics'][metric_type]
            if 'alpha' in metric_info:
                return metric_info['alpha']
        except KeyError:
            pass
        
        return default_alphas.get(metric_type, 1.0)
    
    def get_metric_tau(self, metric_type: str) -> float:
        """
        获取指标的门控阈值 tau
        
        Args:
            metric_type: 指标类型
        
        Returns:
            tau 值（默认值见设计文档第6.2节）
        """
        # 默认tau值（来自设计文档第6.2节）
        default_taus = {
            'duration_ms': 0.05,
            'gc_stw_time_ms': 0.10,
            'max_stw_time_ms': 0.10,
            'total_gc_count': 0.08
        }
        
        # 尝试从baseline中获取
        try:
            metric_info = self._baseline['metrics'][metric_type]
            if 'tau' in metric_info:
                return metric_info['tau']
        except KeyError:
            pass
        
        return default_taus.get(metric_type, 0.1)
    
    def get_metric_lambda(self, metric_type: str) -> float:
        """
        获取指标的尾部差距阈值 lambda
        
        Args:
            metric_type: 指标类型
        
        Returns:
            lambda 值（默认值见设计文档第6.3节）
        """
        # 默认lambda值（来自设计文档第6.3节）
        default_lambdas = {
            'duration_ms': 1.20,
            'gc_stw_time_ms': 1.50,
            'max_stw_time_ms': 1.50,
            'total_gc_count': 1.30
        }
        
        # 尝试从baseline中获取
        try:
            metric_info = self._baseline['metrics'][metric_type]
            if 'lambda' in metric_info:
                return metric_info['lambda']
        except KeyError:
            pass
        
        return default_lambdas.get(metric_type, 1.5)
    
    def has_v2_fields(
        self, 
        metric_type: str, 
        jdk_version: str, 
        gc_type: str
    ) -> bool:
        """
        检查指定配置是否有V2字段
        
        Args:
            metric_type: 指标类型
            jdk_version: JDK版本
            gc_type: GC类型
        
        Returns:
            是否有V2字段
        """
        rank_hist = self.get_rank_hist(metric_type, jdk_version, gc_type)
        regret_baseline = self.get_regret_baseline(metric_type, jdk_version, gc_type)
        
        return rank_hist is not None or regret_baseline is not None
    
    def get_overall_rank_hist(self, metric_type: str, gc_type: str) -> Optional[Dict[str, int]]:
        """
        获取整体（不区分JDK）的排名直方图
        
        Args:
            metric_type: 指标类型
            gc_type: GC类型
        
        Returns:
            排名频数字典 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['overall'][gc_type]
            return baseline.get('rank_hist')
        except KeyError:
            return None
    
    def get_overall_regret_baseline(self, metric_type: str, gc_type: str) -> Optional[Dict[str, float]]:
        """
        获取整体（不区分JDK）的regret基线参数
        
        Args:
            metric_type: 指标类型
            gc_type: GC类型
        
        Returns:
            regret基线参数 或 None
        """
        try:
            baseline = self._baseline['baselines'][metric_type]['overall'][gc_type]
            result = {}
            for key in ['regret_median', 'regret_mad', 'regret_q90', 'regret_q95', 'regret_q99']:
                if key in baseline:
                    result[key] = baseline[key]
            
            if not result:
                return None
            return result
        except KeyError:
            return None


# 全局加载器实例
_loader = None

def get_baseline_loader() -> BaselineLoader:
    """获取基准模型加载器实例"""
    global _loader
    if _loader is None:
        _loader = BaselineLoader()
    return _loader
