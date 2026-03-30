# SipSense — Remaining Gap Items

> Updated 2026-03-29.

---

## GAP 1: Purchase Flow — MOSTLY DONE

**Done:**
- Buy CTAs on whiskey detail, chat cards, next-bottle widget (PR #33)
- Affiliate click tracking with source attribution (PR #33)
- Price verdict badge + budget alternatives on buy section
- Price drop alert toggle on whiskey detail
- Post-purchase follow-up banner ("Did you buy it? Rate it!") on Browse

**Still Missing:**
- [ ] Sign up for affiliate programs (Drizly, ReserveBar, Total Wine, Amazon Associates, Caskers, Flaviar) — **not a code task**
- [ ] Multi-retailer price comparison (requires real affiliate data per retailer)

---

## GAP 2: Stripe / Payment Integration — DONE

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

## GAP 3: Taste Identity — DONE

- [x] Shareable "Whiskey DNA" card on Profile (PR #33)
- [x] Palate evolution timeline — monthly snapshots with category distribution, narrative comparison vs 3 months ago (`/taste-identity/evolution`)
- [x] Taste percentile rankings — total rated percentile, top category percentile, diversity score (`/taste-identity/percentiles`)
- [x] Post-check-in insights — category count, category avg comparison, personal favorites, region tracking, flavor pattern detection, serving style patterns, score trends, exploration milestones (`checkin_insights.py`)

---

## GAP 4: Low-Frequency Usage / Engagement — DONE

- [x] Streak system — daily heartbeat, current/longest streak tracking, integrated with quiz and check-ins (`/streaks`)
- [x] Daily content — Daily Discovery featured bottle with facts and tasting tips (`/daily`)
- [x] Daily knowledge quiz — blind tasting quiz with 4 options, streak integration (`/taste-identity/quiz-question`)
- [x] Community challenges — monthly goals with progress tracking and top-10 leaderboard (`/challenges`)

---

## GAP 5: Email System — DONE

- [x] AWS SES integration with graceful degradation (`email_service.py`)
- [x] HTML email templates: welcome, password reset, weekly digest, re-engagement, onboarding drip (`email_templates.py`)
- [x] Email preference management with per-type opt-in/out and one-click unsubscribe (`/email-preferences`)
- [x] Email audit logging via `EmailLog` table
- [x] Welcome email after signup
- [x] Password reset flow with secure token + 1-hour expiry (`/auth/forgot-password`, `/auth/reset-password`)
- [x] Scheduled jobs via APScheduler (`scheduler.py` + `scheduled_jobs.py`):
  - Weekly digest (Sunday 10am UTC)
  - Re-engagement emails (daily, targets 14+ day inactive users, 30-day cooldown)
  - Onboarding drip (days 1, 3, 7, 14 after registration)
  - Streak push reminders (daily 8pm UTC)
  - Price alert checks (daily 9am UTC)

**Setup needed (not code):**
- [ ] Verify SES sending domain (sipsense.ai) in AWS
- [ ] Set env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `SES_FROM_EMAIL`

---

## GAP 6: SEO / Public Pages — DONE (PR #34)

## GAP 7: "Next Bottle" as Core Feature — DONE (PR #33)
