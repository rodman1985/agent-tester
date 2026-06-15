"""
Schema校验器模块
实现SOP5刚性规则自动判定
"""

import re
from typing import Dict, Any, List, Tuple
from config import MODULES, BASIC_FIELDS


class SchemaValidator:
    """Schema校验器（SOP5刚性规则自动判定）"""

    def __init__(self):
        # 结构化Schema定义
        self.required_modules = MODULES
        self.basic_fields = BASIC_FIELDS
        
        # 格式归一化规则（正则校验）
        self.format_rules = {
            "手机号": r"1[3-9]\d{9}",
            "邮箱": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "日期": r"\d{4}[.\-/年]\d{1,2}[.\-/月]",
            "学历": "博士|硕士|本科|大专|高中|初中|小学|候选人未提供",
        }

    def validate_output(self, output: str, expected_structured: str) -> Dict[str, Any]:
        """
        校验Agent输出是否符合Schema（SOP5刚性规则）
        
        Returns:
            校验结果，包含合规状态、违规详情
        """
        violations = []
        
        # 1. 模块完整性校验
        module_result = self._validate_modules(output, expected_structured)
        violations.extend(module_result["violations"])
        
        # 2. 字段完整性校验
        field_result = self._validate_fields(output, expected_structured)
        violations.extend(field_result["violations"])
        
        # 3. 格式归一化校验
        format_result = self._validate_formats(output)
        violations.extend(format_result["violations"])
        
        # 4. 结构化合规校验（检查嵌套结构）
        structure_result = self._validate_structure(output)
        violations.extend(structure_result["violations"])
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "module_score": module_result["score"],
            "field_score": field_result["score"],
            "format_score": format_result["score"],
            "structure_score": structure_result["score"],
            "total_score": (module_result["score"] + field_result["score"] + 
                          format_result["score"] + structure_result["score"]) / 4,
        }

    def _validate_modules(self, output: str, expected_structured: str) -> Dict[str, Any]:
        """
        模块完整性校验（SOP5刚性规则）
        """
        violations = []
        found_modules = []
        
        # 分析E列中声明的模块
        declared_modules = [m for m in self.required_modules 
                          if self._is_field_declared(expected_structured, m)]
        
        for module in declared_modules:
            if module in output:
                found_modules.append(module)
            else:
                violations.append({
                    "type": "模块缺失",
                    "field": module,
                    "actual": "未包含",
                    "expected": f"包含{module}模块",
                    "rule": "Schema强制校验",
                })
        
        score = len(found_modules) / len(declared_modules) * 100 if declared_modules else 100
        return {"violations": violations, "score": score}

    def _validate_fields(self, output: str, expected_structured: str) -> Dict[str, Any]:
        """
        字段完整性校验（SOP5刚性规则）
        """
        violations = []
        found_fields = []
        
        # 分析E列中声明的字段
        declared_fields = [f for f in self.basic_fields 
                         if self._is_field_declared(expected_structured, f)]
        
        for field in declared_fields:
            if field in output:
                found_fields.append(field)
            else:
                violations.append({
                    "type": "字段缺失",
                    "field": field,
                    "actual": "未包含",
                    "expected": f"包含{field}字段",
                    "rule": "Schema强制校验",
                })
        
        score = len(found_fields) / len(declared_fields) * 100 if declared_fields else 100
        return {"violations": violations, "score": score}

    def _validate_formats(self, output: str) -> Dict[str, Any]:
        """
        格式归一化校验（SOP5刚性规则：正则校验）
        """
        violations = []
        validated_count = 0
        total_checks = 0
        
        for field_name, pattern in self.format_rules.items():
            if field_name in output:
                total_checks += 1
                # 提取字段值
                field_value = self._extract_field_value(output, field_name)
                if field_value:
                    # 正则校验
                    if isinstance(pattern, str) and "|" in pattern:
                        # 白名单字典校验
                        if field_value in pattern.split("|"):
                            validated_count += 1
                        else:
                            violations.append({
                                "type": "格式违规",
                                "field": field_name,
                                "actual": field_value,
                                "expected": f"符合白名单: {pattern}",
                                "rule": "白名单字典刚性校验",
                            })
                    else:
                        # 正则校验
                        if re.search(pattern, field_value):
                            validated_count += 1
                        else:
                            violations.append({
                                "type": "格式违规",
                                "field": field_name,
                                "actual": field_value,
                                "expected": f"符合正则: {pattern}",
                                "rule": "正则刚性校验",
                            })
        
        score = validated_count / total_checks * 100 if total_checks else 100
        return {"violations": violations, "score": score}

    def _validate_structure(self, output: str) -> Dict[str, Any]:
        """
        结构化合规校验（SOP5：Schema强制校验嵌套结构）
        """
        violations = []
        checks_passed = 0
        total_checks = 4
        
        # 1. 检查基本信息模块是否存在
        if "## 基本信息" in output:
            checks_passed += 1
        else:
            violations.append({
                "type": "结构违规",
                "field": "基本信息模块",
                "actual": "缺失",
                "expected": "存在",
                "rule": "Schema强制校验",
            })
        
        # 2. 检查工作经历是否为独立结构
        if "##工作经历" in output or "## 工作经历" in output:
            checks_passed += 1
        else:
            violations.append({
                "type": "结构违规",
                "field": "工作经历模块",
                "actual": "缺失",
                "expected": "存在",
                "rule": "Schema强制校验",
            })
        
        # 3. 检查教育背景是否为独立结构
        if "##教育背景" in output or "## 教育背景" in output:
            checks_passed += 1
        else:
            violations.append({
                "type": "结构违规",
                "field": "教育背景模块",
                "actual": "缺失",
                "expected": "存在",
                "rule": "Schema强制校验",
            })
        
        # 4. 检查是否包含Markdown格式标记
        if "##" in output:
            checks_passed += 1
        else:
            violations.append({
                "type": "结构违规",
                "field": "Markdown格式",
                "actual": "缺失",
                "expected": "包含##标记",
                "rule": "Schema强制校验",
            })
        
        score = checks_passed / total_checks * 100
        return {"violations": violations, "score": score}

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

    def _extract_field_value(self, output: str, field_name: str) -> str:
        """
        提取字段值
        """
        field_index = output.find(field_name)
        if field_index == -1:
            return ""
        
        colon_index = output.find("：", field_index)
        if colon_index == -1:
            colon_index = output.find(":", field_index)
            if colon_index == -1:
                return ""
        
        next_newline = output.find("\n", colon_index + 1)
        if next_newline == -1:
            return output[colon_index + 1:].strip()
        else:
            return output[colon_index + 1:next_newline].strip()


def validate_schema(output: str, expected_structured: str) -> Dict[str, Any]:
    """
    便捷函数：执行Schema校验
    """
    validator = SchemaValidator()
    return validator.validate_output(output, expected_structured)