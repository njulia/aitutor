# Stripe live setup for Homework Magic

The changed files use the live Stripe Pricing Table supplied for Homework Magic. Checkout is available only to a signed-in parent or guardian. Access is updated only from a signature-verified Stripe webhook.

## 1. Copy the files into the project

Keep these paths exactly:

```text
web_app.py
src/webapp/stripe_pricing_billing.py
static/pricing.html
test/unit/test_stripe_pricing_billing.py
```

No change is required in `homework_rag.py` or `static/app.html` for billing.

## 2. Check the three products before launch

Open the live Pricing Table in Stripe and confirm each product's amount, currency and renewal interval match the public `/pricing` page.

Important: Stripe's embeddable Pricing Table is for subscriptions. If the £0.99 five-day product is meant to be a **one-time payment that never renews**, do not launch it as a recurring five-day subscription. The supplied backend deliberately ignores non-subscription Checkout Sessions. A one-time five-day pass needs a separate one-time Checkout/Payment Link integration and a five-day entitlement.

## 3. Configure the Pricing Table confirmation page

In Stripe Dashboard, edit the live Pricing Table and set its post-purchase redirect to:

```text
https://homeworkmagic.co.uk/pricing?checkout=success&session_id={CHECKOUT_SESSION_ID}
```

The page waits briefly for the verified webhook and then confirms that access is ready.

## 4. Create the webhook destination

In Stripe Workbench, create an event destination using:

```text
https://homeworkmagic.co.uk/api/billing/stripe/webhook
```

Subscribe to these account events:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

Reveal the endpoint signing secret, which starts with `whsec_`. This is different from the webhook secret printed by Stripe CLI.

References: [Stripe Pricing Table fulfilment](https://docs.stripe.com/payments/checkout/pricing-table#handle-fulfillment-with-the-stripe-api) and [webhook signature verification](https://docs.stripe.com/webhooks/signature).

## 5. Activate and brand the customer portal

In Stripe Dashboard, activate the customer portal and review its branding. The
application creates or reuses its own portal configuration so signed-in parents
can:

- update payment methods;
- view invoices;
- cancel subscriptions;
- change between the configured monthly plans.

The Stripe secret or restricted key must be allowed to read and create Billing
Portal configurations and sessions. If you manage a configuration yourself,
set its `bpc_...` ID as `STRIPE_PORTAL_CONFIGURATION_ID`; it must enable both
subscription cancellation and price changes for the configured monthly products.

Also enable Stripe's option to limit a Customer to one active subscription. Existing subscribers are sent to the portal instead of being offered a duplicate checkout.

## 6. Store the two private Stripe values in Secret Manager

Never put either private value in source code or `.env` files committed to Git.

```bash
export PROJECT_ID="your-gcp-project-id"
export SERVICE="your-cloud-run-service"
export REGION="europe-west2"

gcloud secrets create homeworkmagic-stripe-secret-key \
  --project="$PROJECT_ID" \
  --replication-policy="automatic"

gcloud secrets create homeworkmagic-stripe-webhook-secret \
  --project="$PROJECT_ID" \
  --replication-policy="automatic"

printf '%s' 'sk_live_REPLACE_ME' | gcloud secrets versions add homeworkmagic-stripe-secret-key \
  --project="$PROJECT_ID" \
  --data-file=-

printf '%s' 'whsec_REPLACE_ME' | gcloud secrets versions add homeworkmagic-stripe-webhook-secret \
  --project="$PROJECT_ID" \
  --data-file=-
```

If either secret already exists, skip its `gcloud secrets create` command and add a new version only.

Grant the Cloud Run runtime service account Secret Manager Secret Accessor access to both secrets.

## 7. Update Cloud Run configuration

```bash
gcloud run services update "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --update-env-vars="APP_BASE_URL=https://homeworkmagic.co.uk,CORS_ORIGINS=https://homeworkmagic.co.uk,STRIPE_PRICING_TABLE_ID=prctbl_1TvlP9A7C4P8kXJMSS8t4VRT,STRIPE_PUBLISHABLE_KEY=pk_live_fYeIDSqsqYC6MDKau5eFsI0U" \
  --update-secrets="STRIPE_SECRET_KEY=homeworkmagic-stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=homeworkmagic-stripe-webhook-secret:latest"
```

The publishable key and Pricing Table ID are public identifiers; the secret key and webhook signing secret are private.

The application creates `stripe_billing_accounts` and `stripe_billing_subscriptions` in `DATABASE_URL` on first use. The production database user therefore needs permission to create these two tables.

## 8. Plan labels and switching

Copy the live Price IDs from Stripe and set the relevant variables. The two
monthly IDs are required for plan switching and plan-specific access checks:

```text
STRIPE_PRICE_TRIAL_5DAY=price_...
STRIPE_PRICE_HOMEWORK_MONTHLY=price_...
STRIPE_PRICE_ELEVENPLUS_MONTHLY=price_...
```

The app verifies plan changes from Stripe webhooks before updating local access.

## 9. Verify after deployment

1. Open `/pricing` while signed out: the public plan summary should appear, but checkout should require parent sign-in.
2. Sign in as a parent: the live Stripe Pricing Table should replace the summary.
3. Complete a test-mode purchase using a separate test Pricing Table and test keys first.
4. Confirm the webhook destination reports successful `2xx` deliveries.
5. Confirm `/api/check-subscription` changes to `has_subscription: true` after the webhook.
6. Cancel in the customer portal and confirm access remains until the paid period ends, then becomes inactive.
7. Verify no learner name, answer, school information or learning-memory content appears in Stripe metadata.
