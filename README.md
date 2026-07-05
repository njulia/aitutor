# Homework Magic - AI Tutor for UK Primary Schools

An AI-powered homework generator and marker for UK primary school students (Year 1-6, ages 5-11), aligned to the UK National Curriculum. Generates personalised homework, marks student submissions (including handwritten photos via OCR), and provides encouraging feedback. Also covers 11+ exam preparation.

## Architecture

FastAPI web application with:
- **Backend**: FastAPI + Uvicorn
- **AI**: LangChain + LangGraph hybrid agent (reactive + deliberative modes)
- **Vector Store**: ChromaDB for homework RAG (Retrieval-Augmented Generation)
- **LLM**: DeepSeek via AGICTO API
- **Frontend**: Custom HTML/JS single-page application

## Features

- **Homework Generation**: Creates age-appropriate homework based on year group, strengths, and interests
- **Multi-Subject Support**: Maths, English, Science, History, Geography, Spanish, French, Latin, Chinese, and more
- **11+ Preparation**: Verbal Reasoning, Non-Verbal Reasoning, Maths, English for grammar school entrance
- **Instant Marking**: AI reviews homework with encouraging feedback, scores, and improvement suggestions
- **File Upload**: Supports images (JPG, PNG, HEIC), PDF, and text files for homework submission
- **OCR**: Reads handwritten homework from photos using multimodal LLM
- **RAG System**: Stores and retrieves homework using vector similarity search
- **Student Profiles**: Personalised learning based on year group, level, and weak areas
- **SEO Pages**: Static landing pages for KS1, KS2, 11+, and homework checking

## Requirements

- Python 3.10+
- AGICTO API Key (for LLM access)

## Quick Start

```bash
# Set API Key
export QWEN_API_KEY="your-api-key"

# (Optional) Enable LangSmith tracing for debugging
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-langsmith-key"

# Install dependencies
pip install -r requirements.txt

# Run the application
python web_app.py
```

The application will start at `http://localhost:5000` (or the port specified in the `PORT` environment variable).

## Project Structure

```
ai_tutor/
├── web_app.py                    # FastAPI application (main server)
├── launch.py                     # Unified launcher (generates SEO pages, starts web_app.py)
── generate_landing_pages.py     # Generates SEO-optimised static landing pages
├── requirements.txt              # Python dependencies
├── run.sh / run.bat              # Launcher scripts
│
├── src/
│   ├── models.py                 # Data models, student profiles, LangChain tools
│   ├── prompts.py                # All LLM prompt templates
│   ├── agent_workflow.py         # LangGraph hybrid agent workflow
│   ├── homework_generator.py     # Homework generation logic
│   ├── homework_manager.py       # Homework save/load/review/CSV management
│   ├── homework_rag.py           # RAG system (ChromaDB) for homework storage & search
│   ├── file_utils.py             # File reading utilities (image OCR, PDF, DOCX, text)
│   │
│   ├── ui/
│   │   ├── shared.py             # Shared UI utilities (profile parsing, homework display)
│   │   └── tui.py                # Terminal UI (CLI mode)
│   │
│   ├── elevenplus/               # 11+ exam preparation module
│   │   ├── elevenplus_rag.py     # RAG system for 11+ knowledge base
│   │   ├── prompts.py            # 11+ specific prompt templates
│   │   └── generate_11plus_*.py  # 11+ homework generators
│   │
│   └── scripts/                  # Batch generation scripts
│
├── templates/
│   ├── app.html                  # Main AI tutor web application (SPA)
│   ├── homework.html             # Homework display template
│   └── elevenplus-practice.html  # 11+ practice page template
│
├── static/
│   ├── index.html                # SEO homepage
│   ├── ks1-homework.html         # KS1 SEO landing page
│   ├── ks2-homework.html         # KS2 SEO landing page
│   ├── check-my-homework.html    # Homework checker SEO page
│   ├── elevenplus-practice.html  # 11+ practice page
│   ├── styles.css                # Shared CSS stylesheet
│   └── elevenplus/               # 11+ specific static content
│       ├── articles.html         # 11+ articles hub
│       ├── uk_grammar_guide.html # UK Grammar Guide
│       └── uk_11plus_vocabulary_list.html  # 11+ Vocabulary List
│
├── data/
│   ├── homework.csv              # Sample homework data
│   ├── chroma_homework_db/       # ChromaDB vector store
│   ├── chinese/                  # Chinese textbook PDFs
│   └── elevenplus/               # 11+ knowledge base data
│
└── homework_output/              # Generated homework output files
```

## API Endpoints

### Web Pages
- `GET /` - Homepage
- `GET /ks1-homework` - KS1 homework landing page
- `GET /ks2-homework` - KS2 homework landing page
- `GET /elevenplus-practice` - 11+ practice landing page
- `GET /elevenplus/articles` - 11+ articles hub
- `GET /elevenplus/uk-grammar-guide` - UK Grammar Guide
- `GET /elevenplus/uk-11plus-vocabulary-list` - 11+ Vocabulary List
- `GET /check-my-homework` - Homework checker landing page
- `GET /app` - Main AI tutor application

### REST API
- `GET /api/health` - Health check
- `GET /api/subjects` - List available subjects
- `GET /api/year-groups` - List year groups
- `POST /api/generate` - Generate homework
- `POST /api/review` - Review/mark homework
- `GET /api/quick-profile/{year}` - Get sample student profile
- `POST /api/sessions` - Create tutoring session
- `GET /api/sessions/{id}` - Get session
- `PUT /api/sessions/{id}` - Update session
- `DELETE /api/sessions/{id}` - Delete session
- `POST /api/upload-file` - Upload homework file
- `POST /api/upload-photo` - Upload photo for OCR

## Subjects

**Primary (KS1-KS2)**: Maths, English, Science, History, Geography, Design and Technology, Art and Design, Computing, Latin, Spanish, French, Chinese, RE, Music, PE

**11+ Preparation**: Maths, English, Verbal Reasoning, Non-Verbal Reasoning

## License

Proprietary - All rights reserved
