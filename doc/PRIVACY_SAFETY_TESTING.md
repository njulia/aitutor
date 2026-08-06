# Privacy and safety testing

Homework Magic is parent-managed and designed for children, so privacy and access-control checks are release-critical.

## Identity and ownership

- Verify parent and child sessions are mutually exclusive when switching roles.
- Verify a child can access only their own profile, progress, rewards, certificates and mock attempts.
- Verify a parent can access only children belonging to their account.
- Verify login, password reset and child-code endpoints are rate limited and return non-revealing errors.

## Data handling

- Use learner nicknames and never require a school, exact birthday, home address or phone number for learning.
- Confirm account and learner APIs are `no-store` and private pages are excluded by robots rules.
- Confirm learner data is not included in Stripe metadata or browser analytics.
- Confirm reward delivery details are parent-only, encrypted at rest and absent from learner responses.
- Confirm test fixtures contain no production personal data or credentials.

## Content and browser safety

- Exercise prompt-injection, abusive-content and oversized-input cases.
- Render provider text with safe DOM APIs; never insert untrusted feedback as HTML.
- Verify external scripts are absent from learner and account pages unless explicitly reviewed.
- Verify microphone access is limited to the learning origin and speech controls can always stop playback.

Record discovered privacy or safeguarding issues as security defects and block release until the risk is resolved or formally accepted by the responsible owner.
