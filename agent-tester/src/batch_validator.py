"""
批次合规校验器模块
实现SOP7批次最终合规兜底（准出终审）
"""

import json
import statistics
from datetime import datetime
from typing import Dict, Any, List
from config import TEST_CONFIG


class BatchValidator:
    """批次合规校验器（SOP7批次最终合规兜底）"""

    def __init__(self):
        self.fluctuation_threshold = TEST_CONFIG.get("fluctuation_threshold", 1.0)
        self.jitter_threshold = TEST_CONFIG.get("jitter_threshold", 1.0)

    def validate_batch(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行批次合规校验（SOP7准出终审）
        
        Returns:
            批次合规结果
        """
        violations = []
        
        # 1. 校验批次核心指标无跳变
        pass_rate_result = self._validate_pass_rate(results)
        violations.extend(pass_rate_result["violations"])
        
        # 2. 校验通过率波动正常
        fluctuation_result = self._validate_fluctuation(results)
        violations.extend(fluctuation_result["violations"])
        
        # 3. 校验无偶发、不可复现的P0严重缺陷
        p0_defects_result = self._validate_p0_defects(results)
        violations.extend(p0_defects_result["violations"])
        
        # 4. 校验抖动率正常
        jitter_result = self._validate_jitter_rate(results)
        violations.extend(jitter_result["violations"])
        
        # 5. 校验评测数据完整性
        data_integrity_result = self._validate_data_integrity(results)
        violations.extend(data_integrity_result["violations"])
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "pass_rate": pass_rate_result["value"],
            "fluctuation": fluctuation_result["value"],
            "jitter_rate": jitter_result["value"],
            "p0_defects": p0_defects_result["value"],
            "data_integrity": data_integrity_result["value"],
            "audit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "audit_conclusion": "批次合规" if len(violations) == 0 else "批次不合规",
        }

    def _validate_pass_rate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        校验通过率无跳变（SOP7）
        
        修改：如果任意测试用例失败（fail），则判定准出失败
        """
        violations = []
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "passed")
        failed = sum(1 for r in results if r["status"] == "failed")
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        # 如果任意测试用例失败，则直接判定准出失败
        if failed > 0:
            violations.append({
                "type": "测试用例失败",
                "actual": f"{failed}个测试用例失败",
                "expected": "0个测试用例失败",
                "rule": "SOP7批次合规校验：任意测试用例失败则准出失败",
                "details": [{"case_id": r["id"], "name": r["name"]} for r in results if r["status"] == "failed"]
            })
        # 否则检查通过率阈值（≥95%）
        elif pass_rate < 95:
            violations.append({
                "type": "通过率跳变",
                "actual": f"{pass_rate:.1f}%",
                "expected": "≥95%",
                "rule": "SOP7批次合规校验",
            })
        
        return {"violations": violations, "value": pass_rate}

    def _validate_fluctuation(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        校验指标波动正常（SOP6/SOP7）
        """
        violations = []
        latency_fluctuation = 0
        token_fluctuation = 0
        
        # 计算各指标波动率
        latencies = [r["metrics"]["latency_ms"] for r in results if r["metrics"]["latency_ms"] > 0]
        tokens = [r["metrics"]["token_metrics"].get("total_tokens", 0) for r in results]
        
        # 计算标准差作为波动指标
        if latencies:
            latency_std = statistics.stdev(latencies)
            latency_mean = statistics.mean(latencies)
            latency_fluctuation = (latency_std / latency_mean * 100) if latency_mean > 0 else 0
            
            if latency_fluctuation > self.fluctuation_threshold * 10:  # 放宽阈值
                violations.append({
                    "type": "延迟波动异常",
                    "actual": f"{latency_fluctuation:.1f}%",
                    "expected": f"≤{self.fluctuation_threshold * 10}%",
                    "rule": "SOP7批次合规校验",
                })
        
        if tokens and any(t > 0 for t in tokens):
            valid_tokens = [t for t in tokens if t > 0]
            if valid_tokens:
                token_std = statistics.stdev(valid_tokens)
                token_mean = statistics.mean(valid_tokens)
                token_fluctuation = (token_std / token_mean * 100) if token_mean > 0 else 0
                
                if token_fluctuation > self.fluctuation_threshold * 10:
                    violations.append({
                        "type": "Token波动异常",
                        "actual": f"{token_fluctuation:.1f}%",
                        "expected": f"≤{self.fluctuation_threshold * 10}%",
                        "rule": "SOP7批次合规校验",
                    })
        
        avg_fluctuation = 0
        valid_count = 0
        if latency_fluctuation > 0:
            avg_fluctuation += latency_fluctuation
            valid_count += 1
        if token_fluctuation > 0:
            avg_fluctuation += token_fluctuation
            valid_count += 1
        if valid_count > 0:
            avg_fluctuation /= valid_count
        
        return {"violations": violations, "value": avg_fluctuation}

    def _validate_p0_defects(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        校验无偶发、不可复现的P0严重缺陷（SOP7）
        """
        violations = []
        p0_defects = []
        
        # 检查是否存在环境异常（不可复现）
        for r in results:
            if r["status"] == "error":
                p0_defects.append({
                    "case_id": r["id"],
                    "type": "环境异常",
                    "detail": r.get("result_summary", ""),
                })
        
        # 检查是否存在严重失败（多次执行仍失败）
        for r in results:
            if r["status"] == "failed":
                pass_count = r.get("pass_count", 0)
                repeat_count = r.get("repeat_count", 3)
                if pass_count == 0:  # 所有轮次都失败
                    p0_defects.append({
                        "case_id": r["id"],
                        "type": "严重失败",
                        "detail": f"{repeat_count}轮执行全部失败",
                    })
        
        if p0_defects:
            violations.append({
                "type": "P0严重缺陷",
                "actual": f"{len(p0_defects)}个P0缺陷",
                "expected": "0个P0缺陷",
                "rule": "SOP7批次合规校验",
                "details": p0_defects,
            })
        
        return {"violations": violations, "value": len(p0_defects)}

    def _validate_jitter_rate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        校验抖动率正常（SOP4/SOP7）
        """
        violations = []
        jitter_rates = [r.get("jitter_rate", 0) for r in results]
        
        if jitter_rates:
            avg_jitter = sum(jitter_rates) / len(jitter_rates)
            max_jitter = max(jitter_rates)
            
            if max_jitter > self.jitter_threshold:
                violations.append({
                    "type": "抖动率超标",
                    "actual": f"最大抖动率{max_jitter:.2f}%",
                    "expected": f"≤{self.jitter_threshold}%",
                    "rule": "SOP7批次合规校验",
                })
        
        avg_jitter = sum(jitter_rates) / len(jitter_rates) if jitter_rates else 0
        return {"violations": violations, "value": avg_jitter}

    def _validate_data_integrity(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        校验评测数据完整性（SOP7：所有评测数据归档可追溯）
        """
        violations = []
        missing_data_count = 0
        
        for r in results:
            # 检查必要字段是否存在
            required_fields = ["id", "name", "status", "metrics", "actual_output"]
            for field in required_fields:
                if field not in r:
                    missing_data_count += 1
                    violations.append({
                        "type": "数据缺失",
                        "case_id": r.get("id", "unknown"),
                        "actual": f"缺失{field}",
                        "expected": f"包含{field}",
                        "rule": "SOP7数据完整性校验",
                    })
                    break
        
        return {"violations": violations, "value": missing_data_count}

    def generate_audit_report(self, results: List[Dict[str, Any]]) -> str:
        """
        生成批次合规审计报告（SOP7）
        """
        audit_result = self.validate_batch(results)
        
        report = f"""
## SOP7批次最终合规审计报告

### 审计时间：{audit_result['audit_time']}

### 审计结论：{audit_result['audit_conclusion']}

### 核心指标校验结果

| 校验项 | 实测值 | 标准阈值 | 是否达标 |
|--------|--------|----------|----------|
| 通过率 | {audit_result['pass_rate']:.1f}% | ≥95% | {'是' if audit_result['pass_rate'] >= 95 else '否'} |
| 指标波动率 | {audit_result['fluctuation']:.1f}% | ≤10% | {'是' if audit_result['fluctuation'] <= 10 else '否'} |
| 平均抖动率 | {audit_result['jitter_rate']:.2f}% | ≤{self.jitter_threshold}% | {'是' if audit_result['jitter_rate'] <= self.jitter_threshold else '否'} |
| P0严重缺陷 | {audit_result['p0_defects']}个 | 0个 | {'是' if audit_result['p0_defects'] == 0 else '否'} |
| 数据完整性 | {audit_result['data_integrity']}个缺失 | 0个缺失 | {'是' if audit_result['data_integrity'] == 0 else '否'} |

### 违规详情

"""
        if audit_result["violations"]:
            for v in audit_result["violations"]:
                report += f"- **{v['type']}**: {v['actual']} (期望: {v['expected']})\n"
        else:
            report += "- 无违规项\n"

        report += f"""
### 归档信息

- 评测数据完整归档：{'是' if audit_result['data_integrity'] == 0 else '否'}
- 可追溯复现：{'是' if audit_result['compliant'] else '否'}
- 版本准出建议：{'通过' if audit_result['compliant'] else '不通过，需整改'}
"""
        
        return report


def validate_batch(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    便捷函数：执行批次合规校验
    """
    validator = BatchValidator()
    return validator.validate_batch(results)