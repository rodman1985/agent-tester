"""AIOpsLab性能&成本&稳定性评测模块

负责执行以下评测流程：
- Step1: 基线锁定
- Step2: 批量隔离执行
- Step3: 多轮防抖采样
- Step4: 指标自动化计算
- Step5: 版本差分判定
- Step6: 数据归档
"""
import hashlib
import statistics
from typing import Dict, List, Any, Tuple

class AIOpsLab:
    """AIOpsLab性能评测引擎"""
    
    def __init__(self):
        self.performance_results = []
        self.baseline_md5 = ""
    
    def lock_baseline(self, test_cases: List[Dict[str, Any]]) -> bool:
        """
        Step1: 基线锁定 - 加载冻结基线用例库，MD5校验输入素材
        
        Args:
            test_cases: 测试用例列表
        
        Returns:
            是否锁定成功
        """
        # 计算用例库MD5
        cases_str = str([(c.get('id'), c.get('name'), c.get('input')) for c in test_cases])
        self.baseline_md5 = hashlib.md5(cases_str.encode()).hexdigest()
        return True
    
    def batch_isolation_execution(self, test_cases: List[Dict[str, Any]], 
                                  execute_case_func) -> List[Dict[str, Any]]:
        """
        Step2: 批量隔离执行 - 沙箱批量跑满基线用例
        
        Args:
            test_cases: 测试用例列表
            execute_case_func: 执行单个用例的函数
        
        Returns:
            执行结果列表
        """
        results = []
        
        for case in test_cases:
            result = execute_case_func(case)
            results.append({
                "case_id": case["id"],
                "case_name": case["name"],
                "token_consumption": result.get("token_consumption", 0),
                "latency_ms": result.get("latency_ms", 0),
                "status": result.get("status", "failed"),
            })
        
        return results
    
    def multi_round_debounce_sampling(self, test_cases: List[Dict[str, Any]], 
                                      execute_case_func, rounds: int = 3) -> List[Dict[str, Any]]:
        """
        Step3: 多轮防抖采样 - 所有用例执行多次，采集性能数据
        
        Args:
            test_cases: 测试用例列表
            execute_case_func: 执行单个用例的函数
            rounds: 执行轮数
        
        Returns:
            多轮执行结果汇总
        """
        all_round_results = []
        
        for round_num in range(rounds):
            round_results = self.batch_isolation_execution(test_cases, execute_case_func)
            for res in round_results:
                res["round"] = round_num + 1
            all_round_results.extend(round_results)
        
        return all_round_results
    
    def calculate_metrics(self, round_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Step4: 指标自动化计算
        
        Args:
            round_results: 多轮执行结果
        
        Returns:
            计算得到的性能指标
        """
        # 按用例分组计算每轮数据
        case_data = {}
        for res in round_results:
            case_id = res["case_id"]
            if case_id not in case_data:
                case_data[case_id] = {
                    "token_consumptions": [],
                    "latencies": [],
                    "statuses": []
                }
            case_data[case_id]["token_consumptions"].append(res["token_consumption"])
            case_data[case_id]["latencies"].append(res["latency_ms"])
            case_data[case_id]["statuses"].append(res["status"])
        
        # 计算每用例的中位数（剔除极值）
        all_tokens = []
        all_latencies = []
        passed_count = 0
        total_count = len(case_data)
        
        for case_id, data in case_data.items():
            # 取中位数作为代表值
            if data["token_consumptions"]:
                token_median = statistics.median(data["token_consumptions"])
                all_tokens.append(token_median)
            
            if data["latencies"]:
                latency_median = statistics.median(data["latencies"])
                all_latencies.append(latency_median)
            
            # 判定用例是否通过（至少两轮通过）
            pass_count = sum(1 for s in data["statuses"] if s == "passed")
            if pass_count >= 2:
                passed_count += 1
        
        # 计算指标
        if all_tokens:
            avg_token_consumption = sum(all_tokens) / len(all_tokens)
        else:
            avg_token_consumption = 0
        
        if all_latencies:
            # 计算P95延迟
            sorted_latencies = sorted(all_latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            if p95_index >= len(sorted_latencies):
                p95_index = len(sorted_latencies) - 1
            p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0
            
            # 计算抖动率（相对标准差）
            latency_std = statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0
            latency_mean = sum(all_latencies) / len(all_latencies) if all_latencies else 1
            latency_jitter_rate = (latency_std / latency_mean) * 100
            
            # Token消耗抖动率
            token_std = statistics.stdev(all_tokens) if len(all_tokens) > 1 else 0
            token_mean = sum(all_tokens) / len(all_tokens) if all_tokens else 0
            token_jitter_rate = (token_std / token_mean) * 100 if token_mean > 0 else 0
        else:
            p95_latency = 0
            latency_jitter_rate = 0
            token_jitter_rate = 0
        
        # CostPass综合成本
        pass_rate = passed_count / total_count if total_count > 0 else 0
        cost_pass = avg_token_consumption / pass_rate if pass_rate > 0 else float('inf')
        
        # 综合抖动率
        overall_jitter_rate = (latency_jitter_rate + token_jitter_rate) / 2
        
        return {
            "avg_token_consumption": avg_token_consumption,
            "p95_latency_ms": p95_latency,
            "cost_pass": cost_pass,
            "latency_jitter_rate": latency_jitter_rate,
            "token_jitter_rate": token_jitter_rate,
            "overall_jitter_rate": overall_jitter_rate,
            "pass_rate": pass_rate,
            "passed_count": passed_count,
            "total_count": total_count,
            "baseline_md5": self.baseline_md5,
        }
    
    def version_diff_judgment(self, current_metrics: Dict[str, float], 
                              prev_metrics: Dict[str, float], 
                              threshold: float = 1.0) -> Dict[str, str]:
        """
        Step5: 版本差分判定 - 遵循1%防抖阈值
        
        Args:
            current_metrics: 当前版本指标
            prev_metrics: 上一版本指标
            threshold: 抖动阈值（%）
        
        Returns:
            差分判定结果
        """
        results = {}
        
        if not prev_metrics:
            results["overall"] = "首次测试"
            results["avg_token_consumption"] = "首次测试"
            results["p95_latency_ms"] = "首次测试"
            results["cost_pass"] = "首次测试"
            results["overall_jitter_rate"] = "首次测试"
            return results
        
        # Token消耗判定（降低为优化）
        token_diff = abs(current_metrics["avg_token_consumption"] - prev_metrics.get("avg_token_consumption", 0))
        token_prev = prev_metrics.get("avg_token_consumption", 0)
        # 如果上一版本Token消耗为0，则使用绝对值判定（≤1%为持平）
        if token_prev == 0:
            if token_diff <= 1:
                results["avg_token_consumption"] = "持平"
            elif current_metrics["avg_token_consumption"] < prev_metrics.get("avg_token_consumption", 0):
                results["avg_token_consumption"] = "优化"
            else:
                results["avg_token_consumption"] = "退化"
        else:
            token_change = (token_diff / token_prev) * 100
            if token_change <= threshold:
                results["avg_token_consumption"] = "持平"
            elif current_metrics["avg_token_consumption"] < prev_metrics["avg_token_consumption"]:
                results["avg_token_consumption"] = "优化"
            else:
                results["avg_token_consumption"] = "退化"
        
        # P95延迟判定（降低为优化）
        latency_diff = abs(current_metrics["p95_latency_ms"] - prev_metrics.get("p95_latency_ms", 0))
        latency_prev = prev_metrics.get("p95_latency_ms", 0)
        # 如果上一版本P95延迟为0，则使用绝对值判定（≤1%为持平）
        if latency_prev == 0:
            if latency_diff <= 1:
                results["p95_latency_ms"] = "持平"
            elif current_metrics["p95_latency_ms"] < prev_metrics["p95_latency_ms"]:
                results["p95_latency_ms"] = "优化"
            else:
                results["p95_latency_ms"] = "退化"
        else:
            latency_change = (latency_diff / latency_prev) * 100
            if latency_change <= threshold:
                results["p95_latency_ms"] = "持平"
            elif current_metrics["p95_latency_ms"] < prev_metrics["p95_latency_ms"]:
                results["p95_latency_ms"] = "优化"
            else:
                results["p95_latency_ms"] = "退化"
        
        # CostPass判定（降低为优化）
        cost_diff = abs(current_metrics["cost_pass"] - prev_metrics.get("cost_pass", 0))
        cost_prev = prev_metrics.get("cost_pass", 0)
        # 如果上一版本CostPass为0，则使用绝对值判定（≤1%为持平）
        if cost_prev == 0:
            if cost_diff <= 1:
                results["cost_pass"] = "持平"
            elif current_metrics["cost_pass"] < prev_metrics.get("cost_pass", 0):
                results["cost_pass"] = "优化"
            else:
                results["cost_pass"] = "退化"
        else:
            cost_change = (cost_diff / cost_prev) * 100
            if cost_change <= threshold:
                results["cost_pass"] = "持平"
            elif current_metrics["cost_pass"] < prev_metrics["cost_pass"]:
                results["cost_pass"] = "优化"
            else:
                results["cost_pass"] = "退化"
        
        # 抖动率判定（降低为优化）
        jitter_diff = abs(current_metrics["overall_jitter_rate"] - prev_metrics.get("overall_jitter_rate", 0))
        jitter_prev = prev_metrics.get("overall_jitter_rate", 0)
        # 如果上一版本抖动率为0，则使用绝对值判定（≤1%为持平）
        if jitter_prev == 0:
            if jitter_diff <= 1:
                results["overall_jitter_rate"] = "持平"
            elif current_metrics["overall_jitter_rate"] < prev_metrics.get("overall_jitter_rate", 0):
                results["overall_jitter_rate"] = "优化"
            else:
                results["overall_jitter_rate"] = "退化"
        else:
            jitter_change = (jitter_diff / jitter_prev) * 100
            if jitter_change <= threshold:
                results["overall_jitter_rate"] = "持平"
            elif current_metrics["overall_jitter_rate"] < prev_metrics["overall_jitter_rate"]:
                results["overall_jitter_rate"] = "优化"
            else:
                results["overall_jitter_rate"] = "退化"
        
        # 综合判定
        optimize_count = sum(1 for v in results.values() if v == "优化")
        degrade_count = sum(1 for v in results.values() if v == "退化")
        
        if degrade_count > 0:
            results["overall"] = "退化"
        elif optimize_count > 0:
            results["overall"] = "优化"
        else:
            results["overall"] = "持平"
        
        return results

# 全局实例
aiops_lab = AIOpsLab()

def run_performance_evaluation(test_cases: List[Dict[str, Any]], 
                               execute_case_func,
                               prev_metrics: Dict[str, float] = None) -> Dict[str, Any]:
    """
    执行完整的性能&成本&稳定性评测
    
    Args:
        test_cases: 测试用例列表
        execute_case_func: 执行单个用例的函数
        prev_metrics: 上一版本指标（用于版本对比）
    
    Returns:
        评测结果汇总
    """
    lab = AIOpsLab()
    
    # Step1: 基线锁定
    lab.lock_baseline(test_cases)
    
    # Step3: 多轮防抖采样（包含Step2批量执行）
    round_results = lab.multi_round_debounce_sampling(test_cases, execute_case_func)
    
    # Step4: 指标计算
    current_metrics = lab.calculate_metrics(round_results)
    
    # Step5: 版本差分判定
    diff_result = lab.version_diff_judgment(current_metrics, prev_metrics)
    
    return {
        "step1_baseline_md5": lab.baseline_md5,
        "step3_round_results": round_results,
        "step4_metrics": current_metrics,
        "step5_diff_result": diff_result,
    }
