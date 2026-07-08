# Homework Magic - System Architecture

## Overview

Homework Magic is an AI-powered homework platform for UK primary school students (Year 1-6, ages 5-11). It covers KS1, KS2, and 11+ exam preparation. The system generates personalised homework, reviews student answers, provides detailed explanations, and tracks learning progress.

## Tech Stack

| Layer | Technology                                      | Purpose |
|-------|-------------------------------------------------|---------|
| Web Framework | FastAPI + Uvicorn                               | Async REST API server |
| Frontend | Vanilla HTML/JS + Marked.js                     | SPA with markdown rendering |
| LLM Backend | Ollama (dev) / LLM API (prod)                   | Homework generation, review, practice |
| Vector DB | ChromaDB                                        | RAG storage for homework content |
| Embedding | sentence-transformers (dev) / OpenAI API (prod) | Semantic search embeddings |
| Progress DB | SQLite (WAL mode)                               | Student progress tracking |
| Caching | In-memory TTL LRU cache                         | Reduce redundant LLM calls |
| Observability | Langfuse (self-hosted)                          | LLM call tracing and quality scoring |
| Payments | Stripe                                          | Subscription management |

## Architecture Diagram

```
                    +------------------+
                    |   Browser (SPA)  |
                    |  app.html / etc  |
                    +--------+---------+
                             |
                      HTTP REST API
                             |
                    +--------v---------+
                    |   FastAPI Server |
                    |    web_app.py    |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v------+  +---v----+  +------v-------+
     |  AI Workflow   |  |  RAG   |  |  Progress DB |
     | agent_workflow |  | Chroma |  |   SQLite     |
     | .py            |  |  DB    |  |  progress_db |
     +--------+------+  +---+----+  +--------------+
              |              |
     +--------v------+  +---v-----------+
     |  LLM Client   |  |  Embedding    |
     | llm_client.py |  |  (local/API) |
     | Ollama / API  |  |  sentence-    |
     +---------------+  |  transformers |
                        +---------------+
```

## Key Modules

### Entry Points
- **`web_app.py`** - Main FastAPI application, all REST endpoints and page routes
- **`launch.py`** - Server launcher (dev/prod modes)
- **`main.py`** - Legacy Streamlit TUI entry point

### AI Pipeline
- **`src/llm_client.py`** - LLM client supporting Ollama (local) and OpenAI-compatible API
- **`src/homework_generator.py`** - Homework generation with RAG retrieval + LLM generation, parallel subject generation
- **`src/homework_rag.py`** - ChromaDB RAG store with local/API embedding support
- **`src/agent_workflow.py`** - Multi-step agent workflow (reactive/deliberative modes)
- **`src/prompts.py`** - All prompt templates (homework, review, explain, practice)

### Data Layer
- **`src/progress_db.py`** - SQLite progress tracking (students, sessions, topics, practice)
- **`src/cache.py`** - TTL LRU cache for homework, review, explain, practice results
- **`src/models.py`** - Pydantic models, student profiles, tool definitions

### Admin & Observability
- **`src/admin.py`** - Admin business logic (metrics, cache management, subscriptions)
- **`src/observability.py`** - Langfuse integration for LLM tracing

### Frontend
- **`templates/app.html`** - Main SPA (Quick Select, Custom Profile, Check Homework, 11+ Practice)
- **`static/index.html`** - Landing page
- **`static/ks1-homework.html`** - KS1 SEO page
- **`static/ks2-homework.html`** - KS2 SEO page
- **`static/elevenplus-practice.html`** - 11+ practice SEO page
- **`static/check-my-homework.html`** - Homework checker SEO page
- **`static/pricing.html`** - Subscription pricing page
- **`static/admin.html`** - Admin dashboard SPA

## Data Flow

### Homework Generation (Quick Select - Free)
```
User selects Year + Subjects
    -> POST /api/generate (quick_select=true)
    -> resolve_profile() builds simple profile
    -> generate_homework_parallel() for all subjects
        -> For each subject (parallel threads):
            1. Check memory cache (TTLCache)
            2. Search RAG for existing homework
            3. If found: return cached homework (zero LLM cost)
            4. If not found: LLM generates new homework
            5. Store new homework in RAG + cache
    -> Return homework list to frontend
    -> Display in question column with answer inputs
```

### Homework Review (Requires Registration + Subscription)
```
User enters answers -> clicks "Check Answers"
    -> POST /api/review
    -> Check review cache
    -> LLM reviews answers against homework
    -> Save progress to SQLite
    -> Return feedback with score
```

### Help Me Improve (Practice Generation)
```
User clicks "Help me improve" after answering homework
    -> POST /api/improve-practice
    -> LLM analyses weak areas from answers + review feedback
    -> Generates targeted practice questions
    -> Practice displayed in question column (replaces homework)
    -> User can input answers in answer area
    -> User clicks "Check Answers" to review practice
```

## Access Control (Paywall)

| Feature | Access Level |
|---------|-------------|
| Quick Select (generate homework) | Free - no registration required |
| Custom Profile (personalised homework) | Registration + Subscription required |
| Check Homework (AI marking) | Registration + Subscription required |
| Track Progress (dashboard) | Registration + Subscription required |
| 11+ Practice (quick generate) | Free - no registration required |
| Help Me Improve (practice) | Available after generating homework |

## Performance Optimisation

### Latency Bottleneck Analysis

| Bottleneck | Impact | Solution |
|-----------|--------|----------|
| Embedding API calls (every RAG op) | ~200-500ms per call | Local sentence-transformers model |
| Sequential subject generation | N * LLM_latency | ThreadPoolExecutor parallel generation |
| LLM API round-trip | ~2-10s per call | Ollama local model for dev; caching |
| Profile parsing (LLM call) | ~2-5s | Cache parsed profiles |
| No caching | Repeated identical requests | TTL LRU cache for all LLM outputs |

### Caching Strategy

| Cache | TTL | Max Size | Purpose |
|-------|-----|----------|---------|
| homework_cache | 1 hour | 500 | Same subject + year homework |
| review_cache | 30 min | 2000 | Same homework + answers review |
| explain_cache | 30 min | 1000 | Same deep explanation |
| practice_cache | 30 min | 1000 | Same practice questions |
| subject_extraction_cache | 24 hours | 200 | Same subject extraction |
| profile_parse_cache | 24 hours | 200 | Same profile parsing |

## Database Schema

See `database_schema.md` for the full relational schema.

### SQLite Tables (progress_db.py)
- **students** - Student profiles (student_id, name, year_group, age)
- **homework_sessions** - Homework review records (scores, answers, feedback)
- **topic_progress** - Per-topic accuracy tracking
- **practice_sessions** - Practice session records

### ChromaDB Collections
- **homework_collection** - Generated homework with metadata (year_group, subject, key_stage)
- **chinese_collection** - Chinese textbook content
- **elevenplus_collection** - 11+ practice content

## UK GDPR Compliance

- All student data stored locally (SQLite)
- Right to erasure: `DELETE /api/admin/users/<id>` removes all student data
- No data sent to third parties except LLM API (configurable)
- Data minimisation: only essential student info collected
