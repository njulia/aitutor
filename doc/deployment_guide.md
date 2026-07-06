# Homework Magic - Deployment Guide

## Development Setup (Ollama + Local Embeddings)

This setup uses Ollama for LLM and sentence-transformers for embeddings. Zero API costs.

### Prerequisites

1. **Python 3.10+**
2. **Ollama** - Install from https://ollama.com

### Step 1: Install Ollama and Pull Models

```bash
# Install Ollama (Windows/Mac/Linux)
# Download from https://ollama.com

# Pull required models
ollama pull qwen2.5:7b        # Main LLM for homework generation/review
ollama pull qwen3.6:35b       # AI coding (optional)
ollama pull llava:7b          # Vision model for OCR (optional)
ollama pull nomic-embed-text  # Embedding model (optional, fallback)
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs `sentence-transformers` for local embeddings (auto-downloads `all-MiniLM-L6-v2` model on first use).

### Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```env
# LLM Backend: "ollama" for local, "api" for cloud
LLM_PROVIDER=ollama

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_VISION_MODEL=llava:7b

# Embedding: "local" for sentence-transformers, "api" for cloud
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Stripe (optional, for subscription testing)
STRIPE_SECRET_KEY=sk_test_...

# Admin (optional)
ADMIN_TOKEN=your-admin-token

# Langfuse (optional, for observability)
LANGFUSE_ENABLED=false
```

### Step 4: Start the Server

```bash
# Development mode
python web_app.py

# Or use the launcher
python launch.py
```

The server starts at `http://localhost:5000`.

### Step 5: Verify

```bash
# Health check
curl http://localhost:5000/api/health

# Expected: {"status": "ok", "initialized": true}
```

## Production Setup (Cloud API)

### Environment Variables

```env
# LLM Backend
LLM_PROVIDER=api
AGICTO_API_KEY=your-api-key

# Embedding
EMBEDDING_PROVIDER=api
QWEN_API_KEY=your-embedding-key

# Stripe
STRIPE_SECRET_KEY=sk_live_...

# Admin
ADMIN_TOKEN=strong-random-token

# Langfuse
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://your-langfuse.example.com

# Server
PORT=5000
```

### Run with Gunicorn

```bash
gunicorn web_app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:5000
```

### Docker Deployment (Example)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV LLM_PROVIDER=api
ENV EMBEDDING_PROVIDER=local

EXPOSE 5000
CMD ["gunicorn", "web_app:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:5000"]
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `api` | LLM backend: `ollama` or `api` |
| `AGICTO_API_KEY` | - | API key for cloud LLM (required if `api`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Ollama model name |
| `OLLAMA_VISION_MODEL` | `llava:7b` | Ollama vision model |
| `EMBEDDING_PROVIDER` | `local` | Embedding backend: `local` or `api` |
| `LOCAL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local embedding model name |
| `QWEN_API_KEY` | - | API key for cloud embeddings |
| `STRIPE_SECRET_KEY` | - | Stripe secret key |
| `ADMIN_TOKEN` | - | Admin authentication token |
| `LANGFUSE_ENABLED` | `true` | Enable Langfuse tracing |
| `LANGFUSE_PUBLIC_KEY` | - | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | - | Langfuse secret key |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse server URL |
| `PORT` | `5000` | Server port |

## Switching Between Dev and Prod

### Development (Zero Cost)
```env
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=local
```

### Production (Cloud API)
```env
LLM_PROVIDER=api
AGICTO_API_KEY=your-key
EMBEDDING_PROVIDER=api
QWEN_API_KEY=your-key
```

### Hybrid (Local Embeddings + Cloud LLM)
```env
LLM_PROVIDER=api
AGICTO_API_KEY=your-key
EMBEDDING_PROVIDER=local
```

This is recommended for production to save on embedding API costs while using a more powerful cloud LLM.

## Data Storage

| Data | Location | Notes |
|------|----------|-------|
| Progress DB | `data/progress.db` | SQLite with WAL mode |
| ChromaDB (homework) | `data/chroma_homework_db/` | RAG vector store |
| ChromaDB (11+) | `data/chroma_11plus_db/` | 11+ RAG vector store |
| Uploaded files | `uploads/` | Temporary, deleted after processing |

## Troubleshooting

### Ollama Connection Error
```
[LLM:Ollama] Connection refused
```
- Ensure Ollama is running: `ollama serve`
- Check model is pulled: `ollama list`
- Verify URL: `curl http://localhost:11434/api/tags`

### Embedding Model Download
First run downloads the model (~80MB for `all-MiniLM-L6-v2`). If behind a proxy:
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### ChromaDB Collection Mismatch
If you switch embedding models, existing ChromaDB data becomes incompatible. Delete and recreate:
```bash
rm -rf data/chroma_homework_db data/chroma_11plus_db
```
