#!/bin/bash
set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RUNTEST="$SCRIPT_DIR/RunTestHere"
TESTCASES_DIR="$SCRIPT_DIR/testcases"
REQUIRED_JDK_VERSIONS=("11" "17" "21" "25" "26")
DIFF_TIMEOUT=300  # 差分测试超时时间（秒）

# 8个主要测试集
MAIN_TESTSUITS=("HotSpot" "OpenJ9" "core" "eclipse" "fop" "jdkissues" "leetcode" "unittests")

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 命令未找到，请先安装"
        return 1
    fi
    return 0
}

# 检查 jenv 环境
check_jenv() {
    log_info "检查 jenv 环境..."
    
    # 检查 jenv 是否安装
    if ! check_command "jenv"; then
        log_error "请先安装 jenv: brew install jenv"
        exit 1
    fi
    
    log_success "jenv 已安装: $(jenv --version)"
    
    # 检查必需的 JDK 版本
    local missing_versions=()
    local available_versions=()
    
    # 获取 jenv 中可用的版本
    while IFS= read -r version; do
        available_versions+=("$version")
    done < <(jenv versions | grep -oE '^[[:space:]]*[0-9]+' | sed 's/^[[:space:]]*//')
    
    # 检查每个必需版本
    for req_version in "${REQUIRED_JDK_VERSIONS[@]}"; do
        local found=false
        for avail_version in "${available_versions[@]}"; do
            if [[ "$avail_version" == "$req_version" ]]; then
                found=true
                break
            fi
        done
        
        if [ "$found" = false ]; then
            missing_versions+=("$req_version")
        fi
    done
    
    # 显示结果
    if [ ${#missing_versions[@]} -eq 0 ]; then
        log_success "所有必需的 JDK 版本都已配置: ${REQUIRED_JDK_VERSIONS[*]}"
    else
        log_error "缺少以下 JDK 版本: ${missing_versions[*]}"
        log_info "当前可用版本: ${available_versions[*]}"
        log_info "请安装缺少的 JDK 版本，例如:"
        for version in "${missing_versions[@]}"; do
            echo "  jenv add \$(brew --prefix openjdk)@${version}"
        done
        exit 1
    fi
}

# 检查测试集
check_testcases() {
    log_info "检查测试集目录..."
    
    if [ ! -d "$TESTCASES_DIR" ]; then
        log_error "测试集目录不存在: $TESTCASES_DIR"
        exit 1
    fi
    
    local missing_testsuits=()
    
    # 检查每个主要测试集
    for testsuit in "${MAIN_TESTSUITS[@]}"; do
        local testsuit_path="$TESTCASES_DIR/$testsuit"
        if [ ! -d "$testsuit_path" ]; then
            missing_testsuits+=("$testsuit")
        else
            # 检查是否有 classHistory 或 diffClasses 子目录
            local has_content=false
            if [ -d "$testsuit_path/classHistory" ] || [ -d "$testsuit_path/diffClasses" ]; then
                has_content=true
            fi
            
            if [ "$has_content" = false ]; then
                log_warning "测试集 $testsuit 存在但缺少测试内容 (classHistory/diffClasses)"
                missing_testsuits+=("$testsuit(空)")
            else
                log_success "测试集 $testsuit 检查通过"
            fi
        fi
    done
    
    if [ ${#missing_testsuits[@]} -gt 0 ]; then
        log_error "以下测试集缺失或为空: ${missing_testsuits[*]}"
        exit 1
    fi
    
    log_success "所有 ${#MAIN_TESTSUITS[@]} 个主要测试集检查通过"
}

# 快速测试每个测试集
quick_test_suits() {
    log_info "开始快速测试所有测试集 (超时: 10秒)..."
    
    local failed_tests=()
    
    for testsuit in "${MAIN_TESTSUITS[@]}"; do
        echo
        log_info "测试集: $testsuit"
        local test_dir="$TESTCASES_DIR/$testsuit"
        
        if [ -n "$test_dir" ]; then
            log_info "  正在测试: $test_dir"
            
            # 创建临时测试目录
            local temp_test_dir="/tmp/quick_test_${testsuit}_$$"
            mkdir -p "$temp_test_dir"
            log_info "  临时目录: $temp_test_dir"
            
            # 使用 TestRun.py 进行快速测试，并捕获退出码
            cd "$RUNTEST"
            (timeout 10s python3 -u ../src/TestRun.py "$test_dir" > "$temp_test_dir/output.log") || true
            # 检查实际是否成功（查看日志中的成功率）
            local success_count=$(grep -c "SUCCESS" "$temp_test_dir/output.log" 2>/dev/null || echo "0")
            local total_count=$(grep -c "Testing:" "$temp_test_dir/output.log" 2>/dev/null || echo "0")
            
            # 修改这里：只要有SUCCESS就算成功，不检查timeout的退出状态
            if [ "$success_count" -gt 0 ]; then
                # 有成功案例，测试通过
                if [ "$total_count" -gt 0 ]; then
                    local success_rate=$((success_count * 100 / total_count))
                    log_success "  ✓ $testsuit 测试通过 ($success_count/$total_count, ${success_rate}%)"
                else
                    log_success "  ✓ $testsuit 测试通过 (有成功案例)"
                fi
            else
                # 没有成功案例
                if [ "$total_count" -gt 0 ]; then
                    log_error "  ✗ $testsuit 测试失败 (运行了 $total_count 个测试，但无成功案例)"
                else
                    log_error "  ✗ $testsuit 测试失败 (无成功的测试用例)"
                fi
                failed_tests+=("$testsuit")
            fi
            
            # 清理临时目录
            rm -rf "$temp_test_dir"
            
        else
            log_warning "  ⚠ $testsuit 没有可测试的内容"
            failed_tests+=("$testsuit(无内容)")
        fi
    done
    
    echo
    if [ ${#failed_tests[@]} -eq 0 ]; then
        log_success "所有测试集快速检查通过！"
    else
        log_error "以下测试集测试失败: ${failed_tests[*]}"
        log_info "请检查这些测试集的配置或内容"
        exit 1
    fi
}

# 询问是否保留 GC 日志
ask_gc_logs() {
    echo
    while true; do
        read -p "是否保留 GC 日志文件？这将占用大量磁盘空间 (y/n): " yn
        case $yn in
            [Yy]* )
                echo "y"
                return 0
                ;;
            [Nn]* )
                echo "n"
                return 0
                ;;
            * )
                echo "请回答 y 或 n"
                ;;
        esac
    done
}

# 创建输出目录
create_output_dir() {
    local timestamp=$(date +%Y%m%d)
    local output_dir="$PROJECT_ROOT/results/$timestamp"
    
    echo "$output_dir"
}

# 执行差分测试
run_differential_test() {
    local output_dir="$1"
    local keep_gc_logs="$2"
    
    log_info "开始执行差分测试..."
    log_info "输出目录: $output_dir"
    log_info "超时设置: ${DIFF_TIMEOUT}秒"
    log_info "GC日志保留: $([ "$keep_gc_logs" = "y" ] && echo "是" || echo "否")"
    
    
    # 构建命令行参数
    local args=("$TESTCASES_DIR" "$output_dir" "-t" "$DIFF_TIMEOUT")
    if [ "$keep_gc_logs" = "y" ]; then
        args+=("--keep-gc-logs")
    fi
    
    cd "$RUNTEST"
    
    log_info "执行命令: python3 Executor.py ${args[*]}"
    
    # 执行差分测试
    if python3 ../src/Executor.py "${args[@]}"; then
        log_success "差分测试完成！"
        log_info "结果保存在: $output_dir"
        
        # 显示测试结果统计
        if [ -f "$output_dir/report.json" ]; then
            echo
            log_info "测试结果摘要:"
            python3 -c "
import json
with open('$output_dir/report.json', 'r') as f:
    data = json.load(f)
    if 'summary' in data:
        summary = data['summary']
        print(f'  总测试数: {summary.get(\"total\", 0)}')
        print(f'  成功数: {summary.get(\"successful\", 0)}')
        print(f'  失败数: {summary.get(\"failed\", 0)}')
        print(f'  成功率: {summary.get(\"success_rate\", 0):.2f}%')
"
        else
            log_warning "未找到测试报告文件"
        fi
    else
        log_error "差分测试执行失败"
        # 清理临时目录
        rm -rf "$temp_exec_dir"
        exit 1
    fi
    
    # 清理临时目录
    rm -rf "$temp_exec_dir"
}

# 主函数
main() {
    echo "=========================================="
    echo "    Java GC 测试框架启动脚本"
    echo "=========================================="
    echo
    
    # 显示环境信息
    log_info "项目根目录: $PROJECT_ROOT"
    log_info "RunEnv 目录: $SCRIPT_DIR"
    log_info "测试用例目录: $TESTCASES_DIR"
    echo
    
    # 1. 检查 jenv 环境
    check_jenv
    echo
    
    # 2. 检查测试集
    check_testcases
    echo
    
    # 3. 快速测试所有测试集
    quick_test_suits
    echo
    
    # 4. 询问是否保留 GC 日志
    local keep_gc_logs=$(ask_gc_logs)
    keep_gc_logs=${keep_gc_logs//[$'\r\n']} 
    echo
    
    # 5. 创建输出目录
    local output_dir=$(create_output_dir)
    echo
    
    # 6. 执行差分测试
    run_differential_test "$output_dir" "$keep_gc_logs"
    
    echo
    log_success "所有测试完成！"
    echo "=========================================="
}

# 信号处理
trap 'log_warning "脚本被中断"; exit 1' INT TERM

# 运行主函数
main "$@"
