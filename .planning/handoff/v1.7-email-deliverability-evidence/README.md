# v1.7 Email Deliverability Evidence — CARRY-01 Operator Capture Procedure

**Phase:** 52-cross-channel-notifications-v1-6-carry-out
**Requirement:** CARRY-01 (closes DEFER-46-01 / VER-12)
**Decision refs:** D-52-13, D-52-14, D-46-19, D-46-20, T-52-08

---

## Purpose

This directory holds the operator-captured evidence from the live
RU email-deliverability probe run. The probe sends to three Russian mailbox
providers (yandex.ru, mail.ru, rambler.ru) via the production Yandex Postbox
SES-V2 adapter and confirms SPF / DKIM / DMARC alignment.

**The AI agent ships this scaffolding. The operator runs the live probe with
real credentials and saves the captured evidence here. This closes DEFER-46-01.**

---

## Required Environment Variables

Set ALL of the following before running the probe:

| Variable | Description | Required |
|----------|-------------|----------|
| `PROBE_YANDEX_TO` | Operator-owned yandex.ru recipient alias (e.g. `you+probe@yandex.ru`) | YES |
| `PROBE_MAIL_TO` | Operator-owned mail.ru recipient alias (e.g. `you+probe@mail.ru`) | YES |
| `PROBE_RAMBLER_TO` | Operator-owned rambler.ru recipient alias (e.g. `you+probe@rambler.ru`) | YES |
| `EMAIL_PROVIDER_API_KEY` | Yandex Postbox secret key (SES-V2 `AWS_SECRET_ACCESS_KEY`) | YES |
| `AWS_ACCESS_KEY_ID` | Yandex Postbox access key ID | YES |
| `EMAIL_FROM_DOMAIN` | Sending domain (e.g. `mail.sportzal.ru`) | YES (defaults to `mail.sportzal.ru`) |
| `EMAIL_FROM_ADDRESS` | Sender address (e.g. `noreply@mail.sportzal.ru`) | NO (auto-derived from `EMAIL_FROM_DOMAIN`) |

**Security (T-52-08):** Never commit real credentials or full recipient
addresses to this directory. The captured evidence files must use only
redacted recipient addresses (`***@yandex.ru` form) per D-46-20.

---

## Run Command

From `apps/backend/`:

```bash
PROBE_YANDEX_TO=you+probe@yandex.ru \
PROBE_MAIL_TO=you+probe@mail.ru \
PROBE_RAMBLER_TO=you+probe@rambler.ru \
EMAIL_PROVIDER_API_KEY=<yandex-postbox-secret-key> \
AWS_ACCESS_KEY_ID=<yandex-postbox-access-key-id> \
EMAIL_FROM_DOMAIN=mail.sportzal.ru \
uv run python -m scripts.verify.v1_6_email_probe
```

**Exit codes:**
- `0` — All 3 sends returned `ok=True` with a `provider_message_id`
- `1` — At least one send failed
- `2` — Operator misconfiguration (missing env vars)

---

## What to Capture

After a successful probe run (exit code 0):

1. **In each recipient mailbox**, open the probe email and select
   "Show original" / "View source" (Gmail: "Show original"; Yandex Mail:
   "Письмо в исходном виде"; Mail.ru: "Исходный текст письма").

2. **Locate the `Authentication-Results:` header block.** It should show:
   - `spf=pass` — the sending IP is authorised by your SPF record
   - `dkim=pass` — the DKIM signature is valid
   - `dmarc=pass` — DMARC policy passes (alignment of SPF/DKIM with From: domain)

3. **Copy the redacted header** — replace the recipient local-part with `***`
   and provider-internal IPs with `<redacted>`. Full addresses must never
   land in committed files (T-52-08 / D-46-20).

---

## Evidence File Format

Save one YAML file per provider. Use the filenames below. The probe script's
stdout block can be pasted directly as the `provider_message_id` value.

### `yandex_ru.yaml`

```yaml
provider: yandex.ru
to: "***@yandex.ru"
provider_message_id: "<paste from probe stdout>"
timestamp: ""          # ISO-8601 UTC, e.g. 2026-05-23T18:00:00Z
authentication_results: |
  <paste verbatim Authentication-Results: header block from mailbox "show original">
  spf=pass ...
  dkim=pass ...
  dmarc=pass ...
notes: ""
```

### `mail_ru.yaml`

```yaml
provider: mail.ru
to: "***@mail.ru"
provider_message_id: "<paste from probe stdout>"
timestamp: ""
authentication_results: |
  <paste verbatim Authentication-Results: header block>
  spf=pass ...
  dkim=pass ...
  dmarc=pass ...
notes: ""
```

### `rambler_ru.yaml`

```yaml
provider: rambler.ru
to: "***@rambler.ru"
provider_message_id: "<paste from probe stdout>"
timestamp: ""
authentication_results: |
  <paste verbatim Authentication-Results: header block>
  spf=pass ...
  dkim=pass ...
  dmarc=pass ...
notes: ""
```

---

## Acceptance Criteria for CARRY-01 Closure

DEFER-46-01 is closed when:

- [ ] All three providers received the probe email (probe exit code 0)
- [ ] `Authentication-Results` headers captured for yandex.ru showing `spf=pass`, `dkim=pass`, `dmarc=pass`
- [ ] `Authentication-Results` headers captured for mail.ru
- [ ] `Authentication-Results` headers captured for rambler.ru
- [ ] Three YAML files saved to this directory with redacted recipients
- [ ] No real credentials or full email addresses committed

Note: per D-46-22, a 1-of-3 alignment partial pass is not a milestone-close
blocker. Document the partial result in the relevant `notes:` field.

---

## Scaffolding Attestation

The AI agent (Phase 52, Plan 52-03) attests:

- The probe script at `apps/backend/scripts/verify/v1_6_email_probe.py`
  targets all three required providers (yandex.ru, mail.ru, rambler.ru)
  via `PROBE_YANDEX_TO`, `PROBE_MAIL_TO`, `PROBE_RAMBLER_TO` env vars.
- The script uses the production-shape `EmailClient` (Yandex Postbox SES-V2),
  not the sandbox stub.
- The `Authentication-Results` capture procedure is documented above.
- The live run and evidence capture are **operator deliverables** (D-52-14).

*Scaffolding ready. Awaiting operator execution.*
