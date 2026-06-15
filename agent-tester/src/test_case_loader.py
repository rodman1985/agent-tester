"""
测试用例加载器模块
负责从Excel文件读取测试用例
实现SOP3测试基线永久冻结（MD5校验）
"""

import pandas as pd
import hashlib
import json
from typing import List, Dict, Any
from config import TEST_CONFIG, BASELINE_CONFIG


class TestCaseLoader:
    """测试用例加载器"""

    def __init__(self, file_path: str = None):
        self.file_path = file_path or TEST_CONFIG["test_case_file"]
        self.baseline_md5 = BASELINE_CONFIG.get("test_case_md5", "")
        self.current_md5 = ""

    def load_cases(self) -> List[Dict[str, Any]]:
        """
        加载所有测试用例（包含SOP3 MD5校验）

        Returns:
            测试用例列表
        """
        try:
            # SOP3: 计算用例文件MD5
            self.current_md5 = self._calculate_file_md5(self.file_path)
            
            # SOP3: 校验用例文件MD5，确保输入素材无变更
            if self.baseline_md5 and self.current_md5 != self.baseline_md5:
                print(f"[WARNING] SOP3基线校验失败：用例文件MD5变更")
                print(f"[WARNING] 基线MD5: {self.baseline_md5}")
                print(f"[WARNING] 当前MD5: {self.current_md5}")
                print(f"[WARNING] 请确认是否为预期变更，否则版本迭代对比无效")
            else:
                print(f"[INFO] SOP3基线校验通过：用例文件MD5 = {self.current_md5}")
            
            df = pd.read_excel(self.file_path)
            
            cases = []
            for _, row in df.iterrows():
                case = {
                    "id": row.get("序号", ""),
                    "name": row.get("测试场景", ""),
                    "description": row.get("核心调试目标", ""),
                    "input_text": f"简历格式优化：{row.get('测试输入内容', '')}",
                    "expected_structured": row.get("结构化信息状况", ""),
                    "expected_output": row.get("预期输出", ""),
                    "judgment_rule": row.get("量化判定规则", ""),
                }
                cases.append(case)
            
            print(f"[INFO] 成功加载 {len(cases)} 个测试用例")
            return cases
        
        except Exception as e:
            print(f"[ERROR] 加载测试用例失败: {e}")
            return []

    def _calculate_file_md5(self, file_path: str) -> str:
        """
        计算文件MD5值（SOP3：测试基线冻结校验）
        """
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                chunk = f.read(8192)
                while chunk:
                    file_hash.update(chunk)
                    chunk = f.read(8192)
            return file_hash.hexdigest()
        except Exception as e:
            print(f"[ERROR] 计算MD5失败: {e}")
            return ""

    def get_baseline_info(self) -> Dict[str, Any]:
        """
        获取基线信息（用于报告展示）
        """
        return {
            "test_case_md5": self.current_md5,
            "schema_version": BASELINE_CONFIG.get("schema_version", "v1.0"),
            "validation_rules_version": BASELINE_CONFIG.get("validation_rules_version", "v1.0"),
            "baseline_verified": not (self.baseline_md5 and self.current_md5 != self.baseline_md5),
        }
