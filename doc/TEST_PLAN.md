# Risk-based test plan

## Release gates

A release is ready only when:

- Python compilation succeeds;
- unit, API and integration suites pass;
- affected browser journeys pass;
- no high-severity security, privacy, billing or child-safety defect remains open;
- public prices, product descriptions and policy pages match the configured payment products;
- database and webhook migrations have a rollback or forward-fix plan.

## Priority areas

| Priority | Area | Main evidence |
|---|---|---|
| Critical | Parent authentication and account ownership | API and browser tests |
| Critical | Payment webhook verification and entitlements | Billing unit/API tests |
| Critical | Child privacy, content minimisation and safeguarding | Privacy/safety tests |
| High | Homework generation, review and model routing | Contract and routing tests |
| High | Progress, memory and retention | Store/API tests |
| High | Public SEO, legal identity and refund disclosures | Public-site contract tests |
| Medium | Accessibility and responsive presentation | Browser tests and manual review |
| Medium | Performance under concurrent AI requests | Timeouts, bulkhead tests and staging load checks |

## Regression selection

Changes to shared middleware, accounts, databases, billing, prompts or learner rendering require the full non-browser suite. HTML-only public-site changes require the focused SEO/legal tests plus browser smoke checks. Payment changes require test-mode Checkout, portal and signed webhook verification before any controlled live test.
