#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简历结构化专家 Agent 测试工程 - 主入口

支持命令行参数，适用于CI场景
实现SOP4多轮复测防抖降噪和SOP6版本对比防抖阈值
"""

import argparse
import sys
from typing import List
from config import TEST_CONFIG
from src.test_case_loader import TestCaseLoader
from src.test_executor import TestExecutor
from src.report_generator import ReportGenerator


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description="简历结构化专家 Agent 测试工具")
    parser.add_argument(
        "-c", "--case-file", 
        default=TEST_CONFIG["test_case_file"],
        help="测试用例Excel文件路径"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=TEST_CONFIG["output_dir"],
        help="报告输出目录"
    )
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8000/api/resume/parse",
        help="Agent API地址"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=TEST_CONFIG["fail_fast"],
        help="遇到失败立即停止"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=TEST_CONFIG["max_retries"],
        help="失败重试次数"
    )
    parser.add_argument(
        "--repeat-count",
        type=int,
        default=TEST_CONFIG.get("repeat_count", 3),
        help="SOP4: 单例重复执行次数（多轮复测防抖降噪）"
    )
    parser.add_argument(
        "--jitter-threshold",
        type=float,
        default=TEST_CONFIG.get("jitter_threshold", 1.0),
        help="SOP4: 抖动率阈值（%），超过则判定环境异常"
    )
    parser.add_argument(
        "--report-format",
        choices=["html", "markdown", "json", "all"],
        default="all",
        help="报告格式"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="详细输出模式"
    )
    return parser.parse_args()


def main():
    """
    主函数
    """
    args = parse_args()

    print("=" * 60)
    print("简历结构化专家 Agent 测试工程")
    print("=" * 60)
    print(f"测试用例文件: {args.case_file}")
    print(f"输出目录: {args.output_dir}")
    print(f"Agent地址: {args.agent_url}")
    print(f"fail-fast模式: {'开启' if args.fail_fast else '关闭'}")
    print(f"重试次数: {args.retries}")
    print(f"SOP4-重复次数: {args.repeat_count}")
    print(f"SOP4-抖动阈值: {args.jitter_threshold}%")
    print(f"SOP6-波动阈值: {TEST_CONFIG.get('fluctuation_threshold', 1.0)}%")
    print("=" * 60)

    # 加载测试用例
    loader = TestCaseLoader(args.case_file)
    test_cases = loader.load_cases()

    if not test_cases:
        print("[ERROR] 未加载到任何测试用例")
        sys.exit(1)

    # 执行测试
    executor = TestExecutor()
    results = []
    env_errors = []  # 记录环境异常
    
    for case in test_cases:
        result = executor.execute_case(case)
        results.append(result)
        
        # SOP4: 记录环境异常
        if result["status"] == "error":
            env_errors.append(case["id"])
        
        if args.fail_fast and result["status"] == "failed":
            print("[INFO] fail-fast模式已开启，遇到失败立即停止")
            break

    # 生成报告
    print("\n[INFO] 生成测试报告...")
    generator = ReportGenerator(args.output_dir)
    generator.generate(results)

    # 输出测试汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "error")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"测试总数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"环境异常: {errors}")
    print(f"跳过: {skipped}")
    print(f"通过率: {pass_rate:.1f}%")
    
    # SOP4: 输出抖动率统计
    jitter_rates = [r.get("jitter_rate", 0) for r in results]
    if jitter_rates:
        avg_jitter = sum(jitter_rates) / len(jitter_rates)
        max_jitter = max(jitter_rates)
        print(f"平均抖动率: {avg_jitter:.2f}%")
        print(f"最大抖动率: {max_jitter:.2f}%")
    
    print("=" * 60)

    # 返回退出码
    if errors > 0:
        print(f"[ERROR] 环境异常！{len(env_errors)}个用例抖动率超标: {', '.join(env_errors)}")
        sys.exit(2)
    elif failed > 0:
        print("[ERROR] 测试失败！")
        sys.exit(1)
    else:
        print("[SUCCESS] 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
