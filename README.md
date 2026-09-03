# Homework Magic

Homework Magic is a FastAPI web application for UK primary-school homework,
guided 11+ practice, timed mock exams, marking and parent-managed child
progress.

The request path is RAG-first: it searches the PostgreSQL/pgvector homework
library by exact year and subject before it can call an LLM. A genuine library
miss may create one new worksheet and private answer key, then stores that set
for future reuse. Retrieved answer keys are used for deterministic marking;
saved teaching methods are rendered locally and are never copied into a later
model prompt.

## Main improvements in this version

- Guided primary and 11+ profile fields are validated, bounded and stripped of
  direct identifiers.
- Successful checked activities now feed an effort-first reward system with
  daily and weekly quests, permanent XP, separate Gift Points, printable
  certificates and parent-approved Homework Magic branded gifts.
- Requested session length now controls the number of returned questions.
- Guided 11+ access is checked before any expensive generation.
- Original, locally scored 11+ mocks are separated into common four-subject and
  school-target formats. Public school, council and government pages are used
  only for format and curriculum guidance; paid papers are never copied.
- The £9.99/month `elevenplus_monthly` plan includes guided 11+ practice and
  the paid mock catalogue. A short diagnostic remains free.
- RAG methods are first-write-wins and reused under opaque hashes.
- Static pages use short public caches, assets use revalidation caches, and
  responses larger than 1 KB are compressed.
- `robots.txt`, the canonical sitemap, permanent legacy redirects and article
  metadata have automated SEO contracts.
- Production settings fail closed when database, legal, email or provider
  configuration is unsafe.
- The container runs as an unprivileged user on Python 3.12.

## Local setup

Python 3.12 is the supported runtime.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
uvicorn web_app:app --host 127.0.0.1 --port 5000 --reload
```

The local template uses SQLite and Ollama. Start Ollama separately, or change
the provider settings in `.env`. Do not commit `.env` or any credentials.

Open:

- Website: `http://127.0.0.1:5000/`
- Tutor: `http://127.0.0.1:5000/app`
- 11+ mocks: `http://127.0.0.1:5000/elevenplus-mock-exams`
- Health: `http://127.0.0.1:5000/api/health`
- Readiness: `http://127.0.0.1:5000/api/ready`

## RAG-first request flow

1. Canonicalise the requested year and subject.
2. Read the learner's assigned document IDs.
3. query exact metadata in the homework or 11+ collection, excluding assigned
   sets where rotation is required.
4. Claim one unseen document atomically and return it.
5. Only after a true miss, call the configured provider once, split the public
   worksheet from its private answer key, and write it to RAG.

Selected year-round weeks are stable and may be reopened. General practice
rotates through unseen library items. A RAG outage is logged and can fall back
to generation so a child is not left without a response.

## Tests

```bash
python -m compileall web_app.py src scripts
node --check static/js/app.js
pytest test/unit test/api test/integration
```

For browser tests:

```bash
python -m playwright install chromium
RUN_E2E=1 pytest test/e2e --browser chromium
```

See [doc/TESTING.md](doc/TESTING.md) and
[doc/END_TO_END_TESTING.md](doc/END_TO_END_TESTING.md).

## Project layout

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

## API Endpoints

### Web pages

- `web_app.py` — FastAPI routes and browser response contracts
- `src/homework_generator.py` — RAG-first assignment and miss generation
- `src/homework_rag.py` / `src/elevenplus_rag.py` — vector-library contracts
- `src/elevenplus_mock_exams.py` — original mock catalogue, signed attempts and
  deterministic local marking
- `src/webapp/` — account, billing, safety, review and runtime services
- `src/webapp/reward_store.py` / `reward_routes.py` — quests, XP, certificates
  and parent-controlled branded gift orders
- `static/` — public pages and dependency-free learner interface
- `scripts/` — original/open-curriculum question generators and maintenance
- `test/` — unit, API, integration and browser coverage
- `deploy/` — reviewed Cloud Run environment and deployment templates
- `doc/` — test, release and privacy guidance

## Privacy and safety

Parent notes are minimised before use and are not persisted in browser
preferences. Clear emails, phone numbers, postcodes, URLs, names and school
disclosures are removed from prompt inputs. Raw learner and AI content storage
is off by default. Production startup validates public operator details,
transactional email, secure cookies, exact CORS origins, PostgreSQL and provider
credentials.

Parents and guardians should still avoid entering a child's full name, school,
address, phone number, email, exact birthday or password.

Reward records contain pseudonymous learner/account IDs and fixed event labels,
not homework answers or marks. XP is permanent and never deducted. A separate
Gift Points balance is used for branded gift orders. Only a signed-in parent or
guardian can approve an order and enter an adult recipient's UK address. The
address is encrypted, excluded from learner-facing responses, removed after
cancellation, and scheduled for deletion 30 days after dispatch.
