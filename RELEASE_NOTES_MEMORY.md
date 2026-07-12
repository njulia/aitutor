# Release notes: PostgreSQL and learning memory

## Added

- Structured per-learner memory with parent opt-in
- Topic mastery, recent events and controlled misconception codes
- Parent memory page with export, retention and erasure controls
- PostgreSQL-backed accounts, sessions, progress, messages, billing and memory
- Stripe Checkout, customer portal and verified webhook materialisation
- Complete learner/account local-data erasure orchestration
- Same-origin write protection and no-store privacy headers
- Local Markdown and chart rendering without public learner-page CDNs
- Docker and PostgreSQL deployment files

## Changed

- Billing now belongs to the parent account rather than a learner
- Production manual subscriptions are disabled
- Production requires PostgreSQL
- Login cookies contain opaque revocable tokens
- Progress percentages use `score / max_score`, not an assumed score out of ten
- RAG question indexes and 11+ metadata are preserved in tutor-mode review

## Defaults

- Learning memory: off
- Raw learner work storage: off
- Raw AI prompt/response storage: off
- Login session lifetime: 12 hours
- Tutor session lifetime: 12 hours
