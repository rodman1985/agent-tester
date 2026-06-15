"""
测试配置文件
"""

# Agent配置
AGENT_CONFIG = {
    "name": "简历结构化专家",
    "api_url": "http://localhost:8000/api/v1/resume/parse",
    "api_key": "",
    "timeout": 60,
    # SOP1: 模型推理参数强制固化
    "inference_params": {
        "temperature": 0,           # 固定为0，关闭创造性采样
        "top_p": 1.0,              # 固定为1.0
        "top_k": 1,                # 固定为1
        "seed": 42,                # 固定全局Seed，保证同输入唯一输出
        "max_tokens": 4096,        # 固定最大Token数
    },
}

# 测试配置
TEST_CONFIG = {
    "test_case_file": "test_cases/简历结构化测试用例（demo）.xlsx",
    "output_dir": "reports",
    "fail_fast": False,
    "max_retries": 1,
    "retry_delay": 2,
    "debug_mode": True,
    # SOP4: 多轮复测防抖降噪配置
    "repeat_count": 3,            # 单例重复执行次数
    "jitter_threshold": 1.0,      # 抖动率阈值（%），超过则判定环境异常
    # SOP6: 版本对比防抖阈值
    "fluctuation_threshold": 1.0, # 指标波动阈值（%），≤则判定为持平
    # SOP2: 评测环境全量锁死配置
    "concurrency": 1,             # 固定并发数
    "session_clear": True,        # 每条用例执行前强制清空会话缓存
    "prompt_version": "v1.0",     # 固定Prompt版本
    "parser_version": "v1.0",     # 固定解析器版本
}

# 报告配置
REPORT_CONFIG = {
    "title": "简历结构化专家 Agent 测试报告",
    "formats": ["html", "markdown", "json"],
}

# 模块名称列表
MODULES = [
    "基本信息",
    "核心优势",
    "工作经历",
    "项目经验",
    "教育背景",
    "技能专长",
    "风险提示",
    "自我评价",
]

# 基本信息字段列表
BASIC_FIELDS = [
    "姓名",
    "性别",
    "年龄",
    "工作年限",
    "联系方式",
    "电话",
    "邮箱",
    "所在城市",
    "求职意向",
    "当前状态",
    # 工作经历字段
    "工作成果",
    "公司简介",
    "核心职责",
    # 项目经验字段
    "项目背景",
    "项目成果",
    "个人职责",
    # 教育背景字段
    "就读时间",
    "在校亮点",
    # 技能专长字段
    "专业技能",
    "通用能力",
    # 检测逻辑默认值
    "未知字段",
]

# SOP3: 测试基线冻结配置（MD5校验）
BASELINE_CONFIG = {
    "test_case_md5": "",          # 用例文件MD5（首次运行后自动记录）
    "schema_version": "v1.0",     # 结构化Schema版本
    "validation_rules_version": "v1.0",  # 校验规则版本
}
