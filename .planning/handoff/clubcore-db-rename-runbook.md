# clubcore DB Rename Operator Runbook (Phase 62 / v1.10)

> Authored by agent; **operator-pending live execution** (precedent v1.4/v1.7/v1.8/v1.9).
> Phase 62 ships renamed config + this checklist; cutover runs ONCE at v1.10 deploy.
> After execution replace this note with `Runbook executed: YYYY-MM-DD — PASS`.
> **Lineage:** D-62-04 (operator-tier rename, NOT Alembic), D-62-05 (DNS checklist),
> D-62-07 (Redis FLUSHDB). **Authored:** 2026-05-26.
> **Evidence destination:** `v1.10-OPERATOR-EVIDENCE.md` → v1.11 / Phase 67 / RUN-08.

## 1. Pre-cutover backup

> Note (62.1): plan 62.1-08 captures fresh smoke evidence against a dedicated `clubcore_smoke` DB target — see `.planning/milestones/v1.10-OPERATOR-EVIDENCE.md`. The `sportzal.dump` filename below documents the original one-time 2026-05-26 cutover backup.

```bash
pg_dump -h <host> -U app -F c -f sportzal.dump sportzal
chmod 600 sportzal.dump
```

`chmod 600` mitigates T-62-05-01 (live PII); store on encrypted volume, delete after the 7-day rollback window.

## 2. Postgres DB rename via dump/restore (D-62-04, operator-tier)

```bash
createdb -h <host> -U app clubcore
pg_restore -h <host> -U app -d clubcore sportzal.dump
psql -h <host> -U app -d clubcore -c "SELECT count(*) FROM clients;"
```

Row-count verify on 2-3 high-volume tables (`clients`, `subscriptions`, `payments`)
against pre-cutover. Mismatch → abort, fall to Section 6 (rollback).

## 3. Redis namespace cutover (historical — completed Phase 62 / REB-03)

Phase 62 / REB-03 flipped the Redis key prefix from the legacy `sz:` namespace to the `cc:` namespace (commit 6ec1115b, 2026-05-26). The operator FLUSHDB / scan-and-DEL cutover step that previously lived here was a one-time operation tied to the v1.10 deploy; it has been executed and is no longer applicable. Phase 62 / D-62-07 lineage preserved for audit trail. Subsequent cutovers (e.g., Phase 63+ infra work) will document their own cutover steps in their own runbooks.

## 4. DNS/DKIM/SPF/DMARC checklist for new email FROM domain (D-62-05)

**v1.10 does NOT change the sending domain.** `CLUBCORE_EMAIL_FROM` is an OPTIONAL override (commented in `.env.example`); fallback chain resolves to `noreply@mail.sportzal.ru`. If operator migrates to `mail.clubcore.ru` later, complete this BEFORE setting `CLUBCORE_EMAIL_FROM` (T-62-05-05 DKIM-before-FROM):

- [ ] **SPF** — `TXT @ "v=spf1 include:<provider> -all"`
- [ ] **DKIM** — publish `TXT s1._domainkey.<domain> "v=DKIM1; k=rsa; p=..."` + configure private key on MTA
- [ ] **DMARC** — `TXT _dmarc.<domain> "v=DMARC1; p=quarantine; rua=mailto:..."` (start `p=none`, escalate after 7-14d)
- [ ] **MX** — only if new domain also receives mail (e.g. for `rua=` reports)
- [ ] Validate: send to Gmail; headers show `spf=pass`, `dkim=pass`, `dmarc=pass`
- [ ] THEN set `CLUBCORE_EMAIL_FROM=noreply@<new-domain>` in production env

## 5. Post-cutover smoke

```bash
cd apps/backend && docker compose up --build       # all services healthy; migrate exits 0
pg_isready -h <host> -U app -d clubcore            # exit 0
curl -i http://localhost:8000/api/v1/health        # HTTP/1.1 200 OK
```

Then run one targeted backend integration test (e.g. `POST /api/v1/auth/login`) to confirm session/cookie/Redis plumbing against `cc:*` + `clubcore` DB.

## 6. Rollback

```bash
dropdb -h <host> -U app clubcore
git revert <Phase 62 G-5 commit>           # reverts .env.example + docker-compose.yml
docker compose up --build
```

`sportzal.dump` from §1 is on disk within the 7-day window; Redis repopulates organically.

## Operator

andre.shipunov@icloud.com
