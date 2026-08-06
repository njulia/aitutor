# Test plan

## Objectives

The test suite protects learner isolation, parent controls, educational correctness, reliable feedback, subscription access, privacy and fast public pages.

## Layers

| Layer | Purpose | Release gate |
|---|---|---|
| Unit | Pure rules, stores, token validation, rendering contracts and configuration | All pass |
| API | Authentication, ownership, rate limits, billing, mocks, progress and rewards | All pass |
| Integration | Database and provider boundaries with fakes | All pass |
| Browser | Critical parent and child journeys | Required before production promotion |
| Manual | Audible speech, responsive layout and Stripe test checkout | Required for affected releases |

## High-risk regression areas

- A child must never select or read a sibling's progress, rewards or mock attempt.
- Parent-only routes must reject child sessions, including browsers containing both legacy cookies.
- Reward XP must be idempotent; Gift Points and redemptions must respect plan and parent approval rules.
- Mock attempt tokens must be owner-bound, canonical, signed, time-limited and single-purpose.
- Billing access changes only after verified provider events.
- Public legal details must be visible and configured before production starts.
- Learner-facing pages must not load unnecessary third-party scripts.

Add a regression test with every defect fix. Prefer deterministic fixtures and bounded inputs.
