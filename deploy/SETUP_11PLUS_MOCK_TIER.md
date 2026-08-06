# Configure billing for 11+ mock exams

The timed mock catalogue is included in the existing **11+ Premium** plan.
Do not create a separate mock-exam product or price.

- Price: **£9.99 GBP**
- Billing period: **monthly**
- Environment variable: `STRIPE_PRICE_ELEVENPLUS_MONTHLY`
- Entitlement name: `elevenplus_monthly`
- Included: guided 11+ practice and all paid common/school-target mocks
- Free without a plan: the short common diagnostic
- The one-off five-day pass does not unlock paid mock exams

## Stripe setup

In Stripe Product catalogue, confirm that the `11+ Premium` product has one
recurring £9.99 monthly Price. Copy its `price_...` identifier into the private
Cloud Run environment configuration as `STRIPE_PRICE_ELEVENPLUS_MONTHLY`.
Never put a Stripe secret key or webhook secret in this repository.

The other advertised prices remain:

- `STRIPE_PRICE_TRIAL_5DAY`: £0.99 one-off
- `STRIPE_PRICE_HOMEWORK_MONTHLY`: £4.99 monthly
- `STRIPE_PRICE_ELEVENPLUS_MONTHLY`: £9.99 monthly

## Verify checkout and access

1. Use Stripe test mode outside production.
2. Sign in with a parent test account and open `/pricing`.
3. Choose **11+ Premium** and complete Checkout with a test card.
4. Confirm the signed webhook activates `elevenplus_monthly`.
5. Open `/elevenplus-mock-exams` as the parent and as one of their kids.
6. Confirm the paid mocks show as included and can be started and submitted.
7. Confirm subject results and topic recommendations appear after submission.

The webhook endpoint is:

```text
https://homeworkmagic.co.uk/api/billing/stripe/webhook
```
