# Homework Magic - 英国小学 AI 辅导系统

为英国小学学生（Year 1-6，5-11 岁）提供 AI 驱动的作业生成和批改服务，完全对齐英国国家课程标准。可生成个性化作业、批改学生作业（包括通过 OCR 识别手写照片），并提供鼓励性反馈。同时支持 11+ 考试准备。

## 架构

FastAPI Web 应用，包含：
- **后端**: FastAPI + Uvicorn
- **AI**: LangChain + LangGraph 混合智能体（反应式 + 深思式模式）
- **向量存储**: ChromaDB 用于作业 RAG（检索增强生成）
- **LLM**: 使用 QWEN
- **前端**: 自定义 HTML/JS 单页应用

## 功能

- **作业生成**: 根据年级、优势和兴趣生成适合年龄的作业
- **多学科支持**: 数学、英语、科学、历史、地理、西班牙语、法语、拉丁语、中文等
- **11+ 准备**: 语法学校入学考试的言语推理、非言语推理、数学、英语
- **即时批改**: AI 批改作业，提供鼓励性反馈、分数和改进建议
- **文件上传**: 支持图片（JPG、PNG、HEIC）、PDF 和文本文件提交作业
- **OCR**: 使用多模态 LLM 从照片中读取手写作业
- **RAG 系统**: 使用向量相似性搜索存储和检索作业
- **学生档案**: 根据年级、水平和薄弱领域进行个性化学习
- **SEO 页面**: KS1、KS2、11+ 和作业检查的静态着陆页

## 环境要求

- Python 3.10+
- QWEN API Key（用于 LLM 访问）

## 快速开始

```bash
# 设置 API Key
export DEFAULT_API_KEY="your-api-key"

# （可选）启用 LangSmith 追踪调试
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-langsmith-key"

# 安装依赖
pip install -r requirements.txt

# 运行应用
python web_app.py
```

应用将在 `http://localhost:5000` 启动（或通过 `PORT` 环境变量指定的端口）。

## 项目结构

```
ai_tutor/
├── web_app.py                    # FastAPI 应用（主服务器）
├── launch.py                     # 统一启动器（生成 SEO 页面，启动 web_app.py）
├── generate_landing_pages.py     # 生成 SEO 优化的静态着陆页
├── requirements.txt              # Python 依赖
├── run.sh / run.bat              # 启动脚本
│
├── src/
│   ├── models.py                 # 数据模型、学生档案、LangChain 工具
│   ├── prompts.py                # 所有 LLM 提示模板
│   ├── agent_workflow.py         # LangGraph 混合智能体工作流
│   ├── homework_generator.py     # 作业生成逻辑
│   ├── homework_manager.py       # 作业保存/加载/批改/CSV 管理
│   ├── homework_rag.py           # RAG 系统（ChromaDB）用于作业存储和搜索
│   ├── elevenplus_rag.py         # 11+ 知识库 RAG 系统
│   ├── file_utils.py             # 文件读取工具（图片 OCR、PDF、DOCX、文本）
│   │
│   ├── ui/
│   │   ├── shared.py             # 共享 UI 工具（档案解析、作业显示）
│   │   └── tui.py                # 终端 UI（CLI 模式）
│   │
│   │── scripts/                  # 批量生成脚本
│   │   └── elevenplus/           # 11+ 作业生成器 
│   │
├── templates/
│   ├── app.html                  # 主 AI 辅导 Web 应用（SPA）
│   ├── homework.html             # 作业显示模板
│   └── elevenplus-practice.html  # 11+ 练习页面模板
│
── static/
│   ├── index.html                # SEO 首页
│   ├── ks1-homework.html         # KS1 SEO 着陆页
│   ├── ks2-homework.html         # KS2 SEO 着陆页
│   ├── check-my-homework.html    # 作业检查 SEO 页面
│   ├── elevenplus-practice.html  # 11+ 练习页面
│   ├── styles.css                # 共享 CSS 样式表
│   └── elevenplus/               # 11+ 专用静态内容
│       ├── articles.html         # 11+ 文章中心
│       ├── uk_grammar_guide.html # 英国语法指南
│       └── uk_11plus_vocabulary_list.html  # 11+ 词汇表
│
├── data/
│   ├── homework.csv              # 示例作业数据
│   ├── chroma_homework_db/       # ChromaDB 向量存储
│   ├── chinese/                  # 中文教材 PDF
│   └── elevenplus/               # 11+ 知识库数据
│
└── homework_output/              # 生成的作业输出文件
```

## API 端点

### Web 页面
- `GET /` - 首页
- `GET /ks1-homework` - KS1 作业着陆页
- `GET /ks2-homework` - KS2 作业着陆页
- `GET /elevenplus-practice` - 11+ 练习着陆页
- `GET /elevenplus/articles` - 11+ 文章中心
- `GET /elevenplus/uk-grammar-guide` - 英国语法指南
- `GET /elevenplus/11plus-vocabulary-list` - 11+ 词汇表
- `GET /check-my-homework` - 作业检查着陆页
- `GET /app` - 主 AI 辅导应用

### REST API
- `GET /api/health` - 健康检查
- `GET /api/subjects` - 列出可用科目
- `GET /api/year-groups` - 列出年级组
- `POST /api/generate` - 生成作业
- `POST /api/review` - 批改作业
- `GET /api/quick-profile/{year}` - 获取示例学生档案
- `POST /api/sessions` - 创建辅导会话
- `GET /api/sessions/{id}` - 获取会话
- `PUT /api/sessions/{id}` - 更新会话
- `DELETE /api/sessions/{id}` - 删除会话
- `POST /api/upload-file` - 上传作业文件
- `POST /api/upload-photo` - 上传照片进行 OCR

## 科目列表

**小学 (KS1-KS2)**: 数学、英语、科学、历史、地理、设计与技术、艺术与设计、计算机、拉丁语、西班牙语、法语、中文、宗教教育、音乐、体育

**11+ 准备**: 数学、英语、言语推理、非言语推理

## 许可证

专有 - 保留所有权利
