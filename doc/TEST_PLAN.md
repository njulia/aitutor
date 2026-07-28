# Test plan

Release priority follows learner impact.

| Area | Main risk | Required evidence |
|---|---|---|
| RAG assignment | Paid generation before library lookup or repeated sets | RAG-first and concurrency unit tests |
| Marking | Answers or saved methods leak to pupils/prompts | Review, question-renderer and method-reuse tests |
| Guided setup | Unbounded fields or identifiers are retained | Guided profile and API contract tests |
| Subscription | Expensive premium work runs before entitlement | Plan-access and generation API tests |
| Accounts | Cross-account learner access | API and family-journey tests |
| Safety/privacy | Child identifiers or crisis content are mishandled | Minimisation and safeguarding tests |
| SEO | Duplicate URLs or missing canonical discovery files | Public SEO contract tests |
| Deployment | Runtime mismatch or unsafe production settings | Compile, readiness and configuration tests |

A release requires successful unit, API, integration and browser suites. Any
change to prompt inputs must include a regression assertion showing that direct
identifiers and locally saved solution methods are absent.
