# Privacy and safeguarding testing

This document describes engineering checks. It is not a legal opinion or a substitute for a child-focused DPIA and professional safeguarding review.

## Privacy contracts covered by automated tests

- Parent or guardian email is used for account ownership.
- Learner profiles accept nicknames and reject obvious contact or school information.
- Session cookies are HttpOnly and do not contain the email address.
- Learner IDs are pseudonymous and are not derived from IP addresses.
- One account cannot access another account's learners, memory or progress.
- Learning memory is off by default.
- Raw questions and answers are removed from structured memory metadata.
- Memory exports do not include the parent email.
- Admin pages and APIs are allowlist protected.
- Public pages do not load learner JavaScript from third-party CDNs.
- Browser storage checks reject obvious email, school and address fields.

## Safeguarding contracts covered by automated tests

- Explicit first-person danger disclosures interrupt normal tutoring.
- Safety guidance uses simple language suitable for ages 5–11.
- The safety page tells the child to contact a trusted adult.
- Immediate-danger guidance includes 999.
- Childline guidance includes 0800 1111.
- Ordinary maths and homework text is not incorrectly blocked.

## Manual safeguarding tests

Use fictional content only. Do not enter real child disclosures into staging systems.

Check that:

- the intervention is calm and does not interrogate the child;
- it does not promise secrecy;
- it tells the child to seek a trusted adult;
- it distinguishes immediate danger from general worry;
- normal tutoring stops during an urgent intervention; and
- logs do not retain the disclosure text when raw storage is disabled.

## Test-data rules

- Use invented learner nicknames.
- Use `example.com` email addresses.
- Never use a real school, address, phone number or date of birth.
- Never copy a real child's homework, medical information or disclosure into tests.
- Keep screenshots and Playwright traces private because they can contain form data.
