# Phase 98: PWA ReferralScreen - Pattern Map

**Mapped:** 2026-06-08
**Files analyzed:** 10 (4 backend, 6 frontend) + 2 new test files
**Analogs found:** 12 / 12 (every file has a strong in-repo analog)

This is a full-stack phase: a backend aggregate read endpoint + a pixel-perfect PWA screen
port + deep-link plumbing. Every target file maps onto an existing analog already in the
codebase — there are no greenfield patterns. The two dominant templates are:

- **Backend:** the loyalty client-read endpoints (`_sum_balance` fold + raw-SQL cross-module
  reads, D-54-08) and the Phase-96 referral service/router/test harness.
- **Frontend:** the Phase-94 ChatScreen graduation recipe (CSS scope to `.x-root`, chrome
  strip, `@/data` hooks, loading/error/empty states, D-71-09 de-list).

---

## File Classification

| Target File | New/Mod | Role | Data Flow | Closest Analog | Match |
|-------------|---------|------|-----------|----------------|-------|
| `apps/backend/app/modules/referrals/router.py` | EDIT | route | request-response (read) | same-file `client_get_referral_code` + `loyalty/router.py` | exact |
| `apps/backend/app/modules/referrals/service.py` | EDIT | service | CRUD-read / transform | `loyalty/service.py` `_sum_balance` + `list_client_loyalty_history` + same-file `resolve_public_code` | exact |
| `apps/backend/app/modules/referrals/repository.py` | EDIT (maybe) | repository | read | same-file `get_code_by_client_id` | exact |
| `apps/backend/app/modules/referrals/schemas.py` | EDIT | model (schema) | — | same-file `ReferralCodeResponse` + `loyalty/schemas.py` `ClientLoyaltyHistoryItem` | exact |
| `apps/backend/app/api/v1/router.py` | NO EDIT | — | — | already mounts `referral_client_router` at `/client` | n/a |
| `apps/backend/.../migrations` | NO EDIT | — | — | reads only — no schema change (confirmed below) | n/a |
| `apps/backend/tests/integration/test_referral_summary.py` | NEW | test | — | `test_referral_code.py` + `test_referral_crediting.py` seed helpers | exact |
| `apps/client-pwa/src/lib/clientQueries.ts` | EDIT | hook | request-response | same-file `useClientLoyaltyBalance` / `useClientMessages` | exact |
| `apps/client-pwa/src/data/index.js` | EDIT | config (barrel) | — | same-file Phase-94 hook re-exports | exact |
| `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` | REWRITE | component (screen) | request-response (read) | `screens/ChatScreen.jsx` (Phase 94) | exact |
| `apps/client-pwa/eslint.config.js` | EDIT | config | — | ChatScreen Phase-94 de-list (3 spots) | exact |
| `apps/client-pwa/src/App.jsx` | EDIT | route | request-response | same-file `/login` public route + sheet structure | exact |
| `apps/client-pwa/src/screens/<Landing>.jsx` | NEW | component (screen) | request-response (read) | `OnboardingScreen.jsx` + ChatScreen scope recipe | role-match |
| `apps/client-pwa/src/screens/OnboardingScreen.jsx` | EDIT | component | request-response | same-file `handleFinish` mutateAsync flow | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/referrals/router.py` (route, read)

**Analog:** same-file `client_get_referral_code` (router.py:85-105) + `loyalty/router.py:37-54`.

Add a third `@client_router.get` handler. Copy the decorator + signature shape verbatim from
the existing `client_get_referral_code` — same `client_router`, same `require_client()` gate,
same `envelope()` wrap, same "no try/except" doctrine.

```python
@client_router.get(
    "/referral/summary",
    response_model=ResponseEnvelope[ReferralSummaryResponse],
    operation_id="client_get_referral_summary",  # camelCase op_id discretion (CONTEXT)
    summary="Aggregate referral summary for the authenticated client (REFER-06; IDOR-safe)",
)
async def client_get_referral_summary(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResponseEnvelope[ReferralSummaryResponse]:
    """code, shareUrl, accruedKopecks, invitees[] — one round-trip for the screen.
    D-20-IDOR: client_id from require_client() principal only. No try/except.
    """
    result = await service.get_referral_summary(session, client.id, settings)
    return envelope(result)
```

**Gotchas:**
- `settings` is needed because `shareUrl = {settings.pwa_base_url}/i/{code}` (router.py:134, schemas.py:22).
- Add `ReferralSummaryResponse` to the schemas import block (router.py:38-44).
- No new router instance — reuse `client_router` (already mounted at `/client`, router.py:134 of v1).

---

### `apps/backend/app/modules/referrals/service.py` (service, read + fold)

**Analog (fold):** `loyalty/service.py:487-502` `_sum_balance`.
**Analog (raw-SQL cross-module read):** `loyalty/service.py:316-374` `list_client_loyalty_history`
and same-file `referrals/service.py:244-273` (raw `text()` against `clients`, D-54-08).
**Analog (assemble response):** same-file `resolve_public_code` (service.py:217-273).

The summary is a read-only service function — **no flush, no commit** (mirror `resolve_public_code`).
It does three reads:

1. **code + shareUrl** — reuse the existing fast path: `repository.get_code_by_client_id`
   (service.py:132) then `f"{settings.pwa_base_url}/i/{existing.code}"`. The summary endpoint
   should mint-if-absent OR read-only-return-empty — recommend reusing
   `get_or_create_referral_code(session, client_id, settings)` so the screen always has a code
   to display (it already handles idempotency + commit).

2. **accruedKopecks** — copy the `_sum_balance` fold but FILTER to referral entries:

```python
# Analog: loyalty/service.py:487-502 _sum_balance — same COALESCE/SUM fold, add entry_type filter
row = (
    await session.execute(
        text(
            "SELECT COALESCE(SUM(amount_kopecks), 0) AS accrued "
            "FROM loyalty_ledger "
            "WHERE client_id = :cid AND entry_type = 'referral_accrual'"
        ),
        {"cid": str(client_id)},
    )
).mappings().one()
accrued_kopecks = int(row["accrued"])
```

3. **invitees[]** — one raw-SQL join across `referral_captures` → `clients` →
   `loyalty_ledger` (D-54-08: cross-module reads via `text()`, NEVER ORM-import `Client`).
   The accrual linkage is `loyalty_ledger.referral_capture_id` → `referral_captures.id`
   (confirmed in `loyalty/models.py:106-118`); `status='joined'` iff a
   `referral_accrual` row exists for the referrer side of that capture.

```python
# referral_captures are this client's referees (referrer_client_id = me).
# joinedAt = referral_captures.created_at (CONTEXT decision).
# status = joined when a referral_accrual ledger row exists for this referrer+capture.
# bonusKopecks = that accrual row's amount (0 while pending).
# PII-minimal: first_name only; NO last_name, NO referee client_id (T-96-06 discipline).
rows = (
    await session.execute(
        text(
            "SELECT c.first_name AS first_name, "
            "       rc.created_at AS joined_at, "
            "       COALESCE(ll.amount_kopecks, 0) AS bonus_kopecks, "
            "       (ll.id IS NOT NULL) AS joined "
            "FROM referral_captures rc "
            "JOIN clients c ON c.id = rc.referee_client_id AND c.deleted_at IS NULL "
            "LEFT JOIN loyalty_ledger ll "
            "  ON ll.referral_capture_id = rc.id "
            "  AND ll.client_id = :cid "
            "  AND ll.entry_type = 'referral_accrual' "
            "WHERE rc.referrer_client_id = :cid "
            "ORDER BY rc.created_at DESC"
        ),
        {"cid": str(client_id)},
    )
).mappings().all()
invitees = [
    ReferralInviteeItem(
        first_name=r["first_name"],
        joined_at=r["joined_at"],
        status="joined" if r["joined"] else "pending",
        bonus_kopecks=int(r["bonus_kopecks"]),
    )
    for r in rows
]
```

**Gotchas:**
- `WHERE deleted_at IS NULL` on the clients join (WR-02 discipline, service.py:251/313).
- Bind UUIDs as `str(client_id)` in `text()` params — same as every other raw read here.
- The accrual row's `client_id` for the *referrer's* bonus is the referrer (= `client_id` here),
  so the `ll.client_id = :cid` filter on the LEFT JOIN gives the referrer-side bonus, matching
  the `accruedKopecks` SUM. Confirm against `loyalty/models.py` accrual semantics (Phase 97).
- Read-only: do NOT `commit()` for the fold/join; only `get_or_create_referral_code` commits
  (and only on first mint).

---

### `apps/backend/app/modules/referrals/schemas.py` (schema)

**Analog:** same-file `ReferralCodeResponse` (schemas.py:17-27) for the camelCase `ResponseData`
pattern; `loyalty/schemas.py:28-41` `ClientLoyaltyHistoryItem` for the item shape with
`datetime`/`int` fields and `# wire:` comments.

```python
class ReferralInviteeItem(ResponseData):
    """One invited friend. Wire: {firstName, joinedAt, status, bonusKopecks}.
    PII-minimal: first name only (T-96-06); NO last name, NO referee client_id."""
    first_name: str          # wire: firstName
    joined_at: datetime      # wire: joinedAt (referral_captures.created_at, ISO-8601 TZ)
    status: Literal["joined", "pending"]  # wire: status
    bonus_kopecks: int       # wire: bonusKopecks (referrer bonus; 0 while pending)


class ReferralSummaryResponse(ResponseData):
    """GET /client/referral/summary payload (REFER-06).
    Wire: {code, shareUrl, accruedKopecks, invitees: [...]}"""
    code: str                # wire: code
    share_url: str           # wire: shareUrl
    accrued_kopecks: int     # wire: accruedKopecks (SUM of own referral_accrual rows)
    invitees: list[ReferralInviteeItem]  # wire: invitees
```

**Gotchas:** add `from datetime import datetime` and `from typing import Literal` to the import
block (schemas.py:10-14 currently imports only `Field`). `ResponseData` provides the
`alias_generator=to_camel` so snake_case attrs serialize camelCase on the wire automatically.

---

### `apps/backend/app/modules/referrals/repository.py` (repository — OPTIONAL)

**Analog:** same-file `get_code_by_client_id` (repository.py:21-28).

Per CONTEXT "Claude's Discretion", the summary join can live inline in `service.py` as raw SQL
(recommended — it's a cross-module read, repository.py is the ORM-only single-access point and
holds no `text()` queries today). **Recommendation: do NOT add a repository method**; keep the
raw-SQL fold/join in `service.py` next to `resolve_public_code`, consistent with how
`_generate_unique_code` and the `clients` reads already live in the service layer.

---

### NO MIGRATION REQUIRED (confirmed)

The summary endpoint is **read-only**. It reads three existing tables built in Phases 96/97:
`referral_codes`, `referral_captures` (both Phase 96, migration 0067), and `loyalty_ledger`
with the `referral_accrual` entry_type + `referral_capture_id` column (Phase 97, migration 0069).
No new columns, indexes, or tables. **Do not author a migration.**

---

### `apps/backend/tests/integration/test_referral_summary.py` (NEW test)

**Analog (harness + auth):** `test_referral_code.py` (whole file) — copy verbatim:
- `_overridden_app` fixture (lines 48-63): overrides `get_db` to the SAVEPOINT session + `get_redis`.
- `http_client` ASGITransport fixture (lines 66-71) — no real network (CLAUDE.md mandate).
- `stub_otp_sender` + `flush_redis` autouse fixtures (lines 74-89).
- `_seed_staff` / `_seed_client` / `_auth_as_client` helpers (lines 97-157) — OTP login flow.

**Analog (seeding accrual rows + captures):** `test_referral_crediting.py` helpers
`_seed_referral_code` (line 254), `_seed_referral_capture` (line 269), `_ensure_referral_config`
(line 289, raw INSERT into `referral_config`), `_count_referral_accrual_rows` (line 396). Reuse
these to set up joined/pending invitees and the accrued SUM.

**Cases to prove:**
- Empty: client with a code but zero captures → `invitees == []`, `accruedKopecks == 0`.
- Pending invitee: capture exists, no accrual row → `status: "pending"`, `bonusKopecks: 0`.
- Joined invitee: capture + `referral_accrual` row → `status: "joined"`, `bonusKopecks > 0`,
  and `accruedKopecks` reflects the SUM.
- `firstName` present, NO `lastName`/referee-id keys in the JSON (PII assertion).
- `shareUrl` ends `/i/<code>`.
- No-auth → 401 (mirror `test_get_referral_code_no_auth_returns_401`, line 279).
- IDOR: client B's summary never includes client A's invitees.

```python
resp = await http_client.get("/api/v1/client/referral/summary")
assert resp.status_code == 200, resp.text
data = resp.json()["data"]
assert data["shareUrl"].endswith(f"/i/{data['code']}")
assert isinstance(data["invitees"], list)
# PII guard
for inv in data["invitees"]:
    assert set(inv.keys()) == {"firstName", "joinedAt", "status", "bonusKopecks"}
```

---

### `apps/client-pwa/src/lib/clientQueries.ts` (hook, request-response)

**Analog:** `useClientLoyaltyBalance` (clientQueries.ts:798-808) — the exact shape to copy:
key-factory entry, typed interface, `useQuery` with `staleTime: 30_000`, `clientRequest('get', ...)`,
`(res as { data: T }).data` unwrap.

1. Add a key-factory entry (clientQueries.ts:23-47 block):
```typescript
referralSummary: () => [...clientPortalKeys.all, 'referral', 'summary'] as const,
```
2. Add the interface + hook (mirror the loyalty interfaces at lines 787-808):
```typescript
interface ReferralInviteeItem {
  firstName: string
  joinedAt: string
  status: 'joined' | 'pending'
  bonusKopecks: number
}
interface ReferralSummaryData {
  code: string
  shareUrl: string
  accruedKopecks: number
  invitees: ReferralInviteeItem[]
}

/** GET /api/v1/client/referral/summary — aggregate referral screen data (REFER-06) */
export function useClientReferralSummary() {
  return useQuery({
    queryKey: clientPortalKeys.referralSummary(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/referral/summary')
      return (res as { data: ReferralSummaryData }).data
    },
    staleTime: 30_000,
  })
}
```

**Gotchas:**
- `/client/referral/*` paths are NOT yet in the generated `schema.d.ts` (Phase 99 handoff). If
  the typed `clientRequest` generic rejects the path, use the SAME cast escape hatch as
  `useClientMessages` (clientQueries.ts:969-975): `clientRequest as unknown as (...) => Promise<unknown>`.
- Read-only — no `onSettled` invalidation needed (per CONTEXT: default cache behavior).

---

### `apps/client-pwa/src/data/index.js` (barrel, swap seam)

**Analog:** the Phase-94 messaging-hook re-export block (data/index.js:67-72).

Add to the `export { ... } from '../lib/clientQueries'` block:
```javascript
  // Phase-98 REFER-06: referral summary hook
  useClientReferralSummary,
```
Also update the top comment (data/index.js:3-6): ReferralSheet is GRADUATING — move it from the
"must NOT import" list to the graduated list alongside GymInfoSheet/NotificationsSheet/ChatScreen.

---

### `apps/client-pwa/src/screens/sheets/ReferralSheet.jsx` (component, REWRITE)

**Analog:** `screens/ChatScreen.jsx` (Phase 94) — the complete port template. The current file
is an 11-line `ComingSoon` placeholder (ReferralSheet.jsx:1-10); replace it entirely.

**The ChatScreen recipe, concretely:**

1. **CSS-as-module-const scoped to `.referral-root`** (ChatScreen.jsx:31-97):
   - `const CSS = \`...\`` holds the verbatim reference CSS with selectors rewritten.
   - `:root {` → `.referral-root {` and append `position: absolute; inset: 0;` to fill the
     SheetGate inset (ChatScreen.jsx:33,63).
   - `body.dark {` → `.referral-root.dark {` (ChatScreen.jsx:72).
   - `* { box-sizing }` → `.referral-root * { box-sizing }` (ChatScreen.jsx:97).
   - prefix every component class (`.card`, `.rwd`, `.code-box`, `.share-chip`, `.step`,
     `.fr-row`, `.btn`, `.toast`, `.t-mini`…) with `.referral-root ` (ChatScreen.jsx:98-106).
   - STRIP device chrome: `.device`/`.island`/`.status-bar`/`.home-indicator`/`.stage` — do not
     transcribe those rules at all.
   The reference source is `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx` (1041 lines;
   its CSS head at lines 13-70 is the `:root`/`body.dark` block to re-scope).

2. **Theme via the existing PWA mechanism** (ChatScreen.jsx:648-663) — copy verbatim:
   ```javascript
   const [isDark, setIsDark] = useState(
     () => (tweaks?.theme === 'dark') || document.documentElement.getAttribute('data-theme') === 'dark',
   );
   useEffect(() => { /* MutationObserver on data-theme */ }, [tweaks?.theme]);
   ```
   Do NOT use the reference's `myzal_theme` localStorage + `document.body.classList` sync.

3. **Root element** (ChatScreen.jsx:1344-1346):
   ```jsx
   return (
     <div className={'referral-root' + (isDark ? ' dark' : '')}>
       <style>{CSS}</style>
       ...
   ```

4. **Data wiring** (ChatScreen.jsx:638-646):
   ```javascript
   const summaryQuery = useClientReferralSummary();
   const isLoading = summaryQuery.isLoading;
   const isError = summaryQuery.isError && !summaryQuery.isFetching;
   const data = summaryQuery.data;
   ```
   Import from `@/data` (ChatScreen.jsx:22-27 import style).

5. **Loading / error / empty states** (ChatScreen.jsx:1389-1412 — the exact 3-branch pattern):
   - `isLoading` → skeletons in place of code-box / accrued figure / friends list.
   - `isError` (and not fetching) → inline error block ("Не удалось загрузить. Потяните вниз…").
   - `invitees.length === 0` → empty-state row ("Пока никого" / "Поделитесь промокодом — …").
   - populated → map `.fr-row` per invitee.
   (UI-SPEC §"Data States" is the authoritative copy; this is the structural pattern.)

6. **Money + date formatting** — use the project helpers, NOT raw math:
   - `import { formatMoney } from '@/utils/format.js'` (LoyaltySheet.jsx:21) for `bonusKopecks`
     and the "Уже накоплено" `accruedKopecks` figure.
   - `Intl.DateTimeFormat('ru-RU', { ..., timeZone: 'Europe/Moscow' })` for `joinedAt`
     (copy the `formatBonusDate` helper from LoyaltySheet.jsx:26-39).

7. **Hide-for-future** (ChatScreen.jsx:1340-1341 `showQuick = false`): keep the gamification
   tier tracker (`.milestones`) in the DOM behind `hidden`/`display:none` — NOT deleted
   (UI-SPEC §"Hidden-for-future").

8. **Props:** the sheet receives `onClose` + `userName` (App.jsx:347). The topbar back button and
   footer CTA call `onClose` / `navigator.share`, not `data-go`.

**Gotchas:**
- Share text MUST embed the server `shareUrl` from the summary response, never a client-built URL
  (CONTEXT + UI-SPEC §"Share / Copy Interaction Contract").
- `@/data` exports ONLY the hook (no mock constants) — this is a wired screen now.
- The `<style>` per-mount is acceptable (matches ChatScreen); singleton hoist is a deferred nit.

---

### `apps/client-pwa/eslint.config.js` (config, D-71-09 de-list — 3 spots)

**Analog:** Phase-94 ChatScreen de-list, regression-guarded by `ChatScreen.delist.test.ts`
(asserts grep-returns-0). The structural precedent is visible in the config's own comments
(eslint.config.js:25-28 documents how ChatScreen graduated).

**EXACT lines to change:**

1. **Remove the negated ignore — line 31:**
   ```javascript
       '!src/screens/sheets/ReferralSheet.jsx',
   ```
   Delete this single line from the `ignores` array (eslint.config.js:14-32). After removal the
   `src/**/*.jsx` glob (line 29) ignores ReferralSheet like every other real `.jsx` screen.

2. **Delete the entire dedicated `no-restricted-paths` block — lines 71-109.** This is the
   `{ files: ['src/screens/sheets/ReferralSheet.jsx'], ... rules: { 'import/no-restricted-paths': [...] } }`
   object (eslint.config.js:71-109) plus its leading comment block (lines 63-70). Removing it
   means there is no longer a zone forbidding ReferralSheet from importing the query layer.

3. **Update comments** (lines 13, 19-21, 63-70): the comments speak of "the net-new placeholder
   screens" / "The remaining net-new placeholder screen" — since ReferralSheet was the LAST one
   in the zone, after removal the whole D-71-09 mechanism is empty. Either delete the now-stale
   comments or note that all net-new screens have graduated.

**Gotcha:** after the edit `grep ReferralSheet eslint.config.js` MUST return 0 (CONTEXT acceptance
criterion). Add/adapt a graduation guard test mirroring `ChatScreen.delist.test.ts:17-26`
(`ReferralSheet.delist.test.ts`): assert `eslintConfig.split('ReferralSheet').length - 1 === 0`.
Note: the existing `ChatScreen.delist.test.ts:23-25` asserts the config STILL contains
'ReferralSheet' — that assertion will now fail and must be removed/updated as part of this phase.

---

### `apps/client-pwa/src/App.jsx` (route — public `/i/:code`)

**Analog:** the `/login` public route (App.jsx:286) and the lazy-screen import pattern
(App.jsx:28-35). Public routes sit OUTSIDE `<RequireAuth>` (App.jsx:285-287).

1. Lazy-import the new landing screen (mirror App.jsx:28-30):
   ```javascript
   const ReferralLandingScreen = lazy(() =>
     import('@/screens/ReferralLandingScreen.jsx').then(m => ({ default: m.ReferralLandingScreen }))
   );
   ```
2. Add the public route inside `<Routes>` next to `/login` (App.jsx:285-287):
   ```jsx
   <Route path="/i/:code" element={<ReferralLandingScreen />} />
   ```
3. Add `/i/` to the tab-bar-hidden conditions (App.jsx:269-275) so the landing is chrome-free,
   the same way `isLoginRoute` / `isOnboardingRoute` are handled.

**Gotchas:**
- Use `react-router-dom` `useParams()` for `:code` (App.jsx already imports from `react-router-dom`).
- The landing is for UNAUTHENTICATED visitors (the invited friend) — keep it outside RequireAuth.

---

### `apps/client-pwa/src/screens/ReferralLandingScreen.jsx` (NEW component, read)

**Analog:** `OnboardingScreen.jsx` (chrome-stripped full-screen `position:absolute;inset:0`
layout, `var(--token)` colors, CTA button pattern) + the ChatScreen scope recipe if it reuses
the referral palette.

Behavior (UI-SPEC §"Deep-Link Landing"):
1. Read `:code` via `useParams()`; resolve via public `GET /i/<code>` (the backend
   `public_resolve_referral_code` already exists, router.py:53-75 → `{valid, referrerFirstName,
   welcomeBonusKopecks}`).
2. On valid → heading "{referrerFirstName} зовёт вас в «Sportzal»", store code in
   `sessionStorage['clubcore:pendingReferral']`, CTA → `/login` (or `/onboarding`).
3. On `valid:false` → neutral "Добро пожаловать в «Sportzal»" + generic CTA, NO pending code.

**Gotchas:**
- The resolver call is unauthenticated. `clientRequest` sends `credentials: 'include'`
  (clientFetcher.ts:51) and `/i/{code}` is public on the backend — a no-cookie call is fine.
  Add a `useClientReferralResolve(code)` hook in clientQueries.ts mirroring the loyalty read hook,
  OR call `fetch`/`clientRequest` directly in the landing screen (discretion — it's a one-shot read).
  Prefer a hook for consistency.
- Brand string is `«Sportzal»` (D-62-02), NOT the reference's "Мой зал".
- sessionStorage key name is discretion; CONTEXT suggests `clubcore:pendingReferral`.

---

### `apps/client-pwa/src/screens/OnboardingScreen.jsx` (EDIT — capture post-auth)

**Analog:** same-file `handleFinish` / `handleSkip` mutateAsync flow (OnboardingScreen.jsx:291-320).

After successful onboarding completion (inside the success branch of `handleFinish`, before/after
`setDone(true)` at line 301, and in `handleSkip` after line 315), read the pending code from
sessionStorage and fire the capture:
```javascript
const pending = sessionStorage.getItem('clubcore:pendingReferral')
if (pending) {
  try {
    await captureReferral.mutateAsync({ code: pending })  // POST /client/referral/capture
  } catch (_e) { /* idempotent no-op server-side; never block onboarding */ }
  sessionStorage.removeItem('clubcore:pendingReferral')
}
```

**Pattern for the capture mutation hook** (add to clientQueries.ts; analog `useOtpVerify`
clientQueries.ts:318-323 — a fire-and-forget POST mutation):
```typescript
export function useCaptureReferral() {
  return useMutation({
    mutationFn: async ({ code }: { code: string }) => {
      await clientRequest('post', '/api/v1/client/referral/capture', { body: { code } })
    },
  })
}
```

**Gotchas:**
- Capture is best-effort: the backend handles self-referral / already-bound as idempotent no-ops
  (service.py:276-366). A failure here must NEVER block the onboarding navigation (swallow with
  `_e` + noop, matching the project's defensive-catch convention).
- Capture MUST happen post-auth (the client is authenticated inside OnboardingScreen under
  RequireAuth — App.jsx:303), so `client_id` comes from the principal (IDOR-safe).
- `useCaptureReferral` must be re-exported through `@/data` (data/index.js).

---

## Shared Patterns

### Cross-module raw-SQL read (D-54-08)
**Source:** `loyalty/service.py:487-502` (`_sum_balance`), `referrals/service.py:244-273`.
**Apply to:** the summary service function — reads of `clients` and `loyalty_ledger` from the
referrals module MUST use `text()`, never an ORM import of `Client`/`LoyaltyLedger`. import-linter
forbids module↔module ORM imports. Bind UUIDs as `str(...)`. Filter `deleted_at IS NULL` on clients.

### IDOR-safe client reads (D-20-IDOR)
**Source:** `loyalty/router.py:43-54`, `referrals/router.py:91-105`.
**Apply to:** the summary endpoint — `client_id` from `require_client()` principal only, never a
URL/body param. No-auth → 401. A client never sees another client's invitees.

### camelCase wire envelope
**Source:** `referrals/schemas.py` + `loyalty/schemas.py` (`ResponseData` + `ResponseEnvelope`/`envelope`).
**Apply to:** new response schemas — snake_case Python attrs auto-serialize camelCase; wrap handler
returns in `envelope(...)`; declare `response_model=ResponseEnvelope[...]`.

### ChatScreen graduation recipe (Phase 94)
**Source:** `screens/ChatScreen.jsx` + `eslint.config.js` de-list + `ChatScreen.delist.test.ts`.
**Apply to:** ReferralSheet rewrite + eslint.config.js edit — CSS scoped to `.referral-root`,
chrome stripped, `@/data` hooks, 3-branch loading/error/empty states, D-71-09 de-list (3 spots),
grep-returns-0 guard test.

### PWA money + date formatting
**Source:** `@/utils/format.js` `formatMoney` (LoyaltySheet.jsx:21) + `Intl.DateTimeFormat`
ru-RU / Europe/Moscow (LoyaltySheet.jsx:26-39).
**Apply to:** ReferralSheet invitee `bonusKopecks`, accrued figure, and `joinedAt` rendering.

### Integration-test harness (ASGITransport + OTP auth)
**Source:** `test_referral_code.py` fixtures (lines 48-157) + `test_referral_crediting.py` seed
helpers (lines 254-396).
**Apply to:** `test_referral_summary.py` — copy the fixture block verbatim, reuse the capture +
accrual seeders. No real network (CLAUDE.md).

---

## No Analog Found

None. Every target file maps onto a strong in-repo analog (the loyalty read endpoints, the Phase-96
referral domain, and the Phase-94 ChatScreen port recipe cover all cases).

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/{referrals,loyalty,gym}`, `apps/backend/app/api/v1`,
`apps/backend/tests/integration`, `apps/client-pwa/src/{lib,data,screens,screens/sheets}`,
`apps/client-pwa/eslint.config.js`, `.planning/refs/v2.6-REFERENCE-ReferFriendScreen.jsx`.
**Files scanned:** ~22 (10 deep reads + targeted greps).
**Pattern extraction date:** 2026-06-08
