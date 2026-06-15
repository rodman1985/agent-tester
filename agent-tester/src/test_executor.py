"""
测试执行器模块
负责执行测试用例并进行判决
"""

import time
import re
import statistics
from datetime import datetime
from typing import Dict, Any, List
from config import TEST_CONFIG, MODULES, BASIC_FIELDS
from src.agent_client import invoke_agent


class TestExecutor:
    """测试执行器"""

    def __init__(self):
        self.max_retries = TEST_CONFIG["max_retries"]
        self.retry_delay = TEST_CONFIG["retry_delay"]
        self.fail_fast = TEST_CONFIG["fail_fast"]
        # SOP4: 多轮复测防抖降噪配置
        self.repeat_count = TEST_CONFIG.get("repeat_count", 3)
        self.jitter_threshold = TEST_CONFIG.get("jitter_threshold", 1.0)

    def execute_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个测试用例（支持多轮复测防抖降噪）

        Args:
            case: 测试用例数据

        Returns:
            测试结果，包含Token消耗、推理延迟、执行步骤等指标
        """
        # SOP4: 单例重复执行多次
        results = []
        for repeat_idx in range(self.repeat_count):
            print(f"[INFO] 执行测试用例 [{case['id']}] {case['name']} (第{repeat_idx + 1}/{self.repeat_count}次)")
            
            result = {
                "id": case["id"],
                "name": case["name"],
                "description": case["description"],
                "status": "unknown",
                "start_time": "",
                "end_time": "",
                "duration_ms": 0,
                "input_preview": case["input_text"][:100],
                "result_summary": "",
                "raw_output": {},
                "expected_structured": case["expected_structured"],
                "expected_output": case["expected_output"],
                "judgment_rule": case["judgment_rule"],
                "fail_details": [],
                "actual_output": "",
                # 新增指标数据
                "metrics": {
                    "token_metrics": {},
                    "execution_metrics": {},
                    "latency_ms": 0,
                },
            }

            result["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            last_error = None
            for attempt in range(self.max_retries + 1):
                try:
                    start_ts = time.time()
                    agent_result = invoke_agent(case["input_text"], {"expected_structured": case.get("expected_structured", "")})
                    end_ts = time.time()

                    result["duration_ms"] = int((end_ts - start_ts) * 1000)
                    result["raw_output"] = agent_result
                    result["actual_output"] = agent_result.get("output", "")

                    # 收集指标数据
                    result["metrics"]["token_metrics"] = agent_result.get("token_metrics", {})
                    result["metrics"]["execution_metrics"] = agent_result.get("execution_metrics", {})
                    result["metrics"]["latency_ms"] = agent_result.get("latency_ms", 0)

                    if self._validate_response(agent_result):
                        judge_result = self._judge_result(agent_result, case)
                        result["status"] = judge_result["status"]
                        result["fail_details"] = judge_result.get("fail_details", [])
                        result["result_summary"] = self._generate_summary(judge_result)
                    else:
                        result["status"] = "failed"
                        result["fail_details"] = [{"field": "响应格式", "actual": "无效响应", "expected": "有效JSON响应"}]
                        result["result_summary"] = "Agent响应格式无效"

                    break

                except Exception as e:
                    last_error = str(e)
                    print(f"[WARNING] 测试用例 [{case['id']}] 执行失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {e}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)

            if last_error and result["status"] == "unknown":
                result["status"] = "failed"
                result["fail_details"] = [{"field": "执行异常", "actual": last_error, "expected": "正常执行"}]
                result["result_summary"] = f"执行异常: {last_error}"

            result["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results.append(result)
            
            if repeat_idx < self.repeat_count - 1:
                time.sleep(1)  # 各轮之间短暂间隔

        # SOP4: 多轮结果综合处理
        final_result = self._aggregate_repeat_results(results)
        return final_result

    def _aggregate_repeat_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        综合处理多轮执行结果（SOP4: 多轮复测防抖降噪）
        
        - 取量化指标的中位数
        - 采用"两次一致生效"原则判定最终状态
        - 检查抖动率，超过阈值则判定环境异常
        """
        if not results:
            return {
                "status": "error",
                "result_summary": "无有效执行结果",
                "fail_details": [{"field": "执行异常", "actual": "无执行结果", "expected": "至少一次成功执行"}],
            }

        # 提取各轮结果
        statuses = [r["status"] for r in results]
        latencies = [r["metrics"]["latency_ms"] for r in results if r["metrics"]["latency_ms"] > 0]
        total_tokens_list = [r["metrics"]["token_metrics"].get("total_tokens", 0) for r in results]
        outputs = [r["actual_output"] for r in results]

        # SOP4: 计算抖动率
        jitter_rate = self._calculate_jitter_rate(outputs)
        if jitter_rate > self.jitter_threshold:
            # 抖动率超过阈值，判定环境异常
            return {
                "status": "error",
                "result_summary": f"环境异常：单用例抖动率{jitter_rate:.2f}% > 阈值{self.jitter_threshold}%",
                "fail_details": [{"field": "环境抖动", "actual": f"抖动率{jitter_rate:.2f}%", "expected": f"≤{self.jitter_threshold}%"}],
                "jitter_rate": jitter_rate,
                **results[0],  # 保留第一轮的基础信息
            }

        # SOP4: 采用"两次一致生效"原则判定最终状态
        passed_count = statuses.count("passed")
        if passed_count >= 2:
            final_status = "passed"
        else:
            final_status = "failed"

        # SOP4: 取量化指标的中位数
        final_latency = statistics.median(latencies) if latencies else 0
        final_total_tokens = int(statistics.median([t for t in total_tokens_list if t > 0])) if any(t > 0 for t in total_tokens_list) else 0

        # 构建最终结果（基于第一轮结果，更新汇总指标）
        final_result = results[0].copy()
        final_result["status"] = final_status
        final_result["metrics"]["latency_ms"] = final_latency
        final_result["metrics"]["token_metrics"]["total_tokens"] = final_total_tokens
        final_result["repeat_count"] = len(results)
        final_result["pass_count"] = passed_count
        final_result["jitter_rate"] = jitter_rate
        
        # 更新结果摘要
        final_result["result_summary"] = f"多轮执行结果: {passed_count}/{len(results)} 通过, 抖动率: {jitter_rate:.2f}%, 中位延迟: {final_latency:.2f}ms"

        return final_result

    def _calculate_jitter_rate(self, outputs: List[str]) -> float:
        """
        计算输出结果的抖动率（基于字符级别的差异）
        """
        if len(outputs) < 2:
            return 0.0

        # 以第一个输出为基准，计算与其他输出的差异率
        base_output = outputs[0]
        total_chars = len(base_output)
        if total_chars == 0:
            return 0.0

        total_diff = 0
        for output in outputs[1:]:
            # 计算编辑距离（简化版本：只统计不同字符数）
            min_len = min(len(base_output), len(output))
            diff_count = sum(1 for i in range(min_len) if base_output[i] != output[i])
            diff_count += abs(len(base_output) - len(output))
            total_diff += diff_count

        avg_diff = total_diff / (len(outputs) - 1)
        jitter_rate = (avg_diff / total_chars) * 100
        return jitter_rate

    def _validate_response(self, response: Dict[str, Any]) -> bool:
        """
        验证Agent响应是否有效
        """
        if not isinstance(response, dict):
            return False
        if "success" not in response:
            return False
        if "output" not in response:
            return False
        return True

    def _judge_result(self, agent_result: Dict[str, Any], case: Dict[str, Any]) -> Dict[str, Any]:
        """
        判断测试结果，返回详细的状态和失败信息

        判决逻辑：
        - 参考E列（expected_structured）的结构化信息做比较
        - 如果E列未声明的模块/字段（即输入材料中不包含），实际结果也不包含的，视为符合预期
        - 只有当E列声明了某个模块/字段（字段名后有实际值），但实际结果不包含时，才判定为失败
        - 如果E列没有任何声明（所有字段都为空），则视为无有效信息场景
        """
        output = agent_result.get("output", "")
        expected_structured = case.get("expected_structured", "")
        expected_output = case.get("expected_output", "")
        
        fail_details = []

        # 分析E列中声明的模块（字段名后有实际值才算声明）
        declared_modules = [m for m in MODULES if self._is_field_declared(expected_structured, m)]
        
        # 分析E列中声明的基本信息字段
        declared_fields = [f for f in BASIC_FIELDS if self._is_field_declared(expected_structured, f)]

        # 特殊情况：无有效信息场景
        if len(declared_modules) == 0 and len(declared_fields) == 0:
            if expected_output:
                key_requirements = ["候选人未提供", "基本信息", "核心优势"]
                matched_count = sum(1 for req in key_requirements if req in output)
                if matched_count >= 2:
                    return {"status": "passed", "fail_details": []}
                else:
                    fail_details.append({
                        "field": "无有效信息场景处理",
                        "actual": f"仅匹配{matched_count}个关键要求",
                        "expected": "匹配至少2个关键要求（候选人未提供、基本信息、核心优势等）"
                    })
            else:
                return {"status": "passed", "fail_details": []}

        # 检查声明模块的完整性
        missing_modules = [m for m in declared_modules if m not in output]
        if missing_modules:
            fail_details.append({
                "field": "模块完整度",
                "actual": f"缺少声明模块: {', '.join(missing_modules)}",
                "expected": f"包含E列声明的模块: {', '.join(declared_modules)}"
            })

        # 检查声明字段的完整性
        missing_fields = [f for f in declared_fields if f not in output]
        if missing_fields:
            fail_details.append({
                "field": "基本信息字段",
                "actual": f"缺少声明字段: {', '.join(missing_fields)}",
                "expected": f"包含E列声明的字段: {', '.join(declared_fields)}"
            })

        # 检查输出长度
        if len(declared_modules) > 0 and len(output) < 100:
            fail_details.append({
                "field": "输出内容长度",
                "actual": f"{len(output)}字符",
                "expected": "至少100字符（结构化简历内容）"
            })

        # 检查预期输出
        if expected_output and expected_output not in output:
            if len(expected_output) > 100:
                expected_start = expected_output[:50]
                if expected_start not in output:
                    fail_details.append({
                        "field": "预期内容匹配",
                        "actual": "未包含预期内容的关键部分",
                        "expected": f"包含: {expected_start}..."
                    })
            else:
                fail_details.append({
                    "field": "预期内容匹配",
                    "actual": f"未包含预期内容: {expected_output}",
                    "expected": expected_output
                })

        if len(fail_details) == 0:
            return {"status": "passed", "fail_details": []}
        else:
            return {"status": "failed", "fail_details": fail_details}

    def _is_field_declared(self, expected_structured: str, field_name: str) -> bool:
        """
        判断E列中是否声明了某个字段（字段名后有实际值才算声明）
        """
        field_index = expected_structured.find(field_name)
        if field_index == -1:
            return False
        
        colon_index = expected_structured.find("：", field_index)
        if colon_index == -1:
            colon_index = expected_structured.find(":", field_index)
            if colon_index == -1:
                return False
        
        next_newline = expected_structured.find("\n", colon_index + 1)
        if next_newline == -1:
            value = expected_structured[colon_index + 1:].strip()
        else:
            value = expected_structured[colon_index + 1:next_newline].strip()
        
        return len(value) > 0

    def _generate_summary(self, judge_result: Dict[str, Any]) -> str:
        """
        生成结果摘要
        """
        fail_details = judge_result.get("fail_details", [])
        
        summary = {
            "status": judge_result.get("status", "unknown"),
            "fail_count": len(fail_details),
            "fail_details": fail_details,
        }
        return str(summary)
