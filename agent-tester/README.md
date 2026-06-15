# Agent Tester - 简历结构化专家测试工程

> 用于测试和评估「简历结构化专家」AI Agent的自动化测试框架

## 工程结构

```
agent-tester/
├── src/                    # 核心测试代码
│   ├── agent_client.py     # Agent客户端，负责调用Agent API
│   ├── agent_eval.py       # Agent效果评测模块（准确率、完整性、一致性）
│   ├── aiops_lab.py        # AIOpsLab性能评测模块
│   ├── batch_validator.py  # 批次合规校验模块
│   ├── report_generator.py # 测试报告生成模块
│   ├── schema_validator.py # Schema合规校验模块
│   ├── skill_spector.py    # SkillSpector保真度评测模块
│   ├── test_case_loader.py # 测试用例加载器
│   └── test_executor.py    # 测试执行器
├── test_cases/             # 测试用例目录
│   ├── Agent准出测试标准.md     # 准出测试标准文档
│   └── 简历结构化测试用例（demo）.xlsx  # 测试用例文件
├── reports/                # 测试报告输出目录
├── config.py               # 配置文件
├── requirements.txt        # 依赖声明
├── run_tests.py            # 测试入口脚本
└── README.md               # 项目说明文档
```

## 文件功能说明

| 文件 | 主要能力 |
|------|----------|
| `run_tests.py` | 测试执行入口，加载用例、执行测试、生成报告 |
| `config.py` | 全局配置管理（Agent地址、测试参数、阈值配置） |
| `src/agent_client.py` | Agent API调用封装，支持真实API和mock双模式 |
| `src/test_case_loader.py` | Excel用例文件加载，MD5基线校验 |
| `src/test_executor.py` | 测试用例执行引擎，支持多轮重试和抖动检测 |
| `src/agent_eval.py` | Agent效果评测（准确率、完整性、一致性计算） |
| `src/aiops_lab.py` | 性能指标计算（Token消耗、延迟、抖动率） |
| `src/skill_spector.py` | 保真度评测，检测信息虚构和丢失 |
| `src/schema_validator.py` | 结构化输出Schema合规校验 |
| `src/batch_validator.py` | 批次测试结果合规性校验（通过率、波动检测） |
| `src/report_generator.py` | 多格式报告生成（HTML、Markdown、JSON） |

## 环境要求

- Python 3.8+
- 依赖包见 `requirements.txt`

## 部署步骤

### 1. 安装依赖

```bash
cd agent-tester
pip install -r requirements.txt
```

### 2. 配置Agent服务

编辑 `config.py` 配置Agent连接信息：

```python
AGENT_CONFIG = {
    "name": "简历结构化专家",
    "api_url": "http://localhost:8000/api/v1/resume/parse",
    "api_key": "",
    "timeout": 60,
}
```

### 3. 启动Agent服务（可选）

如果使用真实Agent服务，需先启动：

```bash
# 进入Agent服务目录
cd ../resume-agent-service
python run.py
```

服务启动后访问：
- API地址: http://localhost:8000/api/v1/resume/parse
- API文档: http://localhost:8000/docs

## 运行测试

### 基本用法

```bash
# 运行所有测试用例
python run_tests.py

# 指定报告格式
python run_tests.py --report-format html
python run_tests.py --report-format markdown
python run_tests.py --report-format json

# 多种格式同时生成
python run_tests.py --report-format html markdown json
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--report-format` | 报告输出格式（html/markdown/json） | html |
| `--fail-fast` | 是否快速失败（遇到失败立即停止） | False |
| `--repeat-count` | 单例重复执行次数 | 3 |
| `--jitter-threshold` | 抖动率阈值（%） | 1.0 |

### 测试配置

在 `config.py` 中可配置以下参数：

```python
TEST_CONFIG = {
    "test_case_file": "test_cases/简历结构化测试用例（demo）.xlsx",
    "output_dir": "reports",
    "fail_fast": False,
    "max_retries": 1,
    "repeat_count": 3,           # 单例重复执行次数
    "jitter_threshold": 1.0,     # 抖动率阈值（%）
    "fluctuation_threshold": 1.0,# 指标波动阈值（%）
    "concurrency": 1,            # 并发数
    "debug_mode": True,          # 调试模式
}
```

## CI/CD 集成

### GitHub Actions 示例

创建 `.github/workflows/test.yml`：

```yaml
name: Agent Test CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python run_tests.py --report-format html
    
    - name: Upload report
      uses: actions/upload-artifact@v3
      with:
        name: test-report
        path: reports/
```

### GitLab CI 示例

创建 `.gitlab-ci.yml`：

```yaml
stages:
  - test

agent_test:
  stage: test
  image: python:3.10-slim
  before_script:
    - pip install --upgrade pip
    - pip install -r requirements.txt
  script:
    - python run_tests.py --report-format html
  artifacts:
    paths:
      - reports/
```

## 测试报告

测试完成后在 `reports/` 目录生成三种格式的报告：

1. **HTML报告**：可视化测试结果，包含详细统计图表
2. **Markdown报告**：便于文档集成和版本控制
3. **JSON报告**：便于程序分析和数据处理

## 测试标准

### 用例通过标准
- PASS：总分 ≥ 96分
- WARN：72分 ≤ 总分 ＜ 96分
- FAIL：总分 ＜ 72分

### 版本准出标准
- 用例通过率 ≥ 95%
- 核心字段错误率 ≤ 3%
- 无任何一票否决类严重缺陷

### 一票否决规则
- 核心联系方式（手机号、邮箱）抽取错误或缺失
- 篡改核心履历信息
- 编造虚假信息
- 批量抽取出现数据混淆

## 工程化SOP

| SOP | 说明 |
|-----|------|
| SOP1 | 模型推理参数强制固化（Temperature=0、固定Seed） |
| SOP2 | 评测环境全量锁死（冻结Prompt、工具链版本） |
| SOP3 | 测试基线永久冻结（用例MD5校验） |
| SOP4 | 多轮复测防抖降噪（单例3次执行） |
| SOP5 | 刚性规则自动判定（精准字符串匹配） |
| SOP6 | 版本对比防抖阈值（波动≤1%判定持平） |
| SOP7 | 批次最终合规兜底（准出终审） |

## 联系信息

如有问题或建议，请联系项目维护人员。

---

*文档版本: v1.0 | 更新时间: 2026-06-15*