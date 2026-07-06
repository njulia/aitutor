# Homework Magic - API Reference

Base URL: `http://localhost:5000`

## Page Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page |
| GET | `/ks1-homework` | KS1 homework SEO page |
| GET | `/ks2-homework` | KS2 homework SEO page |
| GET | `/elevenplus-practice` | 11+ practice SEO page |
| GET | `/check-my-homework` | Homework checker SEO page |
| GET | `/pricing` | Subscription pricing page |
| GET | `/app` | Main SPA (AI tutor) |
| GET | `/progress` | Progress dashboard |
| GET | `/admin` | Admin dashboard |

## Public API Endpoints

### Health Check
```
GET /api/health
Response: {"status": "ok", "initialized": true}
```

### Get Subjects
```
GET /api/subjects
Response: {
    "primary": ["Maths", "English", "Spanish", ...],
    "eleven_plus": ["Maths", "English", "Verbal Reasoning", "Non-Verbal Reasoning"]
}
```

### Get Year Groups
```
GET /api/year-groups
Response: {
    "year_groups": [1, 2, 3, 4, 5, 6],
    "quick_select": [
        {"year": 1, "age": 5, "stage": "KS1"},
        ...
    ]
}
```

### Generate Homework
```
POST /api/generate
Content-Type: application/json

Request (Quick Select - Free):
{
    "quick_select": true,
    "year": 3,
    "subjects": ["Maths", "English"],
    "student_id": "optional_id"
}

Request (Custom Profile - Requires Subscription):
{
    "quick_select": false,
    "profile": {
        "description": "Ana is a 7-year-old in Year 2..."
    },
    "subjects": ["Maths"]
}

Response:
{
    "success": true,
    "homework": [
        {"subject": "Maths", "content": "...", "doc_id": "1234567890"}
    ],
    "profile": {"year_group": 3, "age": 7, "student_id": "student_3"}
}
```

### Review Homework
```
POST /api/review
Content-Type: application/json

Request:
{
    "homework": "homework question text...",
    "answers": "student's answers...",
    "subject": "Maths",
    "profile": {"year_group": 3, "student_id": "student_3"}
}

Response:
{
    "success": true,
    "review": "## Score: 7/10\n\n..."
}
```

### Deep Explanation
```
POST /api/explain-deep
Content-Type: application/json

Request:
{
    "homework": "...",
    "answers": "...",
    "subject": "Maths",
    "profile": {...},
    "review_feedback": "optional prior review text"
}

Response:
{
    "success": true,
    "explanation": "## Deep Explanation..."
}
```

### Improve Practice
```
POST /api/improve-practice
Content-Type: application/json

Request:
{
    "homework": "...",
    "answers": "...",
    "subject": "Maths",
    "profile": {...},
    "review_feedback": "..."
}

Response:
{
    "success": true,
    "practice": "## Practice Questions..."
}
```

### Get Progress
```
GET /api/progress/{student_id}?subject=Maths

Response:
{
    "success": true,
    "summary": {
        "overall": {"total_sessions": 10, "avg_accuracy": 75.0},
        "by_subject": [
            {"subject": "Maths", "avg_accuracy": 80.0, "total_sessions": 5}
        ]
    },
    "score_history": [
        {"subject": "Maths", "score": 8.0, "max_score": 10, "created_at": "..."}
    ],
    "topics": [...]
}
```

### File Upload
```
POST /api/upload-file
Content-Type: multipart/form-data

File: homework.txt

Response:
{
    "success": true,
    "content": "extracted text...",
    "is_image": false
}
```

### Photo Upload (OCR)
```
POST /api/upload-photo
Content-Type: application/json

Request:
{
    "photo": "data:image/jpeg;base64,..."
}

Response:
{
    "success": true,
    "content": "OCR extracted text..."
}
```

### Feedback
```
POST /api/feedback
Content-Type: application/json

Request:
{
    "trace_id": "langfuse-trace-id",
    "score": 1.0,
    "name": "user_feedback",
    "comment": "Great explanation!"
}
```

### Session Management
```
POST /api/sessions          -> Create session
GET  /api/sessions/{id}     -> Get session
PUT  /api/sessions/{id}     -> Update session
DELETE /api/sessions/{id}   -> Delete session
```

### Subscription
```
POST /api/create-subscription
Request: {"email": "...", "name": "...", "duration": "5_days" | "30_days"}
```

## Admin API Endpoints

### Overview
```
GET /api/admin/overview
Response: {
    "sessions": {...},
    "total_students": 42,
    "langfuse_enabled": true,
    "timestamp": "..."
}
```

### User Management
```
GET    /api/admin/users?limit=100&offset=0    -> List students
GET    /api/admin/users/{student_id}          -> Student detail
PUT    /api/admin/users/{student_id}          -> Update student
DELETE /api/admin/users/{student_id}          -> Delete student (GDPR erasure)
```

### Subscriptions
```
GET /api/admin/subscriptions
Response: {
    "active_subscriptions": 10,
    "estimated_revenue_gbp": 99.50,
    "subscriptions": [...]
}
```

### AI Metrics
```
GET /api/admin/ai-metrics
Response: {
    "sessions": {...},
    "cache": {
        "homework": {"size": 50, "hits": 200, "misses": 100, "hit_rate": "66.7%"},
        ...
    },
    "system": {"langfuse_enabled": true, "timestamp": "..."}
}
```

### AI Evaluation
```
GET /api/admin/ai-evaluation
Response: {
    "total_reviews": 100,
    "average_score": 7.2,
    "score_distribution": [...],
    "by_subject": [...],
    "daily_trend": [...]
}
```

### Cache Management
```
POST /api/admin/cache/clear
Response: {"success": true, "cleared": {"homework": 50, "review": 100, ...}}
```
