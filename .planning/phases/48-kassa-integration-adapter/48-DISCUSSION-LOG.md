# Phase 48 Discussion Log

**Date:** 2026-05-21
**Phase:** 48 — ЮKassa Integration Adapter
**Mode:** `--auto` — recommended defaults selected by Claude; no interactive AskUserQuestion calls
**Single-pass cap:** enforced (one CONTEXT.md write, no re-pass)

---

## Prior Context Loaded

- `.planning/PROJECT.md` — milestone v1.7 scope, RF constraints
- `.planning/REQUIREMENTS.md` — ADAPTER-01..06 full text
- `.planning/ROADMAP.md` — Phase 48 goal + 5 success criteria (locks `httpx` + `respx`)
- `.planning/STATE.md` — Phase 47 complete
- `.planning/phases/47-bedrock/47-CONTEXT.md` — D-47-01..09 prior decisions (Protocol slots, settings, `_money.py`, `YOOKASSA_TRUSTED_IPS`, Alembic 0033)
- `.planning/research/SUMMARY.md`, `STACK.md`, `PITFALLS.md`, `ARCHITECTURE.md` — milestone research

**Carried-forward decisions (no re-discussion):**
- Protocol slots live in `app/core/dependencies.py` (D-47-02)
- `YooKassaSettings` is standalone, lives in `app/integrations/yookassa/settings.py` (D-47-08)
- `sandbox` flag toggles ONLY IP-verifier bypass + API URL fork (D-47-07; refined in this phase to "only bypass; URL stays the same" per D-48-08)
- 6 trusted CIDRs already shipped as `YOOKASSA_TRUSTED_IPS` frozenset (Phase 47 plan 47-03)
- AST gate test module `test_locked_yookassa_constants_ast.py` already exists (Phase 47 plan 47-03); Phase 48 extends it
- Idempotence-Key (single `t`) per ЮKassa spec

---

## Codebase Scout

Reviewed:
- `apps/backend/app/integrations/email/` — pattern source (`types.py`, `client.py`, `factory.py`, `circuit_breaker.py`)
- `apps/backend/app/integrations/yookassa/` — Phase 47 shipped: `settings.py`, `webhook_verifier.py` (skeleton), `_money.py`, `_stubs.py`
- `apps/backend/app/core/dependencies.py` — Protocol slot home (referenced via D-47-02)

---

## Gray Areas Auto-Selected

`[--auto] Selected all gray areas: Transport choice, Result type shape, httpx lifecycle, Auth + URL, Idempotence-Key strategy, Boot probe target + failure mode, Receipt builder return shape, Enum + literal locking, IP verifier body, respx fixture canon, Composition-root wiring split.`

---

## Auto-Selected Decisions (per area)

### Transport choice
- **Q:** Use official `yookassa` SDK (run_in_executor) or raw `httpx.AsyncClient`?
- **Selected:** `httpx.AsyncClient` (recommended). Locked by ROADMAP.md wording ("Pure async httpx wrapper… `respx` test fixtures"). Diverges from research SUMMARY.md's SDK recommendation; rationale documented in D-48-01.

### Result type shape (ADAPTER-01)
- **Q:** Frozen dataclass + Literal classification, or Pydantic v2 model?
- **Selected:** `@dataclass(frozen=True)` with closed `Literal['ok'|'validation_error'|'transient_error'|'permanent_error']` classification. Mirrors `EmailSendResult` (D-42-13). Cloudpickle-safe for any future ARQ enqueue.

### httpx client lifecycle (ADAPTER-02)
- **Q:** Long-lived shared `AsyncClient` or fresh per call?
- **Selected:** Long-lived per process, constructed in factory, closed in lifespan teardown. Conscious divergence from email's per-call `aioboto3` (different SDK semantics).

### Auth + base URL
- **Q:** Where to put Basic Auth? Different sandbox base URL?
- **Selected:** `httpx.BasicAuth` on client; ЮKassa sandbox uses the **same base URL** with sandbox credentials; `sandbox` flag in settings affects ONLY the IP-verifier bypass.

### Idempotence-Key strategy
- **Q:** Adapter auto-generates the key, or caller passes it?
- **Selected:** Caller passes (`idempotency_key: UUID | str`). Phase 49 orchestrator persists the key in `online_payments` BEFORE the HTTP call so retries replay (Pitfall 2 mitigation).

### Boot probe (ADAPTER-03)
- **Q:** What endpoint? Behavior on failure?
- **Selected:** `GET /v3/me` (auth + connectivity, no side effects). **Non-fatal** — factory still returns the client; only logs `yookassa_boot_probe ok=False`. Diverges from email factory's fail-fast (D-42-30) per SC2 "degraded mode" requirement.

### Receipt builder (ADAPTER-04)
- **Q:** Return `dict` or typed model? Where do enums live?
- **Selected:** Returns `dict[str, Any]` (matches STACK.md §6 + ЮKassa wire shape). Three enums in `receipt.py`: `PaymentSubject(StrEnum)`, `PaymentMode(StrEnum)`, `VatCode(IntEnum)`. AST gate enforces literal `payment_subject` / `payment_mode` at every callsite (extends Phase 47 gate module per D-48-18).

### Receipt `payment_mode` literals
- **Q:** Need both `full_payment` and `full_prepayment`? When does each apply?
- **Selected:** Ship both. `full_prepayment` for online membership sales paid before activation (the common case); `full_payment` for at-point-of-consumption sales. Phase 49 orchestrator picks per sale type.

### IP verifier body (ADAPTER-05)
- **Q:** Read `request.client.host` or trust `X-Forwarded-For`?
- **Selected:** Phase 48 reads `request.client.host` only. `X-Forwarded-For` trust toggle deferred to Phase 50 (where webhook route + proxy topology land). Marked `# TODO Phase 50:` in the verifier.

### `respx` fixtures (ADAPTER-06)
- **Q:** Where do canonical response bodies live? In Python literals or JSON files?
- **Selected:** JSON files under `tests/integrations/yookassa/_responses/`; fixtures load them. 6 fixtures total (5 httpx-mocked + 1 plain-dict for the webhook body).

### Composition-root wiring split
- **Q:** Phase 48 wires which Protocol slots?
- **Selected:** Phase 48 wires ONLY `YooKassaClientProvider` (real instance replaces Phase 47 `yookassa_client_provider_noop_stub`). Other 3 slots stay no-op (Phase 49 wires activators; Phase 50 wires fiscal dispatcher).

### Circuit breaker for adapter outbound calls
- **Q:** Wrap `create_payment` with a circuit breaker in Phase 48?
- **Selected:** No. Phase 48 ships breaker-less adapter. Phase 49 orchestrator owns outbound retry/breaker semantics if needed; Phase 51 FISCAL-05 owns the fiscal-receipt dispatcher breaker (`sz:yookassa:circuit:receipts`).

---

## Scope Creep Redirected

- `POST /v3/receipts` standalone receipts → deferred (may surface in Phase 51 FISCAL-04)
- `X-Forwarded-For` proxy trust → deferred to Phase 50 (webhook route phase)
- mypy override for `yookassa.*` → rejected (SDK is not imported per D-48-05)
- Sandbox-specific base URL → rejected (does not exist in ЮKassa API v3)
- Webhook signature verification (`Notification-Sign`) → rejected (does not exist; IP allowlist + re-fetch is the model — PITFALLS Pitfall 1)

---

## Claude's Discretion Items

Documented in CONTEXT.md `<decisions>` "Claude's Discretion" subsection:
- JSON parser default (`httpx.Response.json()`)
- `User-Agent` header (`Sportzal/1.7 ЮKassa-Adapter`)
- Hardcoded `"RUB"` currency literal
- Default `quantity="1.00"`
- `confirmation.return_url` injection point (client, not orchestrator)

---

## Output

- `48-CONTEXT.md` — written (26 decisions D-48-01..26)
- 6 ADAPTER reqs mapped to plan-phase scope
- Next: `/gsd-plan-phase 48 --auto` (auto-advance via `--auto` chain)
