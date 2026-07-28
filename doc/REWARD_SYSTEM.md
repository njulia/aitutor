# Reward Quest System

The reward system is designed for children aged 5–11 and their parents or
guardians. It rewards steady effort rather than high marks.

## Learning loop

1. A signed-in learner finishes an activity and checks their work.
2. The server awards permanent XP and matching Gift Points once for that
   activity on that day.
3. Daily and weekly quest bonuses are claimed automatically.
4. Lifetime XP unlocks levels and printable certificates.
5. Gift Points may be exchanged for a Homework Magic branded gift.
6. A parent approves or declines the request using the parent account password.
7. Approval requires an adult recipient's UK delivery address.
8. An administrator posts the parcel and marks the order as dispatched.

XP is never deducted. A gift approval spends only Gift Points, so a learner's
XP total, level and certificates do not go backwards. Repeated submissions of
the same checked work do not award more points. Only the first three checked
activities each day receive activity points. Quest bonuses are also one-time
and enforced with database uniqueness constraints.

## Default XP rules

| Action | Permanent XP | Gift Points |
| --- | ---: | ---: |
| Complete and check a homework activity | 20 | 20 |
| Complete and check a tutor question | 10 | 10 |
| First checked activity today | +10 | +10 |
| Second checked activity today | +15 | +15 |
| Third checked activity today | +20 | +20 |
| Learn on 3 days this week | +30 | +30 |
| Learn on 5 days this week | +50 | +50 |
| Explore 3 subjects this week | +25 | +25 |

The activity values and cap can be adjusted with
`REWARD_HOMEWORK_ACTIVITY_XP`, `REWARD_TUTOR_ACTIVITY_XP` and
`REWARD_DAILY_ACTIVITY_CAP`. Quest bonuses remain fixed so every family sees
the same clear rules.

## Certificates and levels

Certificates unlock at 100, 250, 500, 1,000 and 2,000 lifetime XP. A parent can
print or save an unlocked certificate from the browser.

- `lifetime_xp` only records earned progress and never decreases.
- `gift_points` is the public balance used for gifts.
- The legacy database column named `spendable_xp` holds Gift Points so existing
  deployments can upgrade without an unsafe table rewrite.

## Homework Magic gift shop

| Branded gift | Gift Points |
| --- | ---: |
| Homework Magic sticker pack | 100 |
| Homework Magic pen | 250 |
| Homework Magic notebook | 500 |

A child's request remains pending and uses no points. The parent must enter the
account password and an adult recipient's UK address to approve it. Approval
uses Gift Points but leaves XP unchanged. An approved order can be cancelled
before dispatch, which returns the Gift Points. The protected administrator
queue is available at `/admin/reward-orders`.

## Safety, privacy and reliability

- Parent approval requires the current account password. The reward store never
  saves that password.
- The delivery recipient must be an adult. No child's name, phone number, email
  address or school is needed for delivery.
- Delivery addresses are validated as UK addresses, encrypted with
  `REWARD_DELIVERY_SECRET`, and never included in learner-facing dashboard
  responses, logs, traces or analytics.
- Only the protected administrator order detail endpoint decrypts an address.
  Marking an order as dispatched schedules the encrypted address for deletion
  after 30 days. Cancelling, learner deletion or account deletion removes it
  immediately.
- The system stores pseudonymous account and learner IDs, fixed event labels,
  point amounts, certificate codes, gift orders and fulfilment decisions.
- It does not store homework text, answers or marks in reward records.
- Reward writes use one shared SQLAlchemy connection pool, row locking and
  unique source keys to remain safe across concurrent Cloud Run workers.
- Reward failures are isolated: a successful homework review still reaches the
  child if XP persistence is temporarily unavailable.
- Learner or account deletion removes wallets, XP history, certificates,
  gift orders, encrypted delivery addresses and legacy catalogue items.

Production must provide a stable secret containing at least 32 random
characters:

```text
REWARD_DELIVERY_SECRET=<secret-manager value>
```

The default quest day uses `Europe/London`. Set `REWARD_TIMEZONE` to another
IANA timezone only if the service's primary family timezone changes.
