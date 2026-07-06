# AI Tutor - AI Monitoring Dashboard Design Document

See design sections:

-   Overview
-   Architecture
-   Database (ai_requests)
-   Logging middleware
-   Langfuse integration
-   Admin pages (Dashboard, Live Requests, Conversations, RAG Inspector,
    Analytics, Cost, Feedback, Models)
-   Backend APIs
-   Frontend routes
-   Security
-   Acceptance criteria

Detailed requirements:

Implement automatic logging of every LLM request including prompts, RAG
context, response, latency, tokens, provider, model, homework metadata
and Langfuse trace IDs. Store in PostgreSQL. Build React admin pages to
inspect requests, conversations, RAG retrieval, analytics, token usage,
costs, failures, feedback and model comparison. Support Ollama, OpenAI,
Gemini, DeepSeek, Qwen and Azure OpenAI through a common interface.
Provide admin-only access, search/filtering, exports, charts and live
updates.
