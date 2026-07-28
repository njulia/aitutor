# Privacy and safety testing

The service is designed for parent-managed UK primary learners.

Required checks:

- Emails, labelled phone numbers, postcodes, URLs, explicit names and school
  disclosures are removed before prompt construction.
- Guided client responses omit learner IDs, notes and weak-area text.
- Parent notes are not written to local browser preferences.
- Learner-facing homework never contains answer, explanation or tip sections.
- Retrieved solution methods are rendered locally and are not sent back to an
  LLM on later attempts.
- Raw learner and model text storage remains disabled by default.
- Explicit first-person safeguarding concerns stop normal tutoring and return
  the approved child-friendly intervention.
- Story, history and curriculum text does not trigger a false intervention.
- Account, message, memory and progress responses are private and `no-store`.

Use synthetic examples only. Never place a real child's name, account, school,
answer history or contact details in fixtures, screenshots, traces or issue
reports.
