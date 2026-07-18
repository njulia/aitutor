# UK Child Safety, Privacy and DPIA Launch Checklist

**Service:** Homework Magic AI Tutor  
**Audience:** UK pupils aged 5–11, operated through a parent or guardian account  
**Status:** Complete and sign before public launch

This checklist supports engineering and governance work. It is not legal advice or a compliance certificate.

## A. Ownership and accountability

- [ ] Legal data controller name is confirmed.
- [ ] Privacy contact email and postal address are published.
- [ ] A named owner is responsible for child privacy.
- [ ] A named owner is responsible for safeguarding.
- [ ] Incident escalation contacts are documented and tested.
- [ ] Records of processing activities are current.
- [ ] All suppliers and sub-processors are listed.

## B. DPIA and best interests

- [ ] A DPIA was started before live processing.
- [ ] All learner, parent, payment, support, upload and AI data flows are mapped.
- [ ] Risks are assessed separately for ages 5–7, 7–9 and 9–11.
- [ ] The best interests of the child are the primary design consideration.
- [ ] Children and parents were consulted in an age-appropriate way.
- [ ] Necessity and proportionality are recorded for every data field.
- [ ] Residual high risks were escalated to the ICO where required.
- [ ] The DPIA has a review date and change trigger.

## C. Lawful basis and parental role

- [ ] A lawful basis is recorded for every processing purpose.
- [ ] Consent is not used where it is not genuinely optional.
- [ ] Where consent is relied upon for an under-13 ISS user, reasonable parental-responsibility verification is implemented.
- [ ] The parent/guardian controls account creation, payments and learner deletion.
- [ ] Children cannot bypass the parent account through browser-stored identifiers.
- [ ] Withdrawal of consent is as easy as giving it, where consent is used.

## D. Data minimisation and retention

- [ ] Full child name, school, address, phone, email and exact birthday are not required for tutoring.
- [ ] Learner text is minimised before being sent to an AI provider.
- [ ] Raw learner and raw AI content are disabled by default.
- [ ] Logs exclude passwords, tokens, uploads, homework text and model prompts.
- [ ] Retention periods are documented and automatically enforced.
- [ ] Password-reset tokens are short-lived, single-use and stored as hashes.
- [ ] Support messages have a justified retention period.
- [ ] Backups follow the same deletion and retention policy.

## E. Child-facing design

- [ ] Language is clear for pupils aged 5–11.
- [ ] The child privacy summary is easy to find and understand.
- [ ] The interface avoids pressure, streak anxiety, shaming and manipulative rewards.
- [ ] No behavioural advertising or personalised marketing is shown to children.
- [ ] No purchase prompts are shown in learning output.
- [ ] Explanations use short steps and supportive wording.
- [ ] The system makes clear that AI can make mistakes.
- [ ] Important decisions can be reviewed by a parent, teacher or human support person.

## F. Safeguarding

- [ ] Explicit personal danger disclosures stop normal tutoring.
- [ ] The response tells the child to speak to a trusted adult.
- [ ] Immediate danger guidance says to call 999.
- [ ] Childline 0800 1111 is displayed correctly.
- [ ] Safety detection is tested for false positives in stories and schoolwork.
- [ ] Staff handling support messages receive safeguarding training.
- [ ] A written process covers abuse disclosures, imminent danger and illegal content.
- [ ] Emergency and safeguarding messages are not treated as ordinary customer support.

## G. AI governance

- [ ] AI provider terms allow the intended child-related use.
- [ ] Provider training on submitted data is disabled contractually and technically where available.
- [ ] Data regions and international transfers are documented.
- [ ] Prompts treat learner text as untrusted data.
- [ ] Prompt-injection and data-exfiltration tests are run.
- [ ] Model output is filtered for age appropriateness and unsafe requests.
- [ ] Token and timeout budgets are set.
- [ ] A fallback message is shown when the AI is unavailable.
- [ ] Quality is evaluated by year group and subject, not only overall.

## H. Security and reliability

- [ ] Production secrets are held in a secret manager.
- [ ] Previously exposed keys are revoked and replaced.
- [ ] HTTPS and secure cookies are enforced.
- [ ] CORS contains only real origins.
- [ ] Admin endpoints reject ordinary and anonymous users.
- [ ] Passwords are hashed with a modern, reviewed scheme.
- [ ] Sensitive routes are rate limited across all instances.
- [ ] PostgreSQL backups and restore tests are current.
- [ ] File type, size, page and pixel limits are enforced.
- [ ] Malware scanning is considered before retaining uploaded files.
- [ ] Availability, latency, 5xx rate and database capacity are monitored.
- [ ] A rollback procedure has been tested.

## I. Payments and commercial design

- [ ] Only the parent/guardian can purchase or manage a subscription.
- [ ] Stripe webhook signatures are verified.
- [ ] Access is revoked on cancellation or failed payment according to the published terms.
- [ ] Prices, renewals, cancellation and refunds are clear before purchase.
- [ ] The child experience has no dark patterns or urgency pressure.
- [ ] Marketing consent is separate from service operation.

## J. Rights and support

- [ ] Parent and child access requests can be handled securely.
- [ ] Correction, deletion, restriction and objection workflows are documented.
- [ ] Account deletion removes account-owned learner records and linked content.
- [ ] The privacy notice explains how to complain to the ICO.
- [ ] Accessibility testing covers keyboard, screen reader, zoom, contrast and readable language.
- [ ] Support response times and emergency limitations are clearly stated.

## Sign-off

| Role | Name | Date | Decision / conditions |
|---|---|---|---|
| Product owner |  |  |  |
| Data protection lead |  |  |  |
| Safeguarding lead |  |  |  |
| Security reviewer |  |  |  |
| Legal reviewer |  |  |  |
