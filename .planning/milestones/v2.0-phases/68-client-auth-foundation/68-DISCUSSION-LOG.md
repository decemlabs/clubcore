# Phase 68: Client Auth Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-29
**Phase:** 68-Client Auth Foundation
**Areas discussed:** OTP delivery flow, Profile self-service scope, aud claim & staff impact, Client session storage

---

## OTP Delivery Flow

### How does a member receive the OTP via Telegram?
| Option | Description | Selected |
|--------|-------------|----------|
| DM to linked chat | Look up Client by phone; bot DMs code to Client.telegram_user_id | ✓ |
| Deep-link bind-then-code | Reuse t.me deep-link; member opens bot, bot binds + DMs code | |

### Known phone with no linked telegram_user_id?
| Option | Description | Selected |
|--------|-------------|----------|
| Silent no-op | Byte-identical to unknown/soft-deleted (anti-oracle); no code sent | ✓ |
| Deep-link fallback | Return deep-link to bind first — breaks byte-identical anti-oracle | |

### How to store client OTP codes (OtpCode.user_id FKs to staff)?
| Option | Description | Selected |
|--------|-------------|----------|
| Reuse via telegram_chat_id | Store rows keyed by telegram_chat_id, user_id NULL | |
| Add client_id column | Add nullable client_id FK + mutual-exclusivity CHECK | ✓ |
| You decide | Leave storage shape to planner | |

**User's choice:** DM to linked chat + silent no-op + add client_id column.
**Notes:** Telegram linking (setting telegram_user_id) acknowledged as a staff/onboarding prerequisite, out of this phase.

---

## Profile Self-Service Scope

### What can a client edit via PATCH /client/me?
| Option | Description | Selected |
|--------|-------------|----------|
| Email only | Matches CAUTH-05; smallest attack surface; rest read-only | ✓ |
| Email + safe profile fields | Also name/birthday/emergency_contact | |

### What does GET /client/me return?
| Option | Description | Selected |
|--------|-------------|----------|
| Core identity fields | id, phone, email, names, birthday, gender | ✓ (after redirect) |
| Core + membership hints | Adds hasActiveMembership — flagged as Phase 69 scope creep | (initially picked) |
| You decide | Planner finalizes field list | |

**Scope redirect:** User initially picked "Core + membership hints"; on flagging the Phase 69 boundary, chose **Keep /me identity-only**.

### Duplicate email on PATCH?
| Option | Description | Selected |
|--------|-------------|----------|
| 409 generic | Non-enumerating 'email_unavailable'; map IntegrityError | ✓ |
| 422 validation | Field-level validation error | |
| You decide | Planner picks status/shape | |

**User's choice:** Email-only edit; identity-only GET (no membership); 409 generic on duplicate.
**Notes:** Membership reads explicitly reserved for Phase 69.

---

## aud Claim & Staff Impact

### What happens to staff tokens?
| Option | Description | Selected |
|--------|-------------|----------|
| Staff stays aud-less | Frozen staff token untouched; only client carries aud | ✓ |
| Staff gains aud:"staff" | Symmetric aud on both — touches frozen token shape | |

### How to decode client token / load principal?
| Option | Description | Selected |
|--------|-------------|----------|
| Separate client decode + loader | New decode_client_token + register_client_loader; parallel stack | ✓ |
| Extend shared decoder | Make decode_access_token aud-aware — couples principals | |
| You decide | Planner picks separate-vs-shared | |

**User's choice:** Staff stays aud-less; fully parallel client decode + loader stack.
**Notes:** Protects CISO-01 byte-parity; client token has no staff Role so cannot reuse decode_access_token.

---

## Client Session Storage

### How to store client refresh sessions?
| Option | Description | Selected |
|--------|-------------|----------|
| Separate client refresh table + Redis ns | client_refresh_token + auth:client:* namespace; port rotation | ✓ |
| Shared table + principal discriminator | refresh_token + principal_type column | |
| You decide | Planner picks shape | |

### Per-phone OTP limits (CAUTH-06)?
| Option | Description | Selected |
|--------|-------------|----------|
| 60s cooldown + 5/day | Conservative abuse protection | ✓ |
| 30s cooldown + 10/day | More forgiving | |
| You decide | Planner sets values | |

**User's choice:** Separate client refresh table + Redis namespace; 60s cooldown + 5/day per phone (per-IP 5/15min locked).
**Notes:** New rate-limit keys required — existing rate_limit.py is per-email login only.

---

## Claude's Discretion

- Per-IP proxy / X-Forwarded-For handling.
- Client access-token TTL, CSRF token naming, logout-all-sessions behavior.
- Exact error envelope shapes where not specified — follow existing conventions.

## Deferred Ideas

- Telegram account linking (setting Client.telegram_user_id) — staff/onboarding prerequisite, own phase.
- Broader client profile self-edit (name/birthday/emergency_contact) — possible later phase.
- Membership/status hints on /me — Phase 69 (CHOME-*).
