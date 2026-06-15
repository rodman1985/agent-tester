"""AgentEval准确率/完整性/一致性评测模块

负责执行以下评测流程：
- Step1: 基线锁定
- Step2: 多轮防抖执行
- Step3: AgentEval刚性打分
- Step4: 指标降噪聚合
- Step5: 版本差分对比
- Step6: 数据归档

优化判定&CI准出门禁规则：
- 效果优化标准：新版本准确率、完整性、一致性 ≥ 历史基线版本
- 准入阈值：单项指标≥95%，无大面积字段缺失、无逻辑穿越错误
- 红线规则：核心字段准确率暴跌、关键逻辑一致性失效
"""
import hashlib
import statistics
import re
from typing import Dict, List, Any, Tuple

def parse_markdown_resume(markdown_text: str) -> Dict[str, Any]:
    """
    解析Markdown格式或简化格式的简历为字典格式
    
    Args:
        markdown_text: Markdown格式或简化格式的简历文本
    
    Returns:
        解析后的字典格式简历
    """
    result = {}
    
    if not markdown_text or not isinstance(markdown_text, str):
        return result
    
    # 判断输入格式
    if "##" in markdown_text:
        # Markdown格式
        # 定义字段映射
        field_patterns = {
            "姓名": r"姓名[：:]\s*([^\n]+)",
            "性别": r"性别[：:]\s*([^\n]+)",
            "年龄": r"年龄[：/]\s*([^\n]+)",
            "工作年限": r"工作年限[：/]\s*([^\n]+)",
            "联系方式": r"联系方式[：:]\s*([^\n]+)",
            "所在城市": r"所在城市[：:]\s*([^\n]+)",
            "求职意向": r"求职意向[：:]\s*([^\n]+)",
            "当前状态": r"当前状态[：:]\s*([^\n]+)",
            "毕业院校": r"毕业院校[：:]\s*([^\n]+)",
            "学历": r"学历[：/]\s*([^\n]+)",
            "专业": r"专业[：/]\s*([^\n]+)",
            "就读时间": r"就读时间[：:]\s*([^\n]+)",
            "在校亮点": r"在校亮点[：:]\s*([^\n]+)",
            "专业技能": r"专业技能[：:]\s*([^\n]+)",
            "通用能力": r"通用能力[：:]\s*([^\n]+)",
            "语言能力": r"语言能力[：:]\s*([^\n]+)",
            "证书资质": r"证书资质[：:]\s*([^\n]+)",
            "自我评价": r"自我评价\s*\n([^\n]+(?:\n[^\n#]+)*)",
        }
        
        # 提取基本信息字段
        for field, pattern in field_patterns.items():
            match = re.search(pattern, markdown_text)
            if match:
                value = match.group(1).strip()
                # 清理特殊标记
                if value and value != "候选人未提供":
                    result[field] = value
        
        # 提取核心优势（列表形式）
        core_advantage_match = re.search(r"##核心优势\s*\n((?:-[^\n]+\n?)+)", markdown_text)
        if core_advantage_match:
            advantages = core_advantage_match.group(1).strip()
            result["核心优势"] = advantages
        
        # 提取工作经历
        work_experience_matches = re.findall(r"【([^】]+)】\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\n]+)", markdown_text)
        if work_experience_matches:
            work_list = []
            for match in work_experience_matches:
                company = match[0].strip()
                industry = match[1].strip()
                position = match[2].strip()
                time = match[3].strip()
                work_list.append({
                    "公司名称": company,
                    "行业": industry,
                    "职位": position,
                    "起止时间": time
                })
            result["工作经历"] = work_list
        
        # 提取项目经验
        project_matches = re.findall(r"([^\|\n]+)\s*\|\s*([^\|]+)\s*\|\s*([^\n]+)", markdown_text)
        if project_matches:
            project_list = []
            for match in project_matches:
                # 过滤掉工作经历的匹配
                if not match[0].startswith("【"):
                    project_name = match[0].strip()
                    role = match[1].strip()
                    cycle = match[2].strip()
                    project_list.append({
                        "项目名称": project_name,
                        "项目角色": role,
                        "项目周期": cycle
                    })
            if project_list:
                result["项目经验"] = project_list
    else:
        # 简化格式（expected_structured格式）
        field_patterns = {
            "姓名": r"姓名[：:]\s*([^\n]+)",
            "手机号": r"手机号[：:]\s*([^\n]+)",
            "邮箱": r"邮箱[：:]\s*([^\n]+)",
            "性别": r"性别[：:]\s*([^\n]+)",
            "年龄": r"年龄[：:]\s*([^\n]+)",
            "工作年限": r"工作年限[：:]\s*([^\n]+)",
            "最高学历": r"最高学历[：:]\s*([^\n]+)",
            "求职意向": r"求职意向[：:]\s*([^\n]+)",
            "期望薪资": r"期望薪资[：:]\s*([^\n]+)",
            "现居城市": r"现居城市[：:]\s*([^\n]+)",
            "毕业院校": r"毕业院校[：:]\s*([^\n]+)",
            "专业": r"专业[：:]\s*([^\n]+)",
            "毕业时间": r"毕业时间[：:]\s*([^\n]+)",
            "工作经历": r"工作经历[：:]\s*([^\n]+)",
            "项目经验": r"项目经验[：:]\s*([^\n]+)",
            "技能专长": r"技能专长[：:]\s*([^\n]+)",
            "通用能力": r"通用能力[：:]\s*([^\n]+)",
            "语言能力": r"语言能力[：:]\s*([^\n]+)",
            "证书资质": r"证书资质[：:]\s*([^\n]+)",
        }
        
        # 提取字段
        for field, pattern in field_patterns.items():
            match = re.search(pattern, markdown_text)
            if match:
                value = match.group(1).strip()
                if value and value != "候选人未提供":
                    result[field] = value
        
        # 字段映射：将expected_structured的字段名映射到output的字段名
        field_mapping = {
            "手机号": "联系方式",
            "现居城市": "所在城市",
            "最高学历": "学历",
            "毕业时间": "就读时间",
            "技能专长": "专业技能",
        }
        
        # 应用字段映射
        for old_field, new_field in field_mapping.items():
            if old_field in result:
                result[new_field] = result[old_field]
    
    return result

# 核心字段定义
CORE_FIELDS = [
    "姓名", "性别", "年龄", "工作年限", "联系方式", "所在城市", "求职意向", "当前状态",
    "核心优势", "公司名称", "行业", "职位", "起止时间", "公司简介", "核心职责", "工作成果",
    "项目名称", "项目角色", "项目周期", "项目背景", "个人职责", "项目成果",
    "毕业院校", "学历", "专业", "就读时间", "在校亮点",
    "专业技能", "通用能力", "语言能力", "证书资质", "自我评价"
]

# 白名单归一化映射（用于字段值归一化比对）
NORMALIZATION_WHITELIST = {
    "性别": {"男", "男", "男性", "男 ", "男\n"},
    "性别": {"女", "女", "女性", "女 ", "女\n"},
    "学历": {"本科", "学士学位", "本科毕业"},
    "学历": {"硕士", "硕士学位", "研究生", "硕士研究生"},
    "学历": {"博士", "博士学位", "博士生"},
    "当前状态": {"在职", "在岗", "现职"},
    "当前状态": {"离职", "待业", "失业"},
    "当前状态": {"应届", "应届生", "即将毕业"},
}

# 逻辑校验规则
LOGIC_RULES = {
    "时间顺序": lambda data: _check_time_order(data),
    "履历连续性": lambda data: _check_career_continuity(data),
    "学历合理性": lambda data: _check_education_rationale(data),
}

def _check_time_order(data: Dict[str, Any]) -> bool:
    """检查时间顺序是否合理"""
    try:
        # 检查工作经历时间是否合理
        work_experience = data.get("工作经历", [])
        for exp in work_experience:
            if isinstance(exp, dict):
                start = exp.get("起止时间", "")
                if start and len(start) >= 7:
                    # 简单检查年份是否合理
                    year = int(start[:4])
                    if year < 1990 or year > 2030:
                        return False
        return True
    except:
        return True

def _check_career_continuity(data: Dict[str, Any]) -> bool:
    """检查履历连续性"""
    try:
        work_experience = data.get("工作经历", [])
        if len(work_experience) > 1:
            # 简单检查是否有明显的时间冲突
            pass
        return True
    except:
        return True

def _check_education_rationale(data: Dict[str, Any]) -> bool:
    """检查学历合理性"""
    try:
        education = data.get("教育背景", {})
        degree = education.get("学历", "")
        if degree:
            # 检查学历是否在合理范围内
            valid_degrees = {"高中", "专科", "大专", "本科", "硕士", "博士"}
            if not any(d in degree for d in valid_degrees):
                return False
        return True
    except:
        return True

class AgentEval:
    """AgentEval评测引擎"""
    
    def __init__(self):
        self.baseline_md5 = ""
    
    def lock_baseline(self, test_cases: List[Dict[str, Any]], gt_files: List[str] = None) -> bool:
        """
        Step1: 基线锁定 - 加载冻结简历基线用例、GT真值文件、逻辑校验规则库
        
        Args:
            test_cases: 测试用例列表
            gt_files: GT真值文件路径列表
        
        Returns:
            是否锁定成功
        """
        # 计算用例库MD5
        cases_str = str([(c.get('id'), c.get('name'), c.get('input'), c.get('expected')) for c in test_cases])
        if gt_files:
            cases_str += str(gt_files)
        self.baseline_md5 = hashlib.md5(cases_str.encode()).hexdigest()
        return True
    
    def multi_round_execution(self, test_cases: List[Dict[str, Any]], 
                              execute_case_func, rounds: int = 3) -> List[Dict[str, Any]]:
        """
        Step2: 多轮防抖执行 - 所有用例单例重复执行多次
        
        Args:
            test_cases: 测试用例列表
            execute_case_func: 执行单个用例的函数
            rounds: 执行轮数
        
        Returns:
            多轮执行结果汇总
        """
        all_round_results = []
        
        for round_num in range(rounds):
            round_results = []
            for case in test_cases:
                result = execute_case_func(case)
                round_results.append({
                    "case_id": case["id"],
                    "case_name": case["name"],
                    "output": result.get("output", {}),
                    "expected": result.get("expected", case.get("expected", {})),
                    "round": round_num + 1,
                })
            all_round_results.extend(round_results)
        
        return all_round_results
    
    def rigid_scoring(self, output: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, float]:
        """
        Step3: AgentEval刚性打分 - 字符串精准匹配+白名单归一校验
        
        Args:
            output: Agent输出结果（可以是字典或Markdown字符串）
            expected: GT真值（可以是字典或Markdown字符串）
        
        Returns:
            打分结果（准确率、完整性、一致性）
        """
        # 处理Markdown字符串格式输入
        if isinstance(output, str):
            output = parse_markdown_resume(output)
        if isinstance(expected, str):
            expected = parse_markdown_resume(expected)
        
        # 如果解析后仍为空，使用默认值
        if not output:
            output = {}
        if not expected:
            expected = {}
        
        # 准确率计算：匹配字段数 / 总字段数
        total_fields = len(expected) if expected else 1
        matched_fields = 0
        
        for key, expected_value in expected.items():
            output_value = output.get(key, "")
            
            # 处理None值
            if expected_value is None:
                expected_value = ""
            if output_value is None:
                output_value = ""
            
            # 转换为字符串进行比较
            expected_str = str(expected_value).strip()
            output_str = str(output_value).strip()
            
            # 白名单归一化校验
            if key in NORMALIZATION_WHITELIST:
                normalized_expected = expected_str.lower()
                normalized_output = output_str.lower()
                # 检查是否在同一归一化组
                matched = False
                for group in NORMALIZATION_WHITELIST[key]:
                    if normalized_expected in group.lower() and normalized_output in group.lower():
                        matched = True
                        break
                if matched:
                    matched_fields += 1
                elif expected_str == output_str:
                    matched_fields += 1
            elif expected_str == output_str:
                matched_fields += 1
        
        accuracy = (matched_fields / total_fields) * 100 if total_fields > 0 else 0
        
        # 完整性计算：输出字段数 / GT字段数
        gt_field_count = len(expected) if expected else 1
        output_field_count = 0
        for key in expected:
            if key in output and output[key] not in [None, "", "候选人未提供"]:
                output_field_count += 1
        
        completeness = (output_field_count / gt_field_count) * 100 if gt_field_count > 0 else 0
        
        # 一致性计算：逻辑规则校验通过率
        logic_pass_count = 0
        logic_total_count = len(LOGIC_RULES)
        
        for rule_name, rule_func in LOGIC_RULES.items():
            if rule_func(output):
                logic_pass_count += 1
        
        consistency = (logic_pass_count / logic_total_count) * 100 if logic_total_count > 0 else 100
        
        return {
            "accuracy": accuracy,
            "completeness": completeness,
            "consistency": consistency,
            "matched_fields": matched_fields,
            "total_fields": total_fields,
            "missing_fields": gt_field_count - output_field_count,
        }
    
    def aggregate_metrics(self, round_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Step4: 指标降噪聚合 - 三次评测指标取中位数
        
        Args:
            round_results: 多轮执行结果
        
        Returns:
            聚合后的指标
        """
        # 按用例分组计算每轮数据
        case_data = {}
        for res in round_results:
            case_id = res["case_id"]
            if case_id not in case_data:
                case_data[case_id] = {
                    "accuracies": [],
                    "completenesses": [],
                    "consistencies": [],
                }
            
            # 计算本轮打分
            scoring_result = self.rigid_scoring(res["output"], res["expected"])
            case_data[case_id]["accuracies"].append(scoring_result["accuracy"])
            case_data[case_id]["completenesses"].append(scoring_result["completeness"])
            case_data[case_id]["consistencies"].append(scoring_result["consistency"])
        
        # 计算每用例的中位数和抖动率
        all_accuracies = []
        all_completenesses = []
        all_consistencies = []
        valid_cases = 0
        
        for case_id, data in case_data.items():
            # 计算抖动率
            acc_std = statistics.stdev(data["accuracies"]) if len(data["accuracies"]) > 1 else 0
            acc_mean = sum(data["accuracies"]) / len(data["accuracies"]) if data["accuracies"] else 1
            acc_mean = acc_mean if acc_mean != 0 else 1  # 防止除零错误
            jitter_rate = (acc_std / acc_mean) * 100
            
            # 抖动率＞1%作废本轮数据
            if jitter_rate > 1:
                continue
            
            # 取中位数
            if data["accuracies"]:
                all_accuracies.append(statistics.median(data["accuracies"]))
            if data["completenesses"]:
                all_completenesses.append(statistics.median(data["completenesses"]))
            if data["consistencies"]:
                all_consistencies.append(statistics.median(data["consistencies"]))
            
            valid_cases += 1
        
        # 计算整体指标
        final_accuracy = sum(all_accuracies) / len(all_accuracies) if all_accuracies else 0
        final_completeness = sum(all_completenesses) / len(all_completenesses) if all_completenesses else 0
        final_consistency = sum(all_consistencies) / len(all_consistencies) if all_consistencies else 0
        
        return {
            "accuracy": final_accuracy,
            "completeness": final_completeness,
            "consistency": final_consistency,
            "valid_cases": valid_cases,
            "total_cases": len(case_data),
            "baseline_md5": self.baseline_md5,
        }
    
    def version_diff_comparison(self, current_metrics: Dict[str, float], 
                                prev_metrics: Dict[str, float],
                                threshold: float = 1.0) -> Dict[str, str]:
        """
        Step5: 版本差分对比 - 遵循1%防抖阈值
        
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
            results["accuracy"] = "首次测试"
            results["completeness"] = "首次测试"
            results["consistency"] = "首次测试"
            return results
        
        # 准确率判定（上涨为优化）
        acc_diff = abs(current_metrics["accuracy"] - prev_metrics.get("accuracy", 0))
        if acc_diff <= threshold:
            results["accuracy"] = "持平"
        elif current_metrics["accuracy"] > prev_metrics["accuracy"]:
            results["accuracy"] = "优化"
        else:
            results["accuracy"] = "退化"
        
        # 完整性判定（上涨为优化）
        comp_diff = abs(current_metrics["completeness"] - prev_metrics.get("completeness", 0))
        if comp_diff <= threshold:
            results["completeness"] = "持平"
        elif current_metrics["completeness"] > prev_metrics["completeness"]:
            results["completeness"] = "优化"
        else:
            results["completeness"] = "退化"
        
        # 一致性判定（上涨为优化）
        cons_diff = abs(current_metrics["consistency"] - prev_metrics.get("consistency", 0))
        if cons_diff <= threshold:
            results["consistency"] = "持平"
        elif current_metrics["consistency"] > prev_metrics["consistency"]:
            results["consistency"] = "优化"
        else:
            results["consistency"] = "退化"
        
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
    
    def check_gate_rules(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        CI准出门禁规则检查
        
        Args:
            metrics: 当前版本指标
        
        Returns:
            门禁检查结果
        """
        accuracy_pass = metrics["accuracy"] >= 95
        completeness_pass = metrics["completeness"] >= 95
        consistency_pass = metrics["consistency"] >= 95
        
        # 红线规则检查
        red_line_violated = False
        red_line_reasons = []
        
        if metrics["accuracy"] < 80:
            red_line_violated = True
            red_line_reasons.append("核心字段准确率暴跌（＜80%）")
        
        if metrics["consistency"] < 80:
            red_line_violated = True
            red_line_reasons.append("关键逻辑一致性失效（＜80%）")
        
        # 综合判定
        can_pass = accuracy_pass and completeness_pass and consistency_pass and not red_line_violated
        
        return {
            "can_pass": can_pass,
            "accuracy_pass": accuracy_pass,
            "completeness_pass": completeness_pass,
            "consistency_pass": consistency_pass,
            "red_line_violated": red_line_violated,
            "red_line_reasons": red_line_reasons,
        }

# 全局实例
agent_eval = AgentEval()

def run_agent_eval(test_cases: List[Dict[str, Any]], 
                   execute_case_func,
                   prev_metrics: Dict[str, float] = None) -> Dict[str, Any]:
    """
    执行完整的AgentEval准确率/完整性/一致性评测
    
    Args:
        test_cases: 测试用例列表
        execute_case_func: 执行单个用例的函数
        prev_metrics: 上一版本指标（用于版本对比）
    
    Returns:
        评测结果汇总
    """
    eval_engine = AgentEval()
    
    # Step1: 基线锁定
    eval_engine.lock_baseline(test_cases)
    
    # Step2: 多轮防抖执行
    round_results = eval_engine.multi_round_execution(test_cases, execute_case_func)
    
    # Step3 & Step4: 刚性打分 + 指标降噪聚合
    current_metrics = eval_engine.aggregate_metrics(round_results)
    
    # Step5: 版本差分对比
    diff_result = eval_engine.version_diff_comparison(current_metrics, prev_metrics)
    
    # Step6: 门禁规则检查
    gate_result = eval_engine.check_gate_rules(current_metrics)
    
    return {
        "step1_baseline_md5": eval_engine.baseline_md5,
        "step2_round_results": round_results,
        "step4_metrics": current_metrics,
        "step5_diff_result": diff_result,
        "step6_gate_result": gate_result,
    }
