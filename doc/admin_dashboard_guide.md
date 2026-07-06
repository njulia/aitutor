# Homework Magic - Admin Dashboard Guide

## Access

Navigate to `http://localhost:5000/admin` in your browser.

The admin dashboard is a single-page application with five tabs:

1. **Overview** - System stats at a glance
2. **Users** - Student management
3. **Subscriptions** - Revenue and subscription tracking
4. **AI Monitor** - System health and cache performance
5. **AI Evaluation** - Quality scoring and feedback analysis

## Tab 1: Overview

Displays key metrics:
- Total homework sessions
- Total registered students
- Langfuse status (enabled/disabled)
- System timestamp

## Tab 2: Users (Student Management)

### Features
- **List all students** with their stats (sessions, average score)
- **View student detail** - See individual session history and topic progress
- **Edit student** - Update name, year group, age, active status
- **Delete student** - Permanently removes student and all related data (UK GDPR right to erasure)

### API Endpoints Used
```
GET    /api/admin/users           -> List students
GET    /api/admin/users/{id}      -> Student detail
PUT    /api/admin/users/{id}      -> Update student
DELETE /api/admin/users/{id}      -> Delete student (GDPR erasure)
```

### GDPR Compliance
When a student is deleted:
- All homework session records are removed
- All topic progress data is removed
- All practice session records are removed
- The student profile is deleted
- This operation is irreversible

## Tab 3: Subscriptions

### Features
- View active subscription count
- Estimated revenue (GBP)
- Recent subscription list with customer ID, status, and creation date

### Subscription Plans
| Plan | Duration | Description |
|------|----------|-------------|
| 5-Day | 5 days | Access to all premium features for 5 days |
| 30-Day | 30 days | Access to all premium features for 30 days |

### Features Behind Paywall
- Custom Profile (personalised homework)
- Check Homework (AI marking)
- Track Progress (dashboard)

### Features Available for Free
- Quick Select (generate homework by year group)
- 11+ Practice (quick generate)

## Tab 4: AI Monitor

### Metrics Displayed

#### Session Statistics
- Total homework sessions
- Average score across all sessions
- Sessions by subject
- Daily activity (last 30 days)

#### Cache Performance
| Cache | TTL | Purpose |
|-------|-----|---------|
| Homework | 1 hour | Same subject + year homework reuse |
| Review | 30 min | Same homework + answers review |
| Explain | 30 min | Deep explanation reuse |
| Practice | 30 min | Practice question reuse |
| Subject Extraction | 24 hours | Subject extraction from text |
| Profile Parse | 24 hours | Profile parsing from description |

Each cache shows:
- Current size (number of entries)
- Total hits / misses
- Hit rate percentage

#### System Status
- Langfuse enabled/disabled
- Last updated timestamp

### Clear Cache
Click "Clear All Caches" to reset all cache instances. This forces fresh LLM calls for subsequent requests.

## Tab 5: AI Evaluation

### Metrics Displayed
- Total reviews processed
- Average score
- Score distribution (histogram):
  - 9-10 (Excellent)
  - 7-8 (Good)
  - 5-6 (Average)
  - 3-4 (Needs Improvement)
  - 0-2 (Poor)
- Score breakdown by subject
- Daily trend chart

### User Feedback
Users can submit thumbs up/down feedback on AI responses via the frontend. These are recorded in Langfuse as scores and can be analysed in the Langfuse dashboard.

## Admin Authentication

Admin endpoints are protected by an optional token:

```env
# .env
ADMIN_TOKEN=your-secret-token
```

If `ADMIN_TOKEN` is not set, all admin requests are allowed (development mode).

In production, always set a strong random token:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Monitoring Checklist

### Daily
- [ ] Check total sessions and new student registrations
- [ ] Review cache hit rates (should be > 50% for homework cache)
- [ ] Check for any error patterns in AI evaluation scores

### Weekly
- [ ] Review subscription revenue trends
- [ ] Analyse score distribution for quality issues
- [ ] Check Langfuse traces for any LLM quality problems
- [ ] Review daily activity patterns for capacity planning

### Monthly
- [ ] Clear caches if memory usage is high
- [ ] Review and delete inactive student accounts (GDPR data minimisation)
- [ ] Update prompt templates based on quality feedback
- [ ] Review embedding model performance
