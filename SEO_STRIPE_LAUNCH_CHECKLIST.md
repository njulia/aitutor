# Homework Magic SEO and Stripe launch checklist

This build uses **`https://homeworkmagic.co.uk` as the single canonical origin**. Deploy the code first, then complete the external steps below. Code changes cannot guarantee Google ranking or complete Stripe identity verification by themselves.

## 1. Set truthful public business details
* 
* Create a production environment YAML file that is not committed to Git:

```yaml
APP_BASE_URL: "https://homeworkmagic.co.uk"
PUBLIC_BASE_URL: "https://homeworkmagic.co.uk"
CORS_ORIGINS: "https://homeworkmagic.co.uk"
CANONICAL_REDIRECT_HOSTS: "www.homeworkmagic.co.uk"

DATA_CONTROLLER_NAME: "Your legal sole-trader name or registered company name"
PRIVACY_CONTACT_EMAIL: "contact@homeworkmagic.co.uk"
BUSINESS_CONTACT_EMAIL: "contact@homeworkmagic.co.uk"
PRIVACY_POSTAL_ADDRESS: "Your legitimate UK business/service address"

# Optional public details; include only when accurate.
BUSINESS_SUPPORT_PHONE: "Your business support number"
BUSINESS_REGISTRATION_NUMBER: "Your Companies House number"
BUSINESS_VAT_STATUS: "Not VAT registered"
```

Then update Cloud Run using your normal project, service and region values:

```bash
gcloud run services update "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --env-vars-file=production-public-env.yaml
```

Important:

- Do not publish a fake name or address.
- A sole trader trading as Homework Magic normally needs to identify the legal proprietor and provide an address where legal documents can be served. A legitimate business-address service can keep a home address off the website.
- A limited company can publish its company name, number and registered office/service address instead of a director's home address.
- Stripe still needs the owner's real residential and identity details privately for KYC.
- If the business is not VAT registered, use the truthful status **Not VAT registered**. Do not invent a VAT number.

The public identity is now rendered visibly on Pricing, Terms, Privacy and Refund pages. Production startup also rejects missing required identity/contact fields.

## 2. Make one domain version authoritative

In the domain and Cloud Run configuration:

1. Keep `homeworkmagic.co.uk` mapped to the Cloud Run service.
2. Also map `www.homeworkmagic.co.uk` so requests can reach the redirect middleware.
3. Confirm both hosts have valid HTTPS certificates.
4. Confirm every `www` request receives a permanent `308` redirect to the same path on the non-`www` host.

Check after deployment:

```bash
curl -I https://homeworkmagic.co.uk/
curl -I https://www.homeworkmagic.co.uk/
curl -s https://homeworkmagic.co.uk/robots.txt
curl -s https://homeworkmagic.co.uk/sitemap.xml
```

Expected results:

- The first URL returns `200`.
- The `www` URL redirects to `https://homeworkmagic.co.uk/`.
- `robots.txt`, the sitemap, page canonical tags and internal article links all use the non-`www` origin.

Google treats redirects, canonical tags and sitemap URLs as reinforcing canonical signals. See [Google's canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls).

## 3. Submit the site to Google

1. Open [Google Search Console](https://search.google.com/search-console/).
2. Add a **Domain property** for `homeworkmagic.co.uk`.
3. Add Google's TXT verification record in the DNS manager where the domain is hosted.
4. After verification, open **Sitemaps** and submit `https://homeworkmagic.co.uk/sitemap.xml`.
5. Open **URL inspection**, inspect `https://homeworkmagic.co.uk/`, run the live test, then select **Request indexing**.
6. Repeat URL inspection for `/ks1-homework`, `/ks2-homework`, `/elevenplus-practice` and `/pricing`.
7. In the Page indexing report, check for crawl errors or a Google-selected canonical different from the declared canonical.

A new or recently changed site can take days or weeks to appear. A `site:` query is useful for a quick check but is not a complete indexing report; Search Console is authoritative.

## 4. Complete Stripe's business settings

In the live Stripe account:

1. Choose the correct legal structure: **Individual / sole trader** unless a limited company has actually been incorporated.
2. Complete the owner/representative's real name, date of birth, residential address and requested identity evidence privately.
3. Use **Homework Magic** as the customer-facing trading name.
4. Set the business website to `https://homeworkmagic.co.uk`.
5. Use this product description:

   > Subscription-based online educational practice for parents and guardians of UK primary pupils aged 5–11. The digital service provides Years 1–6 homework practice, feedback and 11+ preparation. No physical goods are supplied.

6. In public business details, configure:
   - support email: `contact@homeworkmagic.co.uk`;
   - support URL: `https://homeworkmagic.co.uk/messages`;
   - terms: `https://homeworkmagic.co.uk/terms`;
   - privacy: `https://homeworkmagic.co.uk/privacy`;
   - refund policy: `https://homeworkmagic.co.uk/refund-policy`;
   - a legitimate customer-facing support address and business phone number;
   - statement descriptor: `HOMEWORKMAGIC` (or Stripe's closest permitted form).
7. If true, select **not VAT registered**. VAT registration is separate from Stripe identity verification.
8. Open every page above in a private/incognito window and confirm it loads without a password and shows no placeholder text.

Stripe says its KYC process requires information about the business, product and the user's relationship to it. Its public business settings also include the business name/site, support email, phone/address and statement descriptor. See [Stripe account setup](https://docs.stripe.com/get-started/account/set-up) and the [Stripe website activation FAQ](https://support.stripe.com/questions/business-website-for-account-activation-faq).

## 5. Verify live Stripe billing before launch

Keep all live billing values from the same Stripe account:

```dotenv
STRIPE_BILLING_ENABLED=true
STRIPE_EXPECTED_LIVEMODE=true
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_TRIAL_5DAY=price_...
STRIPE_PRICE_HOMEWORK_MONTHLY=price_...
STRIPE_PRICE_ELEVENPLUS_MONTHLY=price_...
```

Configure the live webhook endpoint:

```text
https://homeworkmagic.co.uk/api/billing/stripe/webhook
```

Subscribe it to the events listed in `README.md`, enable the Stripe customer portal, and make one low-value live purchase using a parent test account. Confirm:

- Checkout requires agreement to the Terms of Service.
- The five-day purchase does not renew.
- Monthly checkout clearly says it renews until cancelled.
- A signed webhook, not the browser redirect, grants access.
- The confirmation email arrives.
- Cancellation works in the billing portal.
- Changing between Homework Premium and 11+ Premium works, and the signed
  `customer.subscription.updated` webhook changes access to the selected plan.
- The bank statement description is recognisable as Homework Magic.

## 6. Final public review

Before requesting another Stripe review, check these pages:

- [Homepage](https://homeworkmagic.co.uk/)
- [Pricing and digital delivery](https://homeworkmagic.co.uk/pricing)
- [Contact and support](https://homeworkmagic.co.uk/messages)
- [Terms](https://homeworkmagic.co.uk/terms)
- [Privacy](https://homeworkmagic.co.uk/privacy)
- [Refunds and cancellation](https://homeworkmagic.co.uk/refund-policy)

The website and the Stripe Dashboard must tell the same truthful story: the same trading name, service, prices, billing periods, contact details and legal operator.

This checklist is practical implementation guidance, not legal or tax advice. Obtain professional advice if the trading structure, public-disclosure obligations or VAT position is uncertain.
