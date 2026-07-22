# Privacy and safety testing for children under 12

Homework Magic is parent-managed and designed for UK primary learners. Testing must follow data minimisation and use fictional identities and homework.

## Automated checks

- Parent ownership is required for learner, progress, memory and billing records.
- Learner profiles reject or minimise unnecessary identifying details.
- Raw learner and AI content storage remains off by default.
- Password-reset tokens are short-lived, single-use and stored safely.
- Support messages cannot be read by another parent or anonymous session.
- Child profiles, answers and progress are not sent in payment metadata.
- Model prompts and rendered model output preserve safety boundaries.
- Explicit safeguarding concerns return trusted-adult, emergency and Childline guidance.
- Public privacy text identifies the controller, purposes, lawful bases, processors, retention, rights and contact routes.

## Manual review

- Use age-appropriate words and short instructions in learner journeys.
- Keep purchase prompts and payment details in parent/guardian areas.
- Never ask a child for a full name, school, address, phone number, exact date of birth or password.
- Confirm optional learning memory can be reviewed and controlled by the parent.
- Check that deletion and privacy-request routes are understandable and reachable.
- Review third-party AI, email, hosting, monitoring and payment configurations before introducing a new processor or transfer location.

Any test artefact containing real child or parent data must be stopped, reported and handled under the incident process; it must not be copied into bug trackers, screenshots or model prompts.
