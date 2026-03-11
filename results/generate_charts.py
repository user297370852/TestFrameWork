#!/usr/bin/env python3
"""
GC测试结果可视化图表生成脚本
生成各种统计指标的概率变化和分布图
支持多种GC类型: ZGC, G1GC, Parallel, Serial
"""
import os
import sys
import json
import csv
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 设置中文字体支持
matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置图表样式
plt.style.use('seaborn-v0_8-darkgrid')

# 定义JDK版本颜色方案
# JDK17: 红色
# JDK21: 蓝色
# JDK25: 黄色
# JDK26: 黑色
JDK_COLORS = {
    'jdk17': '#FF6B6B',  # 红色
    'jdk21': '#2196F3',  # 蓝色
    'jdk25': '#FFC107',  # 黄色
    'jdk26': '#000000'   # 黑色
}

JDK_COLOR_LIST = ['#FF6B6B', '#2196F3', '#FFC107', '#000000']


def get_gc_type_from_csv(csv_file):
    """从CSV文件名推断GC类型"""
    filename = os.path.basename(csv_file).lower()
    if 'zgc' in filename:
        return 'ZGC'
    elif 'g1gc' in filename:
        return 'G1GC'
    elif 'parallel' in filename:
        return 'Parallel'
    elif 'serial' in filename:
        return 'Serial'
    elif 'shenandoah' in filename:
        return 'Shenandoah'
    else:
        return 'GC'


def load_summary_data(csv_file):
    """从CSV文件加载汇总数据"""
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def plot_gc_count_distribution(data, jdk_versions, output_dir, gc_type):
    """绘制GC次数分布图（箱线图）"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'{gc_type} - GC Count Distribution Across JDK Versions', fontsize=16, fontweight='bold')

    plot_data = {}
    for jdk in jdk_versions:
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))
        plot_data[jdk] = gc_counts

    # 箱线图（只显示有数据的JDK版本）
    ax1 = axes[0, 0]
    box_data = [plot_data[jdk] for jdk in jdk_versions]
    valid_data_indices = [i for i, data in enumerate(box_data) if len(data) > 0]
    
    if valid_data_indices:
        valid_box_data = [box_data[i] for i in valid_data_indices]
        valid_labels = [jdk_versions[i].upper() for i in valid_data_indices]
        valid_colors = [JDK_COLOR_LIST[i] for i in valid_data_indices]
        
        bp = ax1.boxplot(valid_box_data, labels=valid_labels,
                         patch_artist=True, notch=True, showmeans=True)
        for patch, color in zip(bp['boxes'], valid_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        ax1.set_ylabel('GC Count', fontsize=12)
        ax1.set_title('Box Plot of GC Counts', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3)
    else:
        ax1.text(0.5, 0.5, 'No Data Available', transform=ax1.transAxes, ha='center', va='center', fontsize=12)
        ax1.set_title('Box Plot of GC Counts', fontsize=13, fontweight='bold')

    # 小提琴图（只显示有数据的JDK版本）
    ax2 = axes[0, 1]
    valid_box_data = [data for data in box_data if len(data) > 0]
    valid_jdk_versions = [jdk for jdk, data in zip(jdk_versions, box_data) if len(data) > 0]
    valid_colors = [color for color, data in zip(JDK_COLOR_LIST, box_data) if len(data) > 0]
    
    if valid_box_data:
        positions = range(1, len(valid_box_data) + 1)
        parts = ax2.violinplot(valid_box_data, positions=positions, showmeans=True, showmedians=True)
        for i, (part, color) in enumerate(zip(parts['bodies'], valid_colors)):
            part.set_facecolor(color)
            part.set_alpha(0.7)
        ax2.set_xticks(positions)
        ax2.set_xticklabels([jdk.upper() for jdk in valid_jdk_versions])
        ax2.set_ylabel('GC Count', fontsize=12)
        ax2.set_title('Violin Plot of GC Counts', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, 'No Data Available', transform=ax2.transAxes, ha='center', va='center', fontsize=12)
        ax2.set_title('Violin Plot of GC Counts', fontsize=13, fontweight='bold')

    # 折线图（时间序列）
    ax3 = axes[1, 0]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))
        ax3.plot(range(1, len(gc_counts) + 1), gc_counts,
                marker='o', label=jdk.upper(), color=color, linewidth=2, markersize=8)
    ax3.set_xlabel('Run Number', fontsize=12)
    ax3.set_ylabel('GC Count', fontsize=12)
    ax3.set_title('GC Count Trend Over Runs', fontsize=13, fontweight='bold')
    ax3.legend(loc='best', fontsize=10)
    ax3.grid(True, alpha=0.3)

    # 直方图（频率分布）
    ax4 = axes[1, 1]
    all_gc_counts = []
    colors = []
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))
        all_gc_counts.extend(gc_counts)
        colors.extend([color] * len(gc_counts))

    ax4.hist(all_gc_counts, bins=20, edgecolor='black', alpha=0.7, color='lightblue')
    ax4.axvline(np.mean(all_gc_counts), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(all_gc_counts):.1f}')
    ax4.axvline(np.median(all_gc_counts), color='green', linestyle='--', linewidth=2, label=f'Median: {np.median(all_gc_counts):.1f}')
    ax4.set_xlabel('GC Count', fontsize=12)
    ax4.set_ylabel('Frequency', fontsize=12)
    ax4.set_title('Histogram of All GC Counts', fontsize=13, fontweight='bold')
    ax4.legend(loc='best', fontsize=10)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = os.path.join(output_dir, 'gc_count_distribution.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存GC次数分布图: {output_file}")
    plt.close()


def plot_pause_time_distribution(data, jdk_versions, output_dir, gc_type):
    """绘制暂停时间分布图"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'{gc_type} - Pause Time Distribution Across JDK Versions', fontsize=16, fontweight='bold')

    # 总暂停时间箱线图
    ax1 = axes[0, 0]
    plot_data = {}
    for jdk in jdk_versions:
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))
        plot_data[jdk] = pause_times

    box_data = [plot_data[jdk] for jdk in jdk_versions]
    bp = ax1.boxplot(box_data, labels=[jdk.upper() for jdk in jdk_versions],
                     patch_artist=True, notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], JDK_COLOR_LIST):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax1.set_ylabel('Total Pause Time (ms)', fontsize=12)
    ax1.set_title('Box Plot of Total Pause Time', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # 最大暂停时间箱线图
    ax2 = axes[0, 1]
    max_pause_data = []
    for jdk in jdk_versions:
        max_pauses = []
        for row in data:
            max_pause = row.get(f"{jdk}_Max_Pause_ms", "")
            if max_pause:
                max_pauses.append(float(max_pause))
        max_pause_data.append(max_pauses)

    bp = ax2.boxplot(max_pause_data, labels=[jdk.upper() for jdk in jdk_versions],
                     patch_artist=True, notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], JDK_COLOR_LIST):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax2.set_ylabel('Max Pause Time (ms)', fontsize=12)
    ax2.set_title('Box Plot of Max Pause Time', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # 暂停时间趋势图
    ax3 = axes[1, 0]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))
        ax3.plot(range(1, len(pause_times) + 1), pause_times,
                marker='o', label=jdk.upper(), color=color, linewidth=2, markersize=8)
    ax3.set_xlabel('Run Number', fontsize=12)
    ax3.set_ylabel('Total Pause Time (ms)', fontsize=12)
    ax3.set_title('Pause Time Trend Over Runs', fontsize=13, fontweight='bold')
    ax3.legend(loc='best', fontsize=10)
    ax3.grid(True, alpha=0.3)

    # 暂停时间直方图
    ax4 = axes[1, 1]
    all_pause_times = []
    for jdk in jdk_versions:
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                all_pause_times.append(float(pause_time))

    ax4.hist(all_pause_times, bins=20, edgecolor='black', alpha=0.7, color='lightblue')
    ax4.axvline(np.mean(all_pause_times), color='red', linestyle='--', linewidth=2,
                label=f'Mean: {np.mean(all_pause_times):.3f} ms')
    ax4.axvline(np.median(all_pause_times), color='green', linestyle='--', linewidth=2,
                label=f'Median: {np.median(all_pause_times):.3f} ms')
    ax4.set_xlabel('Total Pause Time (ms)', fontsize=12)
    ax4.set_ylabel('Frequency', fontsize=12)
    ax4.set_title('Histogram of All Pause Times', fontsize=13, fontweight='bold')
    ax4.legend(loc='best', fontsize=10)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = os.path.join(output_dir, 'pause_time_distribution.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存暂停时间分布图: {output_file}")
    plt.close()


def plot_coefficient_of_variation(data, jdk_versions, output_dir, gc_type):
    """绘制变异系数对比图（衡量概率性行为的波动程度）"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(f'{gc_type} - Coefficient of Variation (CV) Analysis', fontsize=16, fontweight='bold')

    # 计算各JDK版本的变异系数
    cv_gc_counts = []
    cv_pause_times = []
    cv_max_pause_times = []

    for jdk in jdk_versions:
        gc_counts = []
        pause_times = []
        max_pause_times = []

        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            max_pause = row.get(f"{jdk}_Max_Pause_ms", "")

            if gc_count:
                gc_counts.append(float(gc_count))
            if pause_time:
                pause_times.append(float(pause_time))
            if max_pause:
                max_pause_times.append(float(max_pause))

        # 计算CV (标准差/平均值 * 100%)
        if len(gc_counts) > 1:
            cv_gc = (np.std(gc_counts) / np.mean(gc_counts) * 100) if np.mean(gc_counts) > 0 else 0
            cv_pause = (np.std(pause_times) / np.mean(pause_times) * 100) if np.mean(pause_times) > 0 else 0
            cv_max_pause = (np.std(max_pause_times) / np.mean(max_pause_times) * 100) if np.mean(max_pause_times) > 0 else 0

            cv_gc_counts.append(cv_gc)
            cv_pause_times.append(cv_pause)
            cv_max_pause_times.append(cv_max_pause)

    # 只处理有数据的JDK版本
    valid_indices = [i for i in range(len(jdk_versions)) if i < len(cv_gc_counts) and i < len(cv_pause_times)]
    
    if valid_indices:
        valid_jdks = [jdk_versions[i] for i in valid_indices]
        x = np.arange(len(valid_jdks))
        width = 0.25

        bars1 = ax1.bar(x - width, [cv_gc_counts[i] for i in valid_indices], width, label='GC Count', color='#FF6B6B', alpha=0.8)
        bars2 = ax1.bar(x, [cv_pause_times[i] for i in valid_indices], width, label='Pause Time', color='#4ECDC4', alpha=0.8)
        bars3 = ax1.bar(x + width, [cv_max_pause_times[i] for i in valid_indices], width, label='Max Pause Time', color='#45B7D1', alpha=0.8)

        ax1.set_xlabel('JDK Version', fontsize=12)
        ax1.set_ylabel('Coefficient of Variation (%)', fontsize=12)
        ax1.set_title('CV Comparison Across JDK Versions', fontsize=13, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels([jdk.upper() for jdk in valid_jdks])
        ax1.legend(loc='best', fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')
        
        # 添加数值标签
        for bars in [bars1, bars2, bars3]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
    else:
        ax1.text(0.5, 0.5, 'No Data Available', transform=ax1.transAxes, ha='center', va='center', fontsize=12)
        ax1.set_title('CV Comparison Across JDK Versions', fontsize=13, fontweight='bold')

    # 波动性评估雷达图（只处理有数据的JDK版本）
    if valid_indices and len(cv_gc_counts) > 0 and len(cv_pause_times) > 0 and len(cv_max_pause_times) > 0:
        categories = ['GC Count', 'Pause Time', 'Max Pause']
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]

        fig_radar = plt.figure(figsize=(8, 8))
        ax_radar = fig_radar.add_subplot(111, projection='polar')

        for i, (jdk, color) in enumerate(zip(valid_jdks, [JDK_COLOR_LIST[idx] for idx in valid_indices])):
            values = []
            if i < len(cv_gc_counts):
                values.append(cv_gc_counts[i])
            else:
                values.append(0)
            if i < len(cv_pause_times):
                values.append(cv_pause_times[i])
            else:
                values.append(0)
            if i < len(cv_max_pause_times):
                values.append(cv_max_pause_times[i])
            else:
                values.append(0)

            values += values[:1]
            ax_radar.plot(angles, values, 'o-', linewidth=2, label=jdk.upper(), color=color)
            ax_radar.fill(angles, values, alpha=0.15, color=color)

        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(categories, fontsize=11)
        max_values = []
        if cv_gc_counts: max_values.append(max(cv_gc_counts))
        if cv_pause_times: max_values.append(max(cv_pause_times))
        if cv_max_pause_times: max_values.append(max(cv_max_pause_times))
        radar_max = max(max_values) * 1.2 if max_values else 100
        ax_radar.set_ylim(0, radar_max)
        ax_radar.set_title('Volatility Assessment Radar Chart', fontsize=13, fontweight='bold', pad=20)
        ax_radar.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        ax_radar.grid(True, alpha=0.3)
    else:
        fig_radar = plt.figure(figsize=(8, 8))
        ax_radar = fig_radar.add_subplot(111, projection='polar')
        ax_radar.text(0.5, 0.5, 'No Data Available', transform=ax_radar.transAxes, ha='center', va='center', fontsize=12)
        ax_radar.set_title('Volatility Assessment Radar Chart', fontsize=13, fontweight='bold', pad=20)

    plt.tight_layout()
    output_file = os.path.join(output_dir, 'coefficient_of_variation.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存变异系数分析图: {output_file}")
    plt.close()


def plot_jdk_comparison(data, jdk_versions, output_dir, gc_type):
    """绘制JDK版本性能对比图"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'{gc_type} - JDK Version Performance Comparison', fontsize=16, fontweight='bold')

    # 计算各版本的平均值
    avg_gc_counts = []
    avg_pause_times = []
    avg_max_pause_times = []

    for jdk in jdk_versions:
        gc_counts = []
        pause_times = []
        max_pause_times = []

        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            max_pause = row.get(f"{jdk}_Max_Pause_ms", "")

            if gc_count:
                gc_counts.append(float(gc_count))
            if pause_time:
                pause_times.append(float(pause_time))
            if max_pause:
                max_pause_times.append(float(max_pause))

        avg_gc_counts.append(np.mean(gc_counts) if gc_counts else 0)
        avg_pause_times.append(np.mean(pause_times) if pause_times else 0)
        avg_max_pause_times.append(np.mean(max_pause_times) if max_pause_times else 0)

    # 平均GC次数对比
    ax1 = axes[0, 0]
    colors = JDK_COLOR_LIST
    bars = ax1.bar([jdk.upper() for jdk in jdk_versions], avg_gc_counts, color=colors, alpha=0.8, edgecolor='black')
    ax1.set_ylabel('Average GC Count', fontsize=12)
    ax1.set_title('Average GC Count by JDK Version', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')

    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=10)

    # 平均暂停时间对比
    ax2 = axes[0, 1]
    bars = ax2.bar([jdk.upper() for jdk in jdk_versions], avg_pause_times, color=colors, alpha=0.8, edgecolor='black')
    ax2.set_ylabel('Average Pause Time (ms)', fontsize=12)
    ax2.set_title('Average Pause Time by JDK Version', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')

    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=10)

    # 相对性能变化（以JDK17为基准）
    ax3 = axes[1, 0]
    baseline_gc = avg_gc_counts[0]
    baseline_pause = avg_pause_times[0]

    gc_changes = [(val - baseline_gc) / baseline_gc * 100 if baseline_gc > 0 else 0
                  for val in avg_gc_counts]
    pause_changes = [(val - baseline_pause) / baseline_pause * 100 if baseline_pause > 0 else 0
                    for val in avg_pause_times]

    x = np.arange(len(jdk_versions))
    width = 0.35

    bars1 = ax3.bar(x - width/2, gc_changes, width, label='GC Count Change', color='#FF6B6B', alpha=0.8)
    bars2 = ax3.bar(x + width/2, pause_changes, width, label='Pause Time Change', color='#4ECDC4', alpha=0.8)

    ax3.set_ylabel('Change (%)', fontsize=12)
    ax3.set_title('Relative Performance Change (vs JDK17)', fontsize=13, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels([jdk.upper() for jdk in jdk_versions])
    ax3.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax3.legend(loc='best', fontsize=10)
    ax3.grid(True, alpha=0.3, axis='y')

    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:+.1f}%', ha='center', va='bottom' if height > 0 else 'top', fontsize=9)

    # 性能雷达图
    ax4 = axes[1, 1]
    categories = ['GC Count', 'Pause Time', 'Max Pause']

    # 归一化数据
    normalized_gc = [(val / max(avg_gc_counts) * 100) if max(avg_gc_counts) > 0 else 0
                     for val in avg_gc_counts]
    normalized_pause = [(val / max(avg_pause_times) * 100) if max(avg_pause_times) > 0 else 0
                       for val in avg_pause_times]
    normalized_max = [(val / max(avg_max_pause_times) * 100) if max(avg_max_pause_times) > 0 else 0
                      for val in avg_max_pause_times]

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        values = []
        idx = jdk_versions.index(jdk)
        values.extend([normalized_gc[idx], normalized_pause[idx], normalized_max[idx]])
        values += values[:1]

        ax4.plot(angles, values, 'o-', linewidth=2, label=jdk.upper(), color=color)
        ax4.fill(angles, values, alpha=0.15, color=color)

    ax4.set_xticks(angles[:-1])
    ax4.set_xticklabels(categories, fontsize=11)
    ax4.set_ylim(0, 100)
    ax4.set_title('Normalized Performance Radar', fontsize=13, fontweight='bold')
    ax4.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = os.path.join(output_dir, 'jdk_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存JDK版本对比图: {output_file}")
    plt.close()


def plot_probability_distribution(data, jdk_versions, output_dir, gc_type):
    """绘制概率分布图（密度图）"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'{gc_type} - Probability Distribution Analysis', fontsize=16, fontweight='bold')

    # GC次数密度图
    ax1 = axes[0, 0]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))

        if gc_counts:
            try:
                from scipy.stats import gaussian_kde
                density = gaussian_kde(gc_counts)
                xs = np.linspace(min(gc_counts) - 2, max(gc_counts) + 2, 200)
                ax1.plot(xs, density(xs), linewidth=2, label=jdk.upper(), color=color)
                ax1.fill_between(xs, 0, density(xs), alpha=0.2, color=color)
            except np.linalg.LinAlgError:
                # 如果KDE失败，绘制简单的直方图
                ax1.hist(gc_counts, bins=10, alpha=0.7, color=color, edgecolor='black', 
                        label=f'{jdk.upper()} (histogram)', density=True)
                ax1.axvline(np.mean(gc_counts), color=color, linestyle='--', alpha=0.7, 
                           label=f'{jdk.upper()} mean')

    ax1.set_xlabel('GC Count', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.set_title('GC Count Probability Distribution', fontsize=13, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 暂停时间密度图
    ax2 = axes[0, 1]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))

        if pause_times:
            try:
                from scipy.stats import gaussian_kde
                density = gaussian_kde(pause_times)
                xs = np.linspace(min(pause_times) * 0.9, max(pause_times) * 1.1, 200)
                ax2.plot(xs, density(xs), linewidth=2, label=jdk.upper(), color=color)
                ax2.fill_between(xs, 0, density(xs), alpha=0.2, color=color)
            except np.linalg.LinAlgError:
                # 如果KDE失败，绘制简单的直方图
                ax2.hist(pause_times, bins=10, alpha=0.7, color=color, edgecolor='black', 
                        label=f'{jdk.upper()} (histogram)', density=True)
                ax2.axvline(np.mean(pause_times), color=color, linestyle='--', alpha=0.7, 
                           label=f'{jdk.upper()} mean')

    ax2.set_xlabel('Pause Time (ms)', fontsize=12)
    ax2.set_ylabel('Probability Density', fontsize=12)
    ax2.set_title('Pause Time Probability Distribution', fontsize=13, fontweight='bold')
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # GC次数累积分布函数
    ax3 = axes[1, 0]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))

        if gc_counts:
            sorted_gc = sorted(gc_counts)
            y = np.arange(len(sorted_gc)) / len(sorted_gc)
            ax3.plot(sorted_gc, y, 'o-', linewidth=2, label=jdk.upper(), color=color, markersize=6)

    ax3.set_xlabel('GC Count', fontsize=12)
    ax3.set_ylabel('Cumulative Probability', fontsize=12)
    ax3.set_title('GC Count CDF', fontsize=13, fontweight='bold')
    ax3.legend(loc='best', fontsize=10)
    ax3.grid(True, alpha=0.3)

    # 暂停时间累积分布函数
    ax4 = axes[1, 1]
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))

        if pause_times:
            sorted_pause = sorted(pause_times)
            y = np.arange(len(sorted_pause)) / len(sorted_pause)
            ax4.plot(sorted_pause, y, 'o-', linewidth=2, label=jdk.upper(), color=color, markersize=6)

    ax4.set_xlabel('Pause Time (ms)', fontsize=12)
    ax4.set_ylabel('Cumulative Probability', fontsize=12)
    ax4.set_title('Pause Time CDF', fontsize=13, fontweight='bold')
    ax4.legend(loc='best', fontsize=10)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = os.path.join(output_dir, 'probability_distribution.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存概率分布图: {output_file}")
    plt.close()


def plot_summary_dashboard(data, jdk_versions, output_dir, gc_type):
    """生成汇总仪表板"""
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    fig.suptitle(f'{gc_type} Probabilistic Behavior Analysis Dashboard', fontsize=20, fontweight='bold')

    # 1. GC次数趋势
    ax1 = fig.add_subplot(gs[0, :2])
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))
        ax1.plot(range(1, len(gc_counts) + 1), gc_counts,
                marker='o', label=jdk.upper(), color=color, linewidth=2, markersize=8)
    ax1.set_xlabel('Run Number', fontsize=12)
    ax1.set_ylabel('GC Count', fontsize=12)
    ax1.set_title('GC Count Trend', fontsize=13, fontweight='bold')
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 2. 暂停时间趋势
    ax2 = fig.add_subplot(gs[0, 2:])
    for jdk, color in zip(jdk_versions, JDK_COLOR_LIST):
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))
        ax2.plot(range(1, len(pause_times) + 1), pause_times,
                marker='o', label=jdk.upper(), color=color, linewidth=2, markersize=8)
    ax2.set_xlabel('Run Number', fontsize=12)
    ax2.set_ylabel('Pause Time (ms)', fontsize=12)
    ax2.set_title('Pause Time Trend', fontsize=13, fontweight='bold')
    ax2.legend(loc='best', fontsize=10)
    ax2.grid(True, alpha=0.3)

    # 3. GC次数箱线图
    ax3 = fig.add_subplot(gs[1, :2])
    box_data = []
    for jdk in jdk_versions:
        gc_counts = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            if gc_count:
                gc_counts.append(float(gc_count))
        box_data.append(gc_counts)

    bp = ax3.boxplot(box_data, labels=[jdk.upper() for jdk in jdk_versions],
                     patch_artist=True, notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], JDK_COLOR_LIST):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax3.set_ylabel('GC Count', fontsize=12)
    ax3.set_title('GC Count Distribution', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    # 4. 暂停时间箱线图
    ax4 = fig.add_subplot(gs[1, 2:])
    box_data = []
    for jdk in jdk_versions:
        pause_times = []
        for row in data:
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if pause_time:
                pause_times.append(float(pause_time))
        box_data.append(pause_times)

    bp = ax4.boxplot(box_data, labels=[jdk.upper() for jdk in jdk_versions],
                     patch_artist=True, notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], JDK_COLOR_LIST):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax4.set_ylabel('Pause Time (ms)', fontsize=12)
    ax4.set_title('Pause Time Distribution', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)

    # 5. 变异系数对比
    ax5 = fig.add_subplot(gs[2, :2])
    cv_gc_counts = []
    cv_pause_times = []

    for jdk in jdk_versions:
        gc_counts = []
        pause_times = []
        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            if gc_count:
                gc_counts.append(float(gc_count))
            if pause_time:
                pause_times.append(float(pause_time))

        cv_gc = (np.std(gc_counts) / np.mean(gc_counts) * 100) if np.mean(gc_counts) > 0 and len(gc_counts) > 1 else 0
        cv_pause = (np.std(pause_times) / np.mean(pause_times) * 100) if np.mean(pause_times) > 0 and len(pause_times) > 1 else 0

        cv_gc_counts.append(cv_gc)
        cv_pause_times.append(cv_pause)

    x = np.arange(len(jdk_versions))
    width = 0.35

    bars1 = ax5.bar(x - width/2, cv_gc_counts, width, label='GC Count', color='#FF6B6B', alpha=0.8)
    bars2 = ax5.bar(x + width/2, cv_pause_times, width, label='Pause Time', color='#4ECDC4', alpha=0.8)

    ax5.set_xlabel('JDK Version', fontsize=12)
    ax5.set_ylabel('Coefficient of Variation (%)', fontsize=12)
    ax5.set_title('Volatility Assessment (CV)', fontsize=13, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels([jdk.upper() for jdk in jdk_versions])
    ax5.legend(loc='best', fontsize=10)
    ax5.grid(True, alpha=0.3, axis='y')

    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom', fontsize=9)

    # 6. 统计摘要
    ax6 = fig.add_subplot(gs[2, 2:])
    ax6.axis('off')

    # 计算统计摘要
    summary_text = "Statistical Summary\n"
    summary_text += "=" * 50 + "\n\n"

    for jdk in jdk_versions:
        gc_counts = []
        pause_times = []
        max_pause_times = []

        for row in data:
            gc_count = row.get(f"{jdk}_GC_Count", "")
            pause_time = row.get(f"{jdk}_Pause_Time_ms", "")
            max_pause = row.get(f"{jdk}_Max_Pause_ms", "")

            if gc_count:
                gc_counts.append(float(gc_count))
            if pause_time:
                pause_times.append(float(pause_time))
            if max_pause:
                max_pause_times.append(float(max_pause))

        if gc_counts:
            summary_text += f"{jdk.upper()}:\n"
            summary_text += f"  GC Count: {np.mean(gc_counts):.1f} ± {np.std(gc_counts):.1f}\n"
            summary_text += f"  Pause Time: {np.mean(pause_times):.3f} ± {np.std(pause_times):.3f} ms\n"
            summary_text += f"  Max Pause: {np.mean(max_pause_times):.3f} ± {np.std(max_pause_times):.3f} ms\n"
            summary_text += f"  CV (GC): {(np.std(gc_counts)/np.mean(gc_counts)*100 if np.mean(gc_counts)>0 else 0):.2f}%\n"
            summary_text += f"  CV (Pause): {(np.std(pause_times)/np.mean(pause_times)*100 if np.mean(pause_times)>0 else 0):.2f}%\n\n"

    ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes,
            fontsize=10, verticalalignment='top', family='monospace')

    # 输出统计摘要到控制台
    print("\n统计摘要:")
    print(summary_text)

    output_file = os.path.join(output_dir, 'summary_dashboard.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ 保存汇总仪表板: {output_file}")
    plt.close()


def generate_all_charts(start_run, end_run, gc_type=None):
    """生成所有图表"""
    script_dir = Path(__file__).parent
    
    if gc_type:
        # 指定了GC类型，优先使用该类型的CSV文件（先在当前目录查找，再到results目录查找）
        csv_file = script_dir / f"{gc_type.lower()}_test_summary.csv"
        if not csv_file.exists():
            csv_file = script_dir / "results" / f"{gc_type.lower()}_test_summary.csv"
    else:
        # 尝试自动检测GC类型文件
        summary_files = [
            "zgc_test_summary.csv",
            "g1gc_test_summary.csv", 
            "parallel_test_summary.csv",
            "serial_test_summary.csv",
            "shenandoah_test_summary.csv"
        ]
        csv_file = None
        for filename in summary_files:
            # 先在当前目录查找
            test_file = script_dir / filename
            if test_file.exists():
                csv_file = test_file
                break
            # 再到results目录查找
            test_file = script_dir / "results" / filename
            if test_file.exists():
                csv_file = test_file
                break
        
        if not csv_file:
            print("错误: 未找到任何GC汇总文件")
            print("请确保CSV文件在以下位置之一:")
            print("  - ./zgc_test_summary.csv")
            print("  - ./g1gc_test_summary.csv")
            print("  - ./results/zgc_test_summary.csv")  
            print("  - ./results/g1gc_test_summary.csv")
            return

    if not csv_file.exists():
        print(f"错误: 汇总文件不存在: {csv_file}")
        print("请先运行批量测试脚本")
        return

    data = load_summary_data(csv_file)
    
    # 确定实际使用的GC类型
    actual_gc_type = gc_type or get_gc_type_from_csv(csv_file)
    
    jdk_versions = ["jdk17", "jdk21", "jdk25", "jdk26"]

    # 创建输出目录（输出到results/charts目录）
    output_dir = script_dir / "results" / "charts" / actual_gc_type.lower() / f"run{start_run}-{end_run}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"开始生成{actual_gc_type}图表...")
    print(f"数据范围: 第{start_run}到第{end_run}次运行")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    # 生成各种图表
    plot_gc_count_distribution(data, jdk_versions, output_dir, actual_gc_type)
    plot_pause_time_distribution(data, jdk_versions, output_dir, actual_gc_type)
    plot_coefficient_of_variation(data, jdk_versions, output_dir, actual_gc_type)
    plot_jdk_comparison(data, jdk_versions, output_dir, actual_gc_type)
    plot_probability_distribution(data, jdk_versions, output_dir, actual_gc_type)
    plot_summary_dashboard(data, jdk_versions, output_dir, actual_gc_type)

    print("=" * 60)
    print(f"✓ 所有图表生成完成!")
    print(f"图表保存在: {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) == 4:
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        gc_type = sys.argv[3]
        generate_all_charts(start, end, gc_type)
    elif len(sys.argv) == 3:
        start = int(sys.argv[1])
        end = int(sys.argv[2])
        generate_all_charts(start, end)
    else:
        print("用法: python3 generate_zgc_charts.py <起始次数> <结束次数> [GC类型]")
        print("示例:")
        print("  python3 generate_zgc_charts.py 1 10")
        print("  python3 generate_zgc_charts.py 1 10 G1GC")
        print("  python3 generate_zgc_charts.py 1 10 Shenandoah")
        print("\n可用GC类型: ZGC, G1GC, Parallel, Serial, Shenandoah")
        print("\n依赖安装:")
        print("  pip3 install matplotlib numpy scipy")
        sys.exit(1)
