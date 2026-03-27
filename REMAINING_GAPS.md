# SipSense — Remaining Gap Items

> Updated 2026-03-27.

---

## GAP 1: Purchase Flow — MOSTLY DONE

**Done:**
- Buy CTAs on whiskey detail, chat cards, next-bottle widget (PR #33)
- Affiliate click tracking with source attribution (PR #33)
- Price verdict badge + budget alternatives on buy section (this PR)
- Price drop alert toggle on whiskey detail (this PR)
- Post-purchase follow-up banner ("Did you buy it? Rate it!") on Browse (this PR)

**Still Missing:**
- [ ] Sign up for affiliate programs (Drizly, ReserveBar, Total Wine, Amazon Associates, Caskers, Flaviar) — **not a code task**
- [ ] Multi-retailer price comparison (requires real affiliate data per retailer)

---

## GAP 2: Stripe / Payment Integration — DONE (this PR)

- [x] Stripe Checkout session endpoint (`/billing/create-checkout-session`)
- [x] Stripe webhook handler (`/billing/webhook`) — checkout.session.completed, subscription.updated, subscription.deleted
- [x] Stripe Customer Portal for self-serve management
- [x] Idempotent webhook processing via `stripe_events` table
- [x] 7-day free trial on first subscription
- [x] Monthly ($4.99) and yearly ($39.99) plan toggle on Premium page
- [x] Premium page connected to Stripe — redirects to Stripe Checkout
- [x] Manage Subscription button for active Stripe subscribers

**Setup needed (not code):**
- [ ] Create Stripe account + products/prices
- [ ] Set env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`
- [ ] Configure Stripe webhook endpoint: `https://sipsense.ai/api/billing/webhook`

---

## GAP 3: Taste Identity (Partially Done)

**Done:**
- Shareable "Whiskey DNA" card on Profile (PR #33)

**Still Missing:**
- [ ] Palate evolution timeline (monthly snapshots, "your taste 3 months ago vs now")
- [ ] Taste percentile rankings ("top 5% of bourbon enthusiasts", "tried more than 73% of users")
- [ ] Personalized post-check-in insights ("this is your 4th peated scotch", "you rate Japanese 0.8 stars above avg")

---

## GAP 4: Low-Frequency Usage / Engagement (Not Started)

- [ ] Streak system ("Learn every day" — open app, read a fact, do a quiz)
- [ ] Daily content that doesn't require drinking (whiskey of the day facts, blind taste quiz)
- [ ] Community challenges ("March Bourbon Madness: Rate 4 bourbons this month")
- [ ] Weekly digest (requires email — see GAP 5)

---

## GAP 5: Email System (Not Started)

- [ ] Set up transactional email (AWS SES — already on AWS)
- [ ] Welcome email after signup
- [ ] Password reset flow (currently no forgot-password)
- [ ] Weekly activity digest
- [ ] Re-engagement emails ("You haven't checked in for 2 weeks")
- [ ] Onboarding drip sequence (Day 1, 3, 7, 14)

---

## GAP 6: SEO / Public Pages — DONE (PR #34)

## GAP 7: "Next Bottle" as Core Feature — DONE (PR #33)
