"""SkillSpector幻觉检测模块（SOP5刚性规则自动判定扩展）

负责检测四类简历场景幻觉：
- 字段无中生有
- 履历信息篡改
- 虚假数值赋值
- 无效冗余编造
"""
import re
from typing import Dict, List, Any, Tuple
from config import MODULES, BASIC_FIELDS

# 白名单字段列表（来自config.py，这些字段不作为幻觉检测内容）
WHITELIST_FIELDS = MODULES + BASIC_FIELDS

# 核心字段定义（用于保真检测）
CORE_FIELDS = [
    # 基本信息
    "姓名", "性别", "年龄", "工作年限", "联系方式", "所在城市", "求职意向", "当前状态",
    # 核心优势
    "核心优势",
    # 工作经历
    "公司名称", "行业", "职位", "起止时间", "公司简介", "核心职责", "工作成果",
    # 项目经验
    "项目名称", "项目角色", "项目周期", "项目背景", "个人职责", "项目成果",
    # 教育背景
    "毕业院校", "学历", "专业", "就读时间", "在校亮点",
    # 技能专长
    "专业技能", "通用能力", "语言能力", "证书资质",
    # 自我评价
    "自我评价"
]

# 格式验证规则
FORMAT_RULES = {
    "手机号": r"1[3-9]\d{9}",
    "邮箱": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "日期": r"\d{4}[.\-/年]\d{1,2}[.\-/月](\d{1,2}[日号])?",
    "学历": r"博士|硕士|本科|大专|高中|中专|初中|小学|候选人未提供",
    "年龄": r"\d{1,3}岁?",
    "工作年限": r"\d+年(\d+个月?)?(经验)?|应届|应届生",
}

# 虚假检测关键词
FICTION_KEYWORDS = [
    # 虚构公司名称关键词
    "知名企业", "大型公司", "著名机构", "行业领先", "头部企业",
    # 虚构职位关键词
    "高级", "资深", "专家", "总监", "经理",
    # 虚假数值关键词
    "优秀", "良好", "突出", "卓越", "顶尖", "一流",
]

class SkillSpector:
    """SkillSpector幻觉检测引擎"""
    
    def __init__(self):
        self.detection_results = []
    
    def scan_all_cases(self, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量扫描所有Agent结构化输出结果
        
        Args:
            test_cases: 测试用例列表，包含实际输出和预期输出
        
        Returns:
            扫描结果汇总
        """
        all_violations = []
        fiction_fields = []
        hallucination_samples = []
        error_categories = {
            "field_fabrication": 0,    # 字段无中生有
            "info_tampering": 0,       # 履历信息篡改
            "fake_value": 0,           # 虚假数值赋值
            "redundant_fabrication": 0 # 无效冗余编造
        }
        
        for case in test_cases:
            if case.get("status") == "passed":
                result = self._scan_single_case(case)
                self.detection_results.append(result)
                
                if result["violations"]:
                    all_violations.extend(result["violations"])
                    fiction_fields.extend(result["fiction_fields"])
                
                if result["has_hallucination"]:
                    hallucination_samples.append({
                        "case_id": case["id"],
                        "case_name": case["name"],
                        "hallucination_count": len(result["violations"]),
                        "error_types": result["error_types"]
                    })
                
                # 统计错误类型
                for err_type in result["error_types"]:
                    if err_type in error_categories:
                        error_categories[err_type] += 1
        
        # 计算指标
        total_fields_extracted = sum(r["total_fields_extracted"] for r in self.detection_results)
        total_fiction_fields = sum(r["fiction_field_count"] for r in self.detection_results)
        total_core_fields = sum(r["core_field_count"] for r in self.detection_results)
        total_lost_fields = sum(r["lost_core_fields"] for r in self.detection_results)
        
        # 核心指标计算
        if total_core_fields > 0:
            base_fidelity = 10 * ((total_core_fields - total_lost_fields) / total_core_fields)
            final_fidelity = max(0, base_fidelity - total_fiction_fields)
        else:
            base_fidelity = 0
            final_fidelity = 0
        
        if total_fields_extracted > 0:
            hallucination_rate = (total_fiction_fields / total_fields_extracted) * 100
        else:
            hallucination_rate = 0
        
        if total_core_fields > 0:
            info_loss_rate = (total_lost_fields / total_core_fields) * 100
        else:
            info_loss_rate = 0
        
        return {
            "summary": {
                "total_cases_scanned": len(self.detection_results),
                "hallucination_cases": len(hallucination_samples),
                "total_violations": len(all_violations),
                "total_fiction_fields": total_fiction_fields,
                "total_fields_extracted": total_fields_extracted,
                "total_core_fields": total_core_fields,
                "total_lost_fields": total_lost_fields,
            },
            "metrics": {
                "base_fidelity": base_fidelity,
                "final_fidelity": final_fidelity,
                "hallucination_rate": hallucination_rate,
                "info_loss_rate": info_loss_rate,
            },
            "error_categories": error_categories,
            "fiction_fields": list(set(fiction_fields)),
            "hallucination_samples": hallucination_samples,
            "all_violations": all_violations,
        }
    
    def _scan_single_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """
        扫描单个用例的结构化输出
        
        Returns:
            单个用例的扫描结果
        """
        output = case.get("actual_output", "")
        expected = case.get("expected_structured", "")
        
        violations = []
        fiction_fields = []
        error_types = []
        total_fields_extracted = 0
        core_field_count = 0
        lost_core_fields = 0
        
        # 1. 检测字段无中生有
        fabricated_fields = self._detect_field_fabrication(output, expected)
        if fabricated_fields:
            violations.extend([{"type": "field_fabrication", "field": f, "desc": f"字段无中生有: {f}"} 
                              for f in fabricated_fields])
            fiction_fields.extend(fabricated_fields)
            error_types.append("field_fabrication")
        
        # 2. 检测履历信息篡改
        tampered_info = self._detect_info_tampering(output, expected)
        if tampered_info:
            violations.extend([{"type": "info_tampering", "field": t["field"], "desc": t["desc"]} 
                              for t in tampered_info])
            error_types.append("info_tampering")
        
        # 3. 检测虚假数值赋值
        fake_values = self._detect_fake_values(output)
        if fake_values:
            violations.extend([{"type": "fake_value", "field": f["field"], "desc": f["desc"]} 
                              for f in fake_values])
            fiction_fields.extend([f["field"] for f in fake_values])
            error_types.append("fake_value")
        
        # 4. 检测无效冗余编造
        redundant_items = self._detect_redundant_fabrication(output)
        if redundant_items:
            violations.extend([{"type": "redundant_fabrication", "field": r["field"], "desc": r["desc"]} 
                              for r in redundant_items])
            error_types.append("redundant_fabrication")
        
        # 5. 统计字段信息
        total_fields_extracted = self._count_extracted_fields(output)
        core_field_count, lost_core_fields = self._count_core_fields(output, expected)
        
        return {
            "case_id": case["id"],
            "case_name": case["name"],
            "violations": violations,
            "fiction_fields": fiction_fields,
            "fiction_field_count": len(fiction_fields),
            "error_types": error_types,
            "has_hallucination": len(violations) > 0,
            "total_fields_extracted": total_fields_extracted,
            "core_field_count": core_field_count,
            "lost_core_fields": lost_core_fields,
        }
    
    def _detect_field_fabrication(self, output: str, expected: str) -> List[str]:
        """检测字段无中生有：输出中存在但预期中不存在的字段（排除白名单字段）"""
        fabricated = []
        
        # 简单实现：检查输出中是否有预期中没有的核心字段值
        for field in CORE_FIELDS:
            # 白名单字段不判定为幻觉
            if field in WHITELIST_FIELDS:
                continue
            
            if f"【{field}】" in output or f"{field}：" in output:
                if not (f"【{field}】" in expected or f"{field}：" in expected):
                    fabricated.append(field)
        
        return fabricated
    
    def _detect_info_tampering(self, output: str, expected: str) -> List[Dict[str, str]]:
        """检测履历信息篡改：字段值与预期不符"""
        tampered = []
        
        # 检测日期篡改
        output_dates = re.findall(FORMAT_RULES["日期"], output)
        expected_dates = re.findall(FORMAT_RULES["日期"], expected)
        
        if len(output_dates) != len(expected_dates):
            tampered.append({"field": "日期", "desc": f"日期数量不一致: 输出{len(output_dates)}个, 预期{len(expected_dates)}个"})
        
        # 检测学历篡改
        output_degrees = re.findall(FORMAT_RULES["学历"], output)
        expected_degrees = re.findall(FORMAT_RULES["学历"], expected)
        
        if output_degrees and expected_degrees and output_degrees != expected_degrees:
            tampered.append({"field": "学历", "desc": f"学历不一致: 输出{output_degrees}, 预期{expected_degrees}"})
        
        return tampered
    
    def _detect_fake_values(self, output: str) -> List[Dict[str, str]]:
        """检测虚假数值赋值：使用虚构关键词"""
        fake_values = []
        
        for keyword in FICTION_KEYWORDS:
            if keyword in output:
                # 尝试定位虚假值所在的字段
                field = self._find_field_containing(output, keyword)
                fake_values.append({"field": field, "desc": f"包含虚假描述关键词: {keyword}"})
        
        return fake_values
    
    def _detect_redundant_fabrication(self, output: str) -> List[Dict[str, str]]:
        """检测无效冗余编造：重复内容或无意义填充"""
        redundant = []
        
        # 检测重复内容（简单实现：检查连续重复的段落）
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        for i in range(len(lines) - 1):
            if lines[i] == lines[i + 1] and len(lines[i]) > 10:
                redundant.append({"field": "冗余内容", "desc": f"发现重复内容: {lines[i][:30]}..."})
                break
        
        # 检测候选人未提供的过度使用
        if output.count("候选人未提供") > 10:
            redundant.append({"field": "无效填充", "desc": "过度使用'候选人未提供'填充"})
        
        return redundant
    
    def _find_field_containing(self, output: str, keyword: str) -> str:
        """查找包含关键词的字段名"""
        for field in CORE_FIELDS:
            if f"【{field}】" in output:
                start = output.find(f"【{field}】")
                end = output.find("\n", start)
                if end == -1:
                    end = len(output)
                if keyword in output[start:end]:
                    return field
        return "未知字段"
    
    def _count_extracted_fields(self, output: str) -> int:
        """统计抽取的字段总数（排除白名单字段）"""
        count = 0
        for field in CORE_FIELDS:
            # 白名单字段不计入统计
            if field in WHITELIST_FIELDS:
                continue
            
            if f"【{field}】" in output or f"{field}：" in output:
                count += 1
        return count
    
    def _count_core_fields(self, output: str, expected: str) -> Tuple[int, int]:
        """统计核心字段数量和丢失数量（排除白名单字段）"""
        found_count = 0
        lost_count = 0
        
        for field in CORE_FIELDS:
            # 白名单字段不计入统计
            if field in WHITELIST_FIELDS:
                continue
            
            expected_has = f"【{field}】" in expected or f"{field}：" in expected
            output_has = f"【{field}】" in output or f"{field}：" in output
            
            if expected_has:
                found_count += 1
                if not output_has:
                    lost_count += 1
        
        return found_count, lost_count

# 全局实例
skill_spector = SkillSpector()

def scan_hallucination(test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    执行幻觉扫描（对外暴露的便捷函数）
    
    Args:
        test_cases: 测试用例列表
    
    Returns:
        幻觉扫描结果
    """
    return skill_spector.scan_all_cases(test_cases)