# Feature Research — v1.6 Email channel + Multi-user admin

**Domain:** Operator-facing CRM (single-gym pet-project, РФ/СНГ), two new pillars laid on top of an already-shipped Telegram-first system: **(1) email as a parallel notification channel** mirroring v1.1/v1.3/v1.4/v1.5 Telegram flows, **(2) owner-managed multi-user admin** (operator onboarding, deactivation, password reset, multi-actor audit traceability).
**Researched:** 2026-05-18
**Confidence:** HIGH (the patterns to mirror — locked Russian copy, anti-oracle, idempotency tables, mandatory snapshot — are all already in production; the open questions are about *what to send by email* and *how to onboard a second reception user*, not how to wire the plumbing)

> Scope reminder. v1.6 is a **subsequent** milestone bolted onto a working system. Existing Telegram flows, auth, payments, audit log (56 LOCKED events) are **not** in scope to re-research. Everything below is constrained to the new surface only.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in any modern operator CRM. Missing these = product feels incomplete or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Email channel — OTP fallback for login** | When a reception user has no Telegram link (or Telegram is down), they still need a passwordless / second-factor path. Today email/password works but Telegram OTP doesn't have an email twin. | **M** | Mirror `app/modules/auth/otp_*` shape: `email_otp_codes` table or reuse `otp_codes` with `channel ∈ {telegram, email}`; same 6-digit / 5-min TTL / 5-attempt envelope; rate-limit 5/15min reused. Russian-locked template `EMAIL_OTP_LOGIN`. |
| **Email channel — expiring-membership notice (7+3+1)** | v1.3 already sends Telegram DMs at T-7 / T-3 / T-1. Clients without a Telegram link get nothing today — silent churn. Email mirror closes the gap. | **M** | Extend `membership_notifications` UNIQUE key from `(membership_id, kind)` to `(membership_id, kind, channel)` so Telegram and email idempotency rows coexist without double-sending. Reuse 06:15 MSK cron loop; add a sibling pass that selects rows where `client.email IS NOT NULL` AND no Telegram link (or both, per D-XX). 6 locked Russian email templates `EMAIL_EXPIRING_{7D,3D,1D}_VARIANT_{A,B}` — anti-oracle A/B variant kept (`client_id.bytes[0] & 1`). |
| **Email channel — payment receipt (cash sale + refund)** | After every cash sale (v1.4 `payments`), client expects a written record. РФ tax law doesn't *require* email receipts for cash yet (54-ФЗ kicks in only for online — v1.7), but operator-facing CRMs treat it as table stakes. Refunds especially must produce a receipt trail. | **M** | New `payment_receipts` idempotency table (UNIQUE `(payment_id, channel)`); fire-on-commit hook after `record_payment` / `issue_refund`; locked Russian templates `EMAIL_PAYMENT_RECEIPT_SALE` + `EMAIL_PAYMENT_RECEIPT_REFUND` carrying `formatMoney`-style ru-RU RUB rendering (NBSP-safe in HTML). **Dependency: v1.4 payments ledger (already shipped).** |
| **Email channel — booking confirmation + 24h reminder** | v1.5 sends Telegram DMs for `BOOKING_CONFIRMED_DM` / `BOOKING_REMINDER_24H_DM`. Email mirror covers clients without Telegram. | **M** | Extend `booking_notifications` UNIQUE to `(booking_id, kind, channel)`. Reuse 06:35 MSK cron. 4 locked Russian email templates: `EMAIL_BOOKING_CONFIRMED`, `EMAIL_BOOKING_CANCELLED_BY_CLIENT`, `EMAIL_BOOKING_CANCELLED_BY_OWNER`, `EMAIL_BOOKING_REMINDER_24H`. |
| **Multi-user admin — owner invites reception user (invite-token flow)** | A one-gym CRM that requires the solo owner to manually INSERT into `users` is a non-starter once the gym hires a second receptionist. Industry-standard pattern: owner clicks "Invite", system mails one-time invite link, invitee sets their own Argon2id password. | **M** | New `user_invitations` table (UUIDv4 token, `email`, `role`, `created_by_user_id`, `expires_at` 72h, `accepted_at NULL`, `revoked_at NULL`, UNIQUE on `(lower(email)) WHERE accepted_at IS NULL AND revoked_at IS NULL`); `POST /api/v1/users/invitations` (owner-only); `POST /api/v1/users/invitations/accept` (public, accepts token + password); 1 locked Russian email template `EMAIL_USER_INVITATION`. **Anti-pattern: admin-set initial password mailed in plaintext.** Sources unanimous — never email a password. |
| **Multi-user admin — password reset (forgot-password)** | Reception loses access regularly (forgotten passwords, lost devices). Without self-service reset the owner becomes a permanent helpdesk. Reusing the invite-token mechanism is the cheapest correct path. | **M** | `password_reset_tokens` table (separate from `user_invitations` to keep semantics clean: invitation = no prior account, reset = existing account); token TTL 1h (shorter than invite — per OWASP 2025); single-use; `POST /api/v1/auth/password/reset/request` returns **the same 202 response for known + unknown email** (anti-oracle invariant — see quality gate); constant-time response (sleep-to-floor pattern, e.g. 500ms minimum) to defeat timing oracle. |
| **Multi-user admin — deactivate user (owner-only, soft)** | The owner needs to revoke a fired receptionist *immediately* without losing audit history. Hard delete would orphan FK references (audit_log, payments.received_by_user_id). | **S** | `users.deactivated_at` nullable timestamp (or `is_active BOOL DEFAULT TRUE` mirroring v1.4 `trainers.is_active`); `POST /api/v1/users/{id}/deactivate` owner-only; deactivation cascades to `logout-all` for that user's families (revoke all refresh-token families); login attempts post-deactivation return 401 `invalid_credentials` (no oracle leak — same code as wrong password). |
| **Multi-user admin — multi-actor audit trail (already-emitting actor surfaced)** | Today audit rows already carry `actor_user_id` from `request.state.user`. The work is making sure all 56 LOCKED events continue to carry the correct actor when the actor is no longer always the solo owner. | **S** | Verification + 1-2 callsite fixes max — most paths already pass actor through correctly via `require_permission` deps. New audit-event pairs: `user_invited`, `user_invitation_accepted`, `user_invitation_revoked`, `user_deactivated`, `user_reactivated`, `password_reset_requested`, `password_reset_completed`. Frozenset grows 56 → 63. |
| **Email — bounce/complaint logging (passive)** | Sending blindly into a black hole is operationally unsafe; if `reception@badtypo.gym` bounces 100 emails before the owner notices, real receipts get lost in the noise. Need a minimal "we tried, here's what happened" log. | **S** | `email_send_log` append-only table (`id`, `to_email`, `template_kind`, `provider_message_id`, `status ∈ {sent, bounced, complained, deferred}`, `received_at`); webhook endpoint `/api/v1/_webhooks/email/{provider}` (provider-signed) that flips status on bounce/complaint events. **No retry orchestrator in v1.6** — manual operator action on a bounce. |
| **Email — sender-domain authentication (SPF + DKIM + DMARC)** | Without SPF/DKIM, Gmail / Mail.ru / Yandex throw to spam ~70% of the time (Google now hard-rejects unauthenticated bulk mail). Setup is a **one-time DNS task**, not code, but it must be in the v1.6 spec as a hard launch gate. | **S** (config) | Configure SPF (single record, prefer ESP's include), DKIM (provider-generated CNAME/TXT in DNS), DMARC (start at `p=none` for monitoring → graduate to `p=quarantine`). Use a **dedicated sending subdomain** (e.g. `mail.sportzal.ru`) so reputation is isolated from the corporate domain. **Owner action**, not developer action — but verification runbook lands in v1.6 milestone close. |
| **Email — plaintext + minimal-HTML dual-part** | Some Russian email clients (older corporate, Mail.ru web on slow connection) still degrade HTML; plaintext fallback prevents an unreadable receipt. | **S** | Every template ships as `(subject, plaintext_body, html_body)` tuple; HTML is "minimal-HTML" — no tracking pixels, no remote images, no JS, table-based layout for legacy Mail.ru rendering. Russian copy is **owner-locked** (same `D-27-OWNER-COPY-LOCK` pattern). |

### Differentiators (Competitive Advantage)

Features that set Sportzal apart in the one-gym-CRM segment. The bar is low here — the segment is dominated by Excel + WhatsApp.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Dual-channel notification (Telegram preferred, email fallback)** | Most РФ gym CRMs (1С:Фитнес, Mobifitness) are SMS-first or email-only. Sportzal's value: Telegram-native for clients who use Telegram (~85% in RU 18-35), email for the rest, with the same locked Russian copy on both. Anti-oracle invariant preserved end-to-end. | **M** | Resolution rule: per-client preference defaults to "Telegram if linked, else email". Owner can override per-client (`clients.preferred_channel ∈ {auto, telegram, email, both}`). For OTP fallback specifically: `both` is risky (which OTP wins?) → restrict to `auto / telegram / email`. |
| **Locked Russian copy + owner sign-off per template** | Every other CRM in this segment lets the operator (or worse, the developer) hand-edit notification templates and ships generic / typo-ridden copy. v1.3 and v1.5 already pay this cost — v1.6 just preserves it on the new channel. | **S** | Mirror `D-20-9` / `D-27-OWNER-COPY-LOCK` mechanism: each new template constant is owner-signed in a decision row before merge; modifying the constant requires a new sign-off. |
| **Per-template anti-oracle A/B variant for membership/booking emails** | The expiring-membership Telegram flow already varies copy by `client_id.bytes[0] & 1` to defeat timing/content-based oracle leak in shared-screen scenarios. Extending the same invariant to email keeps the two channels behaviorally identical. | **S** | Same selector function reused; just doubles the template constant count for expiring + booking. Receipt and OTP templates do NOT need variants (no oracle surface). |
| **Multi-user audit traceability surfaced in receipts** | Cash sale email receipts include "Принял: Анна П." (operator first-name + last-initial). Owner can audit at a glance from email archive without opening admin-web. | **S** | One JOIN in receipt-render path; field is `actor_display_name` derived from `users.full_name`. No new endpoint needed. |
| **Invite-link copy-paste fallback (owner sees the link)** | Email deliverability is never 100%. Owner sees the invitation URL in admin-web immediately after creating it and can paste it into Telegram / SMS / WhatsApp if the email doesn't arrive. | **S** | `POST /api/v1/users/invitations` returns the `accept_url` in the response body **once** (creation-time only — never echoed again, since the URL is the secret). Stored audit row notes "url returned to owner". |
| **`logout-all-on-deactivate` happens atomically** | Most competitor CRMs deactivate a user but leave their browser session live for hours until the JWT expires. Sportzal already has refresh-rotation families — deactivation revokes them in the same transaction. | **S** | Reuse v1.1 `revoke_family` machinery; just iterate all families for the user. Audit `user_deactivated` payload includes `families_revoked: N`. |
| **DMARC `rua` reports surface to owner** | The owner gets a weekly summary email of who's been spoofing the gym's domain (basically "0 spoof attempts this week, you're safe"). Trivial config trick, but no other RU gym CRM bothers. | **S** | Configure `rua=mailto:owner@gym.ru` in the DMARC record. No code. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Email preference centre / unsubscribe management UI** | Modern email best practice; CAN-SPAM / GDPR-style framing. | All v1.6 email is **transactional** (CAN-SPAM doesn't apply; РФ ФЗ-152 transactional carve-out applies). A preference centre implies marketing campaigns (out of scope through v2.0). Building UI for "do you want to receive payment receipts? Y/N" is silly — if the answer is N, the client shouldn't be doing business with the gym. | **No unsubscribe link on transactional emails.** Plaintext footer line: "Это служебное письмо от тренажёрного зала Sportzal. Если вы получили его по ошибке, напишите owner@gym.ru." Single mailto, no API. |
| **Marketing campaigns / mailing lists / scheduled blasts** | "We could just send a promo email to everyone with an expiring membership!" | This is a different product. Marketing email = subscription consent + suppression list + send-time optimization + unsubscribe link compliance + likely a separate ESP account (high-volume ESPs reject mixing transactional and marketing on same IP). Sportzal's volume is ~5-50 emails/day; ESPs for that volume don't even sell marketing tiers. | **Explicit out-of-scope.** Re-evaluate in v3+ (post-launch, post-multi-tenant). |
| **Multi-factor auth with TOTP / hardware keys** | "Reception logs in from a shared front-desk PC, MFA is best practice." | Reception turnover is high; TOTP enrollment friction is real; the gym already has CCTV at front desk for physical access control. Email OTP fallback already covers the "lost phone" recovery path. Owner can enable later if pain becomes real. | Telegram OTP (already shipped) + email OTP (v1.6) already provide step-up auth on demand. Reception can be required to re-enter password every N hours via short access-token TTL (already 15min) — no new mechanism needed. |
| **Per-user RBAC granularity / custom roles** | "What if the night reception shouldn't be able to issue refunds?" | Sportzal currently has 2 roles (owner / reception) and `OWNER_ONLY` is 26 entries. Custom roles = role designer UI = role-explosion management = enterprise SaaS scope. The gym has at most 3-5 operators ever. | Stay 2-role. If a refund-restriction comes up, add a third hard-coded role (`reception_no_refund`) and one frozenset row — but only when there's a real second receptionist asking for it. |
| **In-app inbox / notification centre** | "Email is unreliable; let's show a bell icon in admin-web with notifications for operators." | Operators don't need to see expiring-membership notices in their inbox — those go to clients. The only operator-facing notification surface is the dashboard itself (v1.8 reports). Building an inbox is building a second UI for data that already has a UI. | Owner gets one weekly digest email (v1.7+) summarizing bounces / failed sends / deactivated users — that's it. |
| **Admin-set initial password (mailed in plaintext)** | "Just generate `Welcome2026!` for new users and email it" — sounds simpler than invite-token flow. | Cardinal sin: passwords in email get archived, forwarded, indexed by spam filters, screenshot. Industry has moved away from this; OWASP/Specops/Auth0 all explicit. Also: forces password rotation on first login, doubling complexity. | **Invite-token flow only.** Owner clicks "Invite" → token-link emailed → invitee sets their own Argon2id password on accept. Never plaintext. |
| **Email-based username (separate from login email)** | "Allow different login email vs notification email per user." | Two email fields means two enumeration surfaces, two verification flows, two reset paths. Real value: ~zero for a 3-5 operator gym. | **Single `users.email` column** serves login + notifications. Future: optional `clients.email` for client-side receipts is separate (clients ≠ users). |
| **Bounce auto-retry with exponential backoff** | "Email failed, we should retry it like a webhook." | Bounces are usually permanent (typo, mailbox full, domain gone). Soft bounces (transient SMTP) are already retried by every modern ESP internally. Building our own retry loop in ARQ duplicates work and risks burn-through of sender reputation. | **No app-layer retry.** Trust ESP's internal retry; log bounce; surface to owner via weekly digest. |
| **Multi-channel "any one of N" for OTP** | "If Telegram fails, automatically fall back to email — same OTP." | Two delivery channels for the *same* OTP doubles the attack surface (compromise either inbox) and creates UX confusion ("which 6-digit do I type?"). Race condition between channels also messy. | **One channel per request.** User picks Telegram OR email at login tab; system delivers via that channel only. If the chosen channel fails (Telegram blocked, email bounce), user re-tries with the other. |
| **Self-service signup for reception users** | "Just put a /signup page so new receptionists can register themselves." | Sportzal is a single-tenant private CRM — there's no "the public" allowed in. Self-signup means anyone with the URL is in the audit log as a real actor. | Owner-only invitation, no public signup. |
| **Client-side email preference per client** (different from operator preference centre — this is for clients) | "Some clients want both Telegram and email; some want only Telegram." | At ~100 clients/gym, manually setting per-client preferences in admin-web is feasible; building a client-facing preference page is not. | `clients.preferred_channel ∈ {auto, telegram, email, both}` editable from admin-web `/clients/{id}` only — no client-facing UI. Default `auto` (Telegram if linked, else email). |

---

## Feature Dependencies

```
EXISTING (already shipped — v1.1 through v1.5):
    auth.users  ──provides──> actor_user_id for all audit emits
    payments    ──provides──> payment row for receipt trigger (v1.4)
    bookings    ──provides──> booking row for confirm/reminder (v1.5)
    memberships ──provides──> expiring rows for 7+3+1 cron (v1.3)
    audit_log   ──provides──> LOCKED_AUDIT_EVENTS frozenset (56 entries)

NEW in v1.6:
    [email-integration]
        └──requires──> ESP selection (Resend / SES / Mailgun — STACK.md decision)
        └──requires──> sender-domain DNS (SPF/DKIM/DMARC — owner config gate)
        └──requires──> email_send_log table (passive bounce tracking)

    [email-otp-fallback]
        └──requires──> [email-integration]
        └──extends───> auth.otp_codes (add channel column, OR new email_otp_codes table)

    [email-expiring-soon]
        └──requires──> [email-integration]
        └──extends───> membership_notifications (UNIQUE key gains channel column)
        └──reuses────> 06:15 MSK cron (already shipped v1.3)

    [email-payment-receipt]
        └──requires──> [email-integration]
        └──requires──> payment_receipts table (idempotency)
        └──hooks-into> record_payment + issue_refund commit paths

    [email-booking-notifications]
        └──requires──> [email-integration]
        └──extends───> booking_notifications (UNIQUE key gains channel column)
        └──reuses────> 06:35 MSK cron (already shipped v1.5)

    [multi-user-admin-invite]
        └──requires──> user_invitations table
        └──requires──> [email-integration] (for invite-link delivery)
        └──extends───> LOCKED_AUDIT_EVENTS (+3: invited / accepted / revoked)

    [multi-user-admin-deactivate]
        └──requires──> users.is_active OR users.deactivated_at column
        └──hooks-into> refresh_tokens revoke-family machinery (already shipped v1.1)
        └──extends───> LOCKED_AUDIT_EVENTS (+2: deactivated / reactivated)

    [multi-user-admin-password-reset]
        └──requires──> password_reset_tokens table (separate from user_invitations)
        └──requires──> [email-integration]
        └──must-honour> ANTI-ORACLE INVARIANT (same 202 for known + unknown email)
        └──extends───> LOCKED_AUDIT_EVENTS (+2: requested / completed)

    [multi-user-audit-traceability]
        └──reuses────> existing actor_user_id flow from require_permission
        └──verifies──> all 56 existing emits already carry actor (mostly already true)
        └──extends───> audit-row response projection to surface actor_display_name
```

### Dependency Notes

- **Every email feature requires the ESP integration + DNS auth first.** Phase ordering: integration scaffold (Phase 41) → DNS gate → individual templates layered on. STACK.md owns the ESP selection.
- **`email_send_log` is a hard prerequisite for any production launch.** Without it, the owner has no way to diagnose "client says they didn't get the receipt" — and that question *will* come up on day one.
- **Multi-user invite requires email integration.** The two pillars are not independent — the invite-link is delivered via the email channel. v1.6 must ship both or neither (the invite flow without email is meaningless; an email channel without operator multi-user is leaving owner cash on the table).
- **Password reset MUST honour anti-oracle invariant.** Forgot-password endpoint returns 202 with body `{"status":"accepted"}` for *every* email, real or not — and waits a constant-time floor (500ms) before responding. **Stated as a quality gate** in the milestone spec.
- **`booking_notifications` and `membership_notifications` UNIQUE-key extension** is a single Alembic migration step but it's a **breaking semantics change** for any in-flight idempotency rows. Migration plan: add `channel TEXT NOT NULL DEFAULT 'telegram'` then drop default — preserves existing rows as Telegram-channel and new email-channel rows coexist.
- **Phase 41 must be the email-integration scaffold**, not a feature-bearing phase. (Same shape as v1.0 Phase A skeleton.) Without it the rest of v1.6 has no commit-floor.

---

## MVP Definition

### Launch With (v1.6)

Minimum viable product — what's needed to ship v1.6 against the milestone goal "close last infra-pillar before online payments".

- [ ] **Email integration scaffold** — ESP wired (STACK.md owns provider choice), `email_send_log` table, send-from helper, DKIM/SPF/DMARC owner runbook — *why essential: every other v1.6 feature requires this*
- [ ] **Email OTP fallback for login** — login tab #3 alongside email/password + Telegram OTP — *why essential: closes auth gap for clients without Telegram and is the simplest end-to-end test of the email send path*
- [ ] **Email expiring-soon (7+3+1) mirror** — same selector as Telegram cron, channel-aware idempotency — *why essential: the operator-facing payoff for adding email at all — revenue retention from non-Telegram clients*
- [ ] **Email payment-receipt (sale + refund)** — hook into v1.4 commit paths — *why essential: the operator-facing artefact most users will ask for first*
- [ ] **Email booking confirmed + 24h reminder** — channel-aware extension of v1.5 templates — *why essential: parity with Telegram booking flow*
- [ ] **Multi-user admin — owner invites reception (invite-token flow)** — `POST /api/v1/users/invitations` + accept endpoint + locked Russian template — *why essential: the operator-onboarding gap is the headline of the milestone*
- [ ] **Multi-user admin — password reset (anti-oracle)** — request + complete endpoints, 1h TTL, constant-time response — *why essential: without it, the owner becomes a permanent helpdesk for forgotten passwords*
- [ ] **Multi-user admin — deactivate user + atomic logout-all** — owner-only PATCH/DELETE, families revoked in same UoW — *why essential: the "fired receptionist still has session" scenario is a hard security gap*
- [ ] **Multi-user audit traceability** — 7 new LOCKED events, verification that all 56 existing emits carry correct `actor_user_id` — *why essential: regulatory + forensic hygiene; cheap because most callsites are already correct*
- [ ] **OpenAPI drift gate refresh** — `openapi.json` + `schema.d.ts` regenerated, forward-guards for new paths — *why essential: handoff invariant since v1.1*

### Add After Validation (v1.7+)

Features to add once core is working and we've seen real email volume.

- [ ] **Weekly digest to owner** (bounces, deactivations, send failures summary) — *trigger: after v1.6 produces ≥1 month of `email_send_log` rows so we know what's worth summarizing*
- [ ] **Per-client `preferred_channel` override UI** — *trigger: owner asks "client X wants email only, not Telegram"; cheap to add but no compelling reason day-1*
- [ ] **Bounce auto-flag in admin-web `/clients/{id}`** (badge "email may be invalid" after 1 hard bounce) — *trigger: after first real-world hard bounce; until then it's speculative*
- [ ] **Audit log read API** (`GET /api/v1/audit-log` with filter by actor) — *scheduled for v1.8 (existing roadmap); now that multi-user is real, "who did what" is meaningful to query*

### Future Consideration (v2+)

Features to defer until product-market fit is established or a second tenant exists.

- [ ] **Marketing/campaign email** — *why defer: out of scope through v2.0; entirely different product surface and probably a different ESP*
- [ ] **Custom RBAC roles beyond owner/reception** — *why defer: 26-entry frozenset already handles every observed case; custom roles is enterprise SaaS scope creep*
- [ ] **TOTP / WebAuthn second factor** — *why defer: email + Telegram OTP already provide step-up; hardware factors only matter at higher attack-value targets*
- [ ] **Per-client email preference centre (client-facing)** — *why defer: gym has ~100 clients, admin-web edit is enough*
- [ ] **Email preference centre for operators** — *why defer: transactional only, nothing to unsubscribe from*
- [ ] **SMS as a third channel** — *why defer: РФ SMS gateways are expensive and Telegram OTP already covers passwordless; revisit only if a hard requirement emerges*

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Email integration scaffold + DKIM/SPF/DMARC runbook | HIGH (gate for everything else) | MEDIUM | **P1** |
| Email OTP fallback for login | MEDIUM | MEDIUM | **P1** |
| Email expiring-soon (7+3+1) | HIGH (revenue retention) | MEDIUM | **P1** |
| Email payment receipt (sale + refund) | HIGH (operator habit) | MEDIUM | **P1** |
| Email booking confirmed + 24h reminder | MEDIUM | MEDIUM | **P1** |
| Multi-user invite-token flow | HIGH (milestone headline) | MEDIUM | **P1** |
| Password reset (anti-oracle) | HIGH | MEDIUM | **P1** |
| Deactivate user + atomic logout-all | HIGH (security) | LOW | **P1** |
| Multi-user audit traceability | MEDIUM (hygiene) | LOW | **P1** |
| OpenAPI drift gate refresh | HIGH (handoff invariant) | LOW | **P1** |
| Dual-channel resolution (`clients.preferred_channel`) | MEDIUM | LOW | **P2** |
| Locked email copy + owner sign-off per template | MEDIUM (consistency) | LOW | **P1** (mandated by quality gate) |
| Anti-oracle A/B variant on expiring + booking emails | LOW (matches existing invariant) | LOW | **P1** (consistency with v1.3/v1.5) |
| Invite-link copy-paste fallback (URL in response) | MEDIUM | LOW | **P2** |
| DMARC `rua` weekly reports → owner | LOW | LOW (DNS only) | **P2** |
| Bounce/complaint webhook + `email_send_log` | HIGH (operational sanity) | MEDIUM | **P1** |
| Plaintext + HTML dual-part templates | MEDIUM | LOW | **P1** |
| Owner weekly digest of bounces/deactivations | LOW (early) | MEDIUM | **P3** (v1.7+) |
| Email preference centre (clients) | LOW | HIGH | **P3** (anti-feature for now) |
| Marketing campaigns | NEGATIVE (off-strategy) | HIGH | **P3** (out of scope through v2.0) |

**Priority key:**
- **P1:** Must have for v1.6 launch
- **P2:** Should have, add if time permits within v1.6
- **P3:** Future consideration

---

## Competitor Feature Analysis

(Indicative — single-gym CRM segment in РФ; data points from public marketing pages, not deep audit.)

| Feature | 1С:Фитнес-клуб (incumbent) | Mobifitness (mid-market SaaS) | FitBase (cheap-SaaS) | Sportzal (our approach) |
|---------|----------------------------|-------------------------------|----------------------|--------------------------|
| Notification channels | SMS + email | SMS + email + push (mobile app) | SMS + email | **Telegram-primary + email fallback** (cheaper + higher engagement in RU 18-35) |
| Operator multi-user | Yes (Windows-style user mgmt) | Yes (web invite-token) | Yes (admin-set password — anti-pattern) | **Invite-token flow** (industry-standard) |
| Email receipts | Yes (PDF attachment) | Yes (HTML inline) | Yes (HTML inline) | **HTML inline + plaintext fallback**; no PDF (deferred to 54-ФЗ v1.7) |
| Anti-oracle on forgot-password | Inconsistent (likely leaks) | Unknown | Likely leaks | **Explicit invariant**, constant-time floor + 202 for all |
| Locked Russian copy | No (operator-editable) | No (operator-editable) | No (operator-editable) | **Yes, owner-sign-off per template** — consistency + brand control |
| Bounce/complaint logging | Hidden in SMTP logs | ESP dashboard only | None | **First-class `email_send_log` table** queryable from admin-web |
| DKIM/SPF/DMARC | Owner-handled, no docs | ESP-managed | Owner-handled, no docs | **Owner runbook in milestone close**, dedicated sending subdomain recommended |
| Marketing campaigns | Yes (bundled — feature bloat) | Yes (separate tier) | Yes (bundled) | **No** (explicitly out of scope) |
| Custom RBAC roles | Yes (Windows AD-style) | Limited | No | **No** (2 hard-coded roles, frozenset-gated) |

**Strategic positioning:** Sportzal is the **opinionated minimal** option — fewer features, but every feature is correct (locked copy, anti-oracle, race-safe at DB layer, append-only audit). Target buyer is a single-gym owner who values not getting hacked / sued / spammed over having a Christmas-tree feature list.

---

## Complexity Reference (S/M/L per quality gate)

- **S (Small, ≤1 day)** — single migration + service method + audit emit; reuses existing machinery; e.g. deactivate user, anti-oracle A/B variant on existing copy, `actor_display_name` in receipt
- **M (Medium, 2-4 days)** — new table + new endpoints + new locked template + new audit events; bridges to external service or extends idempotency contract; e.g. invite-token flow, email OTP fallback, payment-receipt hook
- **L (Large, ≥5 days)** — net-new subsystem requiring research; not present in v1.6 scope (the milestone is intentionally bridging, not greenfield)

Aggregate v1.6 weight ≈ 7 × M + 4 × S ≈ 18-26 working days (consistent with v1.3's 6-day / 44-req shape and v1.5's 18-day / 57-req shape — v1.6 sits between).

---

## Quality-Gate Checklist (re-applied)

- [x] **Categories clear** — Email-Templates / Multi-User-Admin / Audit-Traceability separated above
- [x] **Complexity noted per feature** — S/M/L column in every table
- [x] **Dependencies on existing modules called out** — payments (v1.4), bookings (v1.5), memberships (v1.3), auth/users (v1.1), audit_log (v1.1+)
- [x] **Anti-features explicitly listed** — 11 anti-features documented, each with rationale and alternative
- [x] **Locked Russian copy + owner sign-off pattern preserved** — explicit in Table Stakes (last row of multi-channel section) and Differentiators (locked copy row); mirrors `D-20-9` / `D-27-OWNER-COPY-LOCK`
- [x] **Anti-oracle invariant on forgot-password** — flagged as quality-gate-mandated invariant in Table Stakes (password reset row) and Dependency Notes; same 202 for known + unknown email, constant-time floor

---

## Sources

- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html) — anti-enumeration ("If an account exists for this email…") + constant-time response patterns + reset-token TTL guidance (single-use, 1h floor) — **HIGH confidence**, authoritative
- [OWASP WSTG — Testing for Weak Password Change or Reset Functionalities](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/04-Authentication_Testing/09-Testing_for_Weak_Password_Change_or_Reset_Functionalities) — verification methodology applied to anti-oracle quality gate — **HIGH**
- [Vaadata — Exploring Password Reset Vulnerabilities and Security Best Practices](https://www.vaadata.com/blog/exploring-password-reset-vulnerabilities-and-security-best-practices/) — confirms token-in-URL avoidance, single-use + rate-limit patterns — **MEDIUM**
- [Mailgun — Implementing SPF, DKIM, and DMARC for Reliable Email Delivery](https://www.mailgun.com/blog/dev-life/how-to-setup-email-authentication/) — confirms dedicated-subdomain pattern + DKIM/SPF/DMARC owner runbook shape — **MEDIUM**
- [Brevo — SPF, DKIM, and DMARC explained](https://www.brevo.com/blog/understanding-spf-dkim-dmarc/) — confirms 2.7× inbox-placement uplift for fully-authenticated senders — **MEDIUM**
- [Postmark — What is transactional email and what is it used for?](https://postmarkapp.com/blog/what-is-transactional-email-and-how-is-it-used) — confirms category boundary between transactional (no unsubscribe) and marketing (mandatory unsubscribe) — **HIGH**
- [Klaviyo — What Is a Transactional Email? 7 Types and How to Use Them](https://www.klaviyo.com/blog/transactional-email) — confirms 7-type taxonomy maps cleanly to v1.6 scope (OTP, receipt, account-activity, notification) — **MEDIUM**
- [Specops — Scripting new user onboarding with First Day Password](https://specopssoft.com/blog/scripting-new-user-onboarding-initial-password/) — explicit warning that "sending passwords via email is no longer supported" — anchors anti-feature "admin-set initial password" — **HIGH**
- [WSO2 — Invite user to set password](https://is.docs.wso2.com/en/latest/guides/account-configurations/user-onboarding/invite-user-to-set-password/) — confirms invite-token flow as industry-standard pattern with TTL-bounded acceptance — **MEDIUM**
- [Auth0 — User Onboarding Strategies in a B2B SaaS Application](https://auth0.com/blog/user-onboarding-strategies-b2b-saas/) — admin-provisioning vs self-service distinction; aligns with Sportzal's single-tenant private CRM (owner-only invitation, no public signup) — **MEDIUM**
- [TechTarget — Enumeration Attacks: What They Are and How to Prevent Them](https://www.techtarget.com/searchsecurity/tip/What-enumeration-attacks-are-and-how-to-prevent-them) — broader enumeration-attack taxonomy beyond just password reset (login error messages, OTP "user exists" leaks) — informs constant-time invariant on login deactivation 401 — **MEDIUM**

Existing project artefacts (HIGH confidence — local sources):
- `/Users/andre/Workspace/Development/clubcore/.planning/PROJECT.md` — `LOCKED_AUDIT_EVENTS` 56-entry frozenset, `OWNER_ONLY` 26-entry RBAC, anti-oracle DM patterns, `D-27-OWNER-COPY-LOCK` sign-off mechanism, `membership_notifications` / `booking_notifications` idempotency table shapes
- `/Users/andre/Workspace/Development/clubcore/.planning/MILESTONES.md` — v1.1 refresh-rotation family + revoke-family machinery; v1.3 expiring-soon cron + per-client A/B variant; v1.4 payments append-only ledger; v1.5 booking notifications

---
*Feature research for: v1.6 Email channel + Multi-user admin (Sportzal gym CRM, РФ/СНГ, single-gym pet-project)*
*Researched: 2026-05-18*
