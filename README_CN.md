# AI Tutor - Hybrid English Tutor

基于 LangGraph 的混合智能体 AI 辅导系统，为英国小学学生（Year 1-6）提供智能课后辅导服务。

## 架构

三层混合智能体架构：

1. **底层 (Reactive)**：即时响应用户问题，提供快速反馈
2. **中间层 (Coordination)**：评估问题类型和难度，动态选择处理模式
3. **顶层 (Deliberative)**：学习分析，制定个性化学习计划

## 功能

- 根据 UK Department for Education 指南，按年龄段生成英语作业
- 自动识别科目（支持 Math、English、Science、History、Geography 等）
- 作业点评与反馈
- 学生学习数据分析与个性化推荐
- 内置《中文》教材（第一册至第十二册）PDF 资源

## 环境要求

- Python 3.10+
- AGICTO API Key

## 快速开始

```bash
# 设置 API Key
export AGICTO_API_KEY="your-api-key"

# （可选）启用 LangSmith 追踪调试
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-langsmith-key"

# 安装依赖
pip install langchain-openai langchain-core langgraph pydantic

# 运行
python hybrid_english_tutor_langgraph.py
```

## 项目结构

```
ai_tutor/
├── hybrid_english_tutor_langgraph.py  # 主程序：LangGraph 混合智能体
├── prompts.py                         # Prompt 模板
├── gui_template.html                  # 前端界面模板
├── styles.css                         # 样式文件
└── chinese/                           # 《中文》教材 PDF 资源（1-12 册）
```

## 科目列表

Math、English、Science、History、Geography、Design and Technology、Art and Design、Computing、Latin、Spanish、Chinese
