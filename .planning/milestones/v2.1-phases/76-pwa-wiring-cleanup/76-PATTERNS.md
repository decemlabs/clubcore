# Phase 76: PWA Wiring + Cleanup — Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 4 (1 new hook, 2 modified screens/sheets, 1 cleanup)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/client-pwa/src/lib/clientQueries.ts` | hook/query | request-response | Same file: `useClientPlans()` lines 307-317 | exact |
| `apps/client-pwa/src/screens/HomeScreen.jsx` | screen component | request-response | Same file: existing `useClientHome()` + `useClientMe()` consumption lines 220-223 | exact |
| `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` | sheet component | request-response (read+mutate) | `src/screens/sheets/CheckoutSheet.jsx` (mutation + toast + `useClientMe` read) | role-match |
| `apps/client-pwa/src/App.jsx` | app shell | cleanup (import removal) | Self — targeted line removal, no new pattern needed | exact |

---

## Pattern Assignments

### 1. `apps/client-pwa/src/lib/clientQueries.ts` — ADD `useClientTrainers()`

**Change:** Add one new read hook and one new `clientPortalKeys` key entry.

**Analog:** `useClientPlans()` in the same file, lines 307-317, and `clientPortalKeys.plans` entry at line 28.

**Key factory entry to add** (mirror line 28):
```typescript
trainers: () => [...clientPortalKeys.all, 'trainers'] as const,
```
Insert after `plans: () => ...` in the `clientPortalKeys` object (lines 23-38).

**Hook to add** (mirror lines 307-317 exactly — only path and key name change):
```typescript
/** GET /api/v1/client/trainers — trainer catalog for newbie Home avatar strip (D-76-01) */
export function useClientTrainers() {
  return useQuery({
    queryKey: clientPortalKeys.trainers(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/trainers')
      return (res as { data: unknown[] }).data
    },
    staleTime: 30_000,
  })
}
```
Insert after `useClientPlans()` (after line 317).

**Transport pattern** (lines 11-13 — already present, no change):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@clubcore/api-client'
import { clientRequest } from './clientFetcher'
```

**No type interface needed** — backend returns `{ id, full_name }` per trainer; keep `unknown[]` cast (same as `useClientPlans` and `useClientPtPackages` at lines 308-329) and let the consumer narrow it at the call site.

---

### 2. `apps/client-pwa/src/screens/HomeScreen.jsx` — Wire Trainer Strip + Plan Chip

**Two sub-changes in this file:**

#### 2a. NHOME-01 — Trainer avatar strip (lines 954-983)

**Analog:** The existing avatar strip code at lines 954-983 IS the pattern — replace `TRAINERS` source with `useClientTrainers()` data.

**Import change** (line 11 — add `useClientTrainers`, remove `TRAINERS`):
```jsx
// BEFORE:
import { useClientHome, useClientMe, useClientBookings, TRAINERS } from '@/data';
// AFTER:
import { useClientHome, useClientMe, useClientBookings, useClientTrainers } from '@/data';
```
Note: `TRAINERS` must also be added to `@/data` re-exports (add to `data/index.js` export list from `clientQueries`).

**Hook call** — add inside `HomeNewbie` component (which renders inside the `HomeScreen` at line 292):

The `HomeNewbie` function is defined separately in the file. Add the hook call at the top of `HomeNewbie`:
```jsx
function HomeNewbie({ me, homeData, bookings, userName, isDark, onOpenPlans, onOpenGymInfo, onOpenNotifications, onTab, onOpenOnboarding }) {
  // ... existing state ...
  const { data: liveTrainers, isLoading: trainersLoading } = useClientTrainers()
```

**Avatar strip render pattern** — replace lines 956-983. Error/empty fallback uses static `TRAINERS` from `'@/data/trainers.js'` (direct import, not from `@/data` swap seam per D-76-05):
```jsx
{/* Avatar stack — live data from useClientTrainers() (D-76-01) */}
<div style={{ display: 'flex', alignItems: 'center' }} aria-hidden="true">
  {trainersLoading ? (
    // Skeleton: 3 grey circles (D-76-04 — no pulse, match skeletons.jsx style)
    [0, 1, 2].map((i) => (
      <span key={i} style={{
        width: 34, height: 34, borderRadius: '50%',
        border: '2.5px solid var(--surface)',
        marginLeft: i === 0 ? 0 : -11,
        background: 'var(--surface-2)', flexShrink: 0,
      }} />
    ))
  ) : (() => {
    // On error or empty list — fall back to static TRAINERS placeholder (D-76-04)
    const display = (liveTrainers && liveTrainers.length > 0) ? liveTrainers : STATIC_TRAINERS_FALLBACK
    const count = (liveTrainers && liveTrainers.length > 0) ? liveTrainers.length : display.length
    return (
      <>
        {display.slice(0, 3).map((tr, i) => (
          <span key={tr.id ?? i} style={{
            width: 34, height: 34, borderRadius: '50%',
            border: '2.5px solid var(--surface)',
            marginLeft: i === 0 ? 0 : -11,
            background: i === 0
              ? 'var(--accent)'
              : i === 1 ? 'color-mix(in oklab, var(--accent) 60%, #6ee7c4)' : 'var(--accent-deep)',
            color: i === 2 ? '#ffffff' : 'var(--on-accent)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 12, fontWeight: 700, flexShrink: 0,
          }}>
            {[...(tr.full_name ?? tr.name ?? '').trim()][0]}
          </span>
        ))}
        {count > 3 && (
          <span style={{
            width: 34, height: 34, borderRadius: '50%',
            border: '2.5px solid var(--surface)', marginLeft: -11,
            background: 'var(--surface-2)', color: 'var(--text-2)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, flexShrink: 0,
          }}>
            +{count - 3}
          </span>
        )}
      </>
    )
  })()}
</div>
```

**Fallback import** — add at top of file for static fallback (D-76-04 / D-76-05):
```jsx
import { TRAINERS as STATIC_TRAINERS_FALLBACK } from '@/data/trainers.js'
```
This is a direct module import, NOT through the `@/data` swap seam (per D-76-05 — the static file stays for TrainersTab/chat).

#### 2b. NHOME-02 — Plan info chip (inside `HeroNewbie` function)

**Analog:** `useClientPlans()` already imported in the codebase; `formatMoney` imported in `ProfileScreen.jsx` line 7 as `import { formatMoney } from '@/utils/format.js'`.

**Import to add** to HomeScreen.jsx:
```jsx
import { formatMoney } from '@/utils/format.js'
```

**Hook call** inside `HeroNewbie` (add alongside `useClientTrainers` call above):
```jsx
const { data: plans } = useClientPlans()
```
`useClientPlans` is already exported from `@/data` — import it alongside the other hooks.

**Plan chip render** — insert after the tariff selector `<div>` block (after line ~526, before the CTA button at line 529). The chip uses the existing `.chip` CSS class:

```jsx
{/* Plan info chip — live count + min monthly price (NHOME-02 / D-76-06..09) */}
{plans && plans.length > 0 ? (
  <div style={{ marginTop: 10, display: 'flex', justifyContent: 'center' }}>
    <span className="chip">
      {plans.length} {pluralPlan(plans.length)} · от {formatMoney(
        Math.min(...plans.map(p => Math.round(p.price_kopecks / (p.duration_days / 30))))
      )}/мес
    </span>
  </div>
) : null /* loading / error: fallback = nothing (existing hardcoded layout already shows) */}
```

**`pluralPlan` helper** — add as a module-level function in HomeScreen.jsx (or in `src/utils/format.js` as a named export — pick one; inline in the screen file is simpler given single usage):
```js
function pluralPlan(n) {
  const abs = Math.abs(n) % 100
  const mod10 = abs % 10
  if (abs >= 11 && abs <= 14) return 'тарифов'
  if (mod10 === 1) return 'тариф'
  if (mod10 >= 2 && mod10 <= 4) return 'тарифа'
  return 'тарифов'
}
```

**`useClientPlans` hook call location:** `HeroNewbie` is a named export function starting at line 329. Add `const { data: plans } = useClientPlans()` near the top of that function alongside the existing `const [sel, setSel] = React.useState(1)`.

---

### 3. `apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx` — Wire Personal Data Sheet

**Analog:** `CheckoutSheet.jsx` — mutation call pattern (`mutateAsync` / `isPending` / try-catch / in-sheet toast). For read pattern: `HomeScreen.jsx` lines 220-221 (`useClientMe` + `useClientHome`).

**Imports to add** (top of ProfileExtraSheets.jsx — mirror CheckoutSheet import style):
```jsx
import { useClientMe, useUpdateClientProfile } from '@/data'
```

**State replacement** — replace lines 40-47 (hardcoded useState initializers) with API-driven initialization:
```jsx
export const PersonalDataSheet = ({ onClose, userName, setTweak }) => {
  const { data: meData } = useClientMe()
  const updateProfile = useUpdateClientProfile()

  // Editable local state — initialized from API data via useEffect
  const [name, setName] = React.useState('')
  const [email, setEmail] = React.useState('')
  const [goal, setGoal] = React.useState('')
  const [heightCm, setHeightCm] = React.useState('')
  const [weightKg, setWeightKg] = React.useState('')

  // Local-only (no backend field) — D-76-11
  const [dob, setDob] = React.useState('14.03.1996')
  const [gender, setGender] = React.useState('f')

  // Hydrate from API on first load (D-76-10)
  React.useEffect(() => {
    if (!meData) return
    setName(meData.firstName ?? '')
    setEmail(meData.email ?? '')
    setGoal(meData.goal ?? '')
    setHeightCm(meData.heightCm != null ? String(meData.heightCm) : '')
    setWeightKg(meData.weightKg != null ? String(meData.weightKg) : '')
  }, [meData])

  // Phone: read-only from API; ref holds initial value for SMS-verify guard
  const phone = meData?.phone ?? ''
  const initialPhone = React.useRef(phone)
  React.useEffect(() => { if (phone) initialPhone.current = phone }, [phone])

  const [saved, setSaved] = React.useState(false)
  const [saveError, setSaveError] = React.useState(false)
```

**Save handler** — replace the existing `onSave` (lines 49-62) with mutation call:
```jsx
  const onSave = async () => {
    // Phone changes still delegate to SMS verify (unchanged from original)
    if (phone !== initialPhone.current) {
      window.__openSmsVerify?.('phone', phone)
      return
    }
    setSaveError(false)
    try {
      await updateProfile.mutateAsync({
        firstName: name,
        email: email || undefined,
        goal: goal || undefined,
        heightCm: heightCm ? Number(heightCm) : undefined,
        weightKg: weightKg ? Number(weightKg) : undefined,
      })
      if (setTweak) setTweak('userName', name)
      setSaved(true)
      setTimeout(() => setSaved(false), 1400)
    } catch {
      setSaveError(true)
      // Error toast — inline pattern (no external toast library in PWA)
      window.__showToast?.('Не удалось сохранить данные. Попробуйте ещё раз.')
    }
  }
  const isSaving = updateProfile.isPending
```

**Save button states** (mirror existing `saved` pattern at lines 72-77, add `isSaving`):
```jsx
<button onClick={onSave} disabled={isSaving} style={{
  border: 0, background: 'transparent',
  color: saved ? 'var(--accent-deep)' : isSaving ? 'var(--text-3)' : 'var(--text)',
  fontSize: 13, fontWeight: 600, padding: '6px 10px',
  cursor: isSaving ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
}}>
  {saved ? 'Сохранено' : isSaving ? 'Сохранение…' : 'Сохранить'}
</button>
```

**Height/weight FormRow changes** (lines 135-138 — change from read-only to editable):
```jsx
// BEFORE (read-only display):
<FormRow label="Рост" value="168 см" onChange={() => {}} />
<Divider3 />
<FormRow label="Вес" value="58 кг" onChange={() => {}} />

// AFTER (editable numeric inputs, D-76-12):
<FormRow label="Рост" value={heightCm} onChange={setHeightCm} type="number" placeholder="см" />
<Divider3 />
<FormRow label="Вес" value={weightKg} onChange={setWeightKg} type="number" placeholder="кг" />
```

**Goal field** (line 139 — was read-only, now editable):
```jsx
// BEFORE:
<FormRow label="Цель" value="Поддержание формы" onChange={() => {}} />
// AFTER:
<FormRow label="Цель" value={goal} onChange={setGoal} />
```

**Name/email fields** (lines 107-111 — swap hardcoded values to state):
```jsx
<FormRow label="Имя" value={name} onChange={setName} />
<Divider3 />
<FormRow label="Телефон" value={phone} onChange={() => {}} type="tel" />
<Divider3 />
<FormRow label="Email" value={email} onChange={setEmail} type="email" />
```

**Local-only indicator** (lines 115-130 — add `[местные данные]` label to DOB/Gender group):
```jsx
<div style={{ padding: '0 16px 12px' }}>
  <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px 8px' }}>
    <div className="t-mini" style={{ color: 'var(--text-3)' }}>О себе</div>
    <div className="t-mini" style={{ color: 'var(--text-3)', marginLeft: 'auto' }}>
      Только на устройстве
    </div>
  </div>
  <div className="card" style={{ padding: 0 }}>
    {/* DOB and Gender rows unchanged */}
  </div>
</div>
```

**Toast surface:** The PWA has no global Sonner — `CheckoutSheet` uses a local `setToast` state + CSS `.co-toast` class. For ProfileExtraSheets, the simplest approach is a similar local toast `div`, or fall back to `window.__showToast` if one is wired, or a `window.alert` as last resort. Inspect `src/components/` for a toast primitive before choosing (see Shared Patterns section below).

---

### 4. `apps/client-pwa/src/App.jsx` — Remove CONVERSATIONS import + unreadChat

**Change:** Surgical removal of 2 lines + 1 prop value change.

**Confirmed current state** (lines 17 and 223):
- Line 17: `import { CONVERSATIONS, TRAINERS } from '@/data';`
- Line 223: `const unreadChat = CONVERSATIONS.reduce((s, c) => s + (c.unread || 0), 0);`
- Line 457: `<TabBar active={tab} onChange={handleTab} unreadChat={unreadChat} />`

**D-76-16 verification result:** `CONVERSATIONS` is imported ONLY in `App.jsx` among screen/component files. The `data/index.js` re-exports it from `data/conversations.js`. The `ChatScreen.jsx` does NOT import `CONVERSATIONS` directly. Therefore `data/conversations.js` and its re-export in `data/index.js` line 50 are orphaned once App.jsx is cleaned — **delete both** (the file and the export line).

**Target state**:
```jsx
// Line 17 — BEFORE:
import { CONVERSATIONS, TRAINERS } from '@/data';
// Line 17 — AFTER (TRAINERS still needed for... check: TRAINERS not used in App.jsx itself):
```

Check: `TRAINERS` at line 17 of `App.jsx` — grep confirms it is NOT used anywhere else in `App.jsx` (only `CONVERSATIONS` is used at line 223 and indirectly in TabBar). However `TRAINERS` is imported from `@/data` in `HomeScreen.jsx` line 11 (but that's a separate file). In `App.jsx` itself, `TRAINERS` appears only in the import line and is NOT referenced in the file body — so **both** `CONVERSATIONS` and `TRAINERS` can be removed from App.jsx's import:

```jsx
// AFTER (entire import line removed — neither is used in App.jsx body):
// (delete line 17 entirely)
```

**Line 223 — remove entirely:**
```jsx
// DELETE: const unreadChat = CONVERSATIONS.reduce((s, c) => s + (c.unread || 0), 0);
```

**Lines 453-458 — change prop:**
```jsx
// BEFORE:
<TabBar
  active={tab}
  onChange={handleTab}
  unreadChat={unreadChat}
/>
// AFTER:
<TabBar
  active={tab}
  onChange={handleTab}
  unreadChat={0}
/>
```

---

## Shared Patterns

### Query hook shape (used by `useClientTrainers`)
**Source:** `apps/client-pwa/src/lib/clientQueries.ts` lines 307-317
```typescript
export function useClientPlans() {
  return useQuery({
    queryKey: clientPortalKeys.plans(),
    queryFn: async () => {
      const res = await clientRequest('get', '/api/v1/client/plans')
      return (res as { data: unknown[] }).data
    },
    staleTime: 30_000,
  })
}
```
Copy this shape exactly for `useClientTrainers` — only `queryKey`, `queryFn` path, and function name change.

### Mutation with isPending + invalidate (used by PersonalDataSheet save)
**Source:** `apps/client-pwa/src/lib/clientQueries.ts` lines 207-229
```typescript
export function useUpdateClientProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { firstName?; goal?; heightCm?; weightKg?; onboardingCompleted?; email? }) => {
      const res = await clientRequest('patch', '/api/v1/client/me', { body: payload })
      return (res as { data: ClientMeData }).data
    },
    onSuccess: (data) => {
      qc.setQueryData(clientPortalKeys.me(), data)   // seed cache immediately
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: clientPortalKeys.me() })
      void qc.invalidateQueries({ queryKey: clientPortalKeys.home() })
    },
  })
}
```
`updateProfile.isPending` is the in-flight guard. `mutateAsync` throws on error — wrap in try/catch.

### Money formatting (used by plan chip)
**Source:** `apps/client-pwa/src/utils/format.js` lines 8-15
```js
export function formatMoney(kopecks) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(kopecks / 100);
}
```
Import as: `import { formatMoney } from '@/utils/format.js'`
Usage pattern in ProfileScreen: `formatMoney(totalKopecks)` — pass integer kopecks, get `"1 500 ₽"`.

### In-screen error toast (used by PersonalDataSheet)
**Source:** `apps/client-pwa/src/screens/sheets/CheckoutSheet.jsx` lines 131-156
The PWA has no global Sonner. `CheckoutSheet` implements a local `toast` state + CSS class `.co-toast`. That class is CheckoutSheet-specific CSS. For `ProfileExtraSheets`, use the same local-state pattern:
```jsx
const [toastMsg, setToastMsg] = React.useState(null)
const toastTimer = React.useRef(null)
const showToast = (msg) => {
  if (toastTimer.current) clearTimeout(toastTimer.current)
  setToastMsg(msg)
  toastTimer.current = setTimeout(() => setToastMsg(null), 2600)
}
```
Then render a `<div>` at the bottom of the sheet body with inline styles matching the error token (`var(--danger)`). No `.co-toast` CSS class available — use inline styles.

### `@/data` swap seam export (applies when adding new hooks)
**Source:** `apps/client-pwa/src/data/index.js` lines 19-47
All new query hooks added to `clientQueries.ts` must also be added to the export list in `data/index.js`. Add `useClientTrainers` to the existing named export block:
```js
export {
  // ... existing exports ...
  useClientTrainers,   // ADD
} from '../lib/clientQueries'
```

---

## No Analog Found

None — all four files have strong analogs within the same codebase.

---

## D-76-16 Verification: `conversations.js` orphan status

**Confirmed orphaned after App.jsx cleanup.** The only consumers of `CONVERSATIONS` are:
1. `apps/client-pwa/src/App.jsx` line 17 (import) and line 223 (usage) — **being removed by CLEAN-01**
2. `apps/client-pwa/src/data/index.js` line 50 (re-export) — becomes dead code after #1 is removed
3. `apps/client-pwa/src/data/conversations.js` (the source file) — no other importer found

**Action for planner:** Plan to delete `apps/client-pwa/src/data/conversations.js` AND remove line 50 from `apps/client-pwa/src/data/index.js` (the `export { CONVERSATIONS }` line and its comment at line 7).

---

## Metadata

**Analog search scope:** `apps/client-pwa/src/` — lib, screens, screens/sheets, data, utils
**Files read:** `clientQueries.ts`, `App.jsx`, `ProfileExtraSheets.jsx`, `HomeScreen.jsx` (sections), `CheckoutSheet.jsx` (section), `format.js`, `data/index.js`
**Pattern extraction date:** 2026-06-02
