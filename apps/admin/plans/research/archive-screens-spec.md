# Archive & Duplicates screens — implementation spec

**Plan 011 spike output.** Covers `Archive.html` (архив клиентов), `Duplicates.html`
(дубликаты клиентов), and `Trainers-Archive.html` (архив тренеров).
Routes already staged in `src/app/routes.ts`; patterns already in the lazy router.

---

## Screens overview

| Screen | Route constant | URL | Template file |
|---|---|---|---|
| Архив клиентов | `ROUTES.clientsArchive` | `/clients/archive` | `design/Archive.html` |
| Дубликаты клиентов | `ROUTES.clientsDuplicates` | `/clients/duplicates` | `design/Duplicates.html` |
| Архив тренеров | `ROUTES.trainersArchive` | `/trainers/archive` | `design/Trainers-Archive.html` |

All three are **fully designed** screens, not fragments. All three share the same design token
palette already captured in `src/styles/tokens.css`; no new raw token values are needed.

**No fourth screen discovered.** The Duplicates merge modal is a Dialog contained within
the Duplicates page itself — it is not a separate route/wizard. The «Очистить корзину»
action on Archive/Trainers-Archive is a single-step confirmation Toast, not a modal page.

---

## Archive (clients)

### Regions

| Region | Description |
|---|---|
| Page head | h1 «Архив клиентов», subtitle, two header actions: «Дубликаты» (link) + «Очистить корзину» (danger ghost button) |
| Filter tabs | Pill tabs: Все (38), Истёк абонемент (21), Неактивные (12), В корзине (5) |
| Panel toolbar | Search input (max-w-80), count label «Показано N из 38» |
| Bulk bar | Accent-tinted bar: count label + «Снять выбор» + «Восстановить» (primary) |
| Table head | Checkbox · Клиент · Причина · В архиве · Действия |
| Table rows | Avatar+name+phone, reason badge, archive date+relative label, «Восстановить» button per row |
| Empty (archive) | Icon + «В архиве пусто» + subtitle + link to /clients |
| Empty (filter/search) | Icon + «Никого не нашли» + subtitle (inline in table body) |
| Error state | Icon + «Не удалось загрузить архив» + «Повторить» button |
| Loading state | 6-row shimmer skeleton (same column grid) |
| Restore modal | Dialog: icon, dynamic title, list of clients to restore, info callout (visit history preserved; plan NOT auto-activated), Cancel + Restore confirm |
| Toast | Bottom center: success message + «Отменить» (undo) |

### Reason badge styles

| `archiveReason` value | Label | CSS token mapping |
|---|---|---|
| `expired` | Истёк абонемент | `bg-warning-soft text-warning-deep` |
| `inactive` | Неактивен | `bg-surface-3 text-fg-muted` |
| `deleted` | В корзине | `bg-danger-soft text-danger` |

Note: `deleted` maps to what the template calls «В корзине» — it is not hard-deleted yet.

### Decomposition table

| Template region | Target layer | Component/file | Notes |
|---|---|---|---|
| Page wrapper + head | `pages/clients-archive/ClientsArchivePage.tsx` | Page root | Mirrors `ClientsPage.tsx` structure |
| Page head | `pages/clients-archive/components/ArchivePageHead.tsx` | page-local | h1, subtitle, «Дубликаты» + «Очистить корзину» actions |
| Filter tabs (pill style) | `components/data/FilterTabs` | **reuse as-is** | The archive uses pill-style tabs, not underlined; however the existing `FilterTabs` renders underlined tabs. Either pass a `variant="pill"` prop (new) or build a thin page-local `ArchiveFilterTabs` wrapper. **Recommendation:** add `variant` prop to `FilterTabs` — it's the second consumer of pill tabs. |
| Search + count | `components/data/Toolbar` `SearchInput` | **reuse as-is** | Already matches. Count label is page-local JSX. |
| Bulk bar | `components/data/BulkBar` | **reuse as-is** | Needs `actions` prop with one `RestoreIcon` action. The template's bulk bar background is `bg-primary-soft` — existing `BulkBar` uses `bg-surface-2`. Add `variant="accent"` or simply apply `className` override at call site (simpler). |
| Table | `components/data/DataTable` | **reuse as-is** | Columns: checkbox · client (avatar+name+phone) · reason badge · archive date · actions. `rowClassName` not needed — archived rows have no per-row colour state. |
| Reason badge | `pages/clients-archive/components/ArchiveReasonBadge.tsx` | page-local | Pill with `archiveReason` → colour mapping above. |
| Archive date cell | `pages/clients-archive/components/ArchiveDateCell.tsx` | page-local | date string + `ago` sub-label. |
| Restore modal | `pages/clients-archive/components/RestoreClientsModal.tsx` | page-local | shadcn `Dialog`. Props: `ids`, `clients`, `onConfirm`, `onCancel`. Contains scrollable restore-list + info callout. |
| Empty states | `src/components/feedback/EmptyState` | **reuse** | Already exists; supply appropriate `title`/`description`/`action`. |
| Toast | `sonner` (`toast()`) | library | Already wired via `Toaster` in providers. |
| Mobile card layout | `pages/clients-archive/components/ArchiveCard.tsx` | page-local | Card layout at ≤860px (no horizontal table). |

### Route snippet

Insert in `src/app/router.tsx` immediately **after** `ROUTES.clients` and **before**
`ROUTES.client()`. This is the static-before-`:id` rule:

```ts
// --- AFTER the /clients route, BEFORE ROUTES.client() ---
{
  path: ROUTES.clientsArchive,
  lazy: async () => ({
    Component: (await import('@/pages/clients-archive/ClientsArchivePage')).ClientsArchivePage,
  }),
  handle: { breadcrumb: ['Клиенты', 'Архив'] },
},
{
  path: ROUTES.clientsDuplicates,
  lazy: async () => ({
    Component: (await import('@/pages/clients-duplicates/ClientsDuplicatesPage')).ClientsDuplicatesPage,
  }),
  handle: { breadcrumb: ['Клиенты', 'Дубликаты'] },
},
```

### Entry points (template evidence)

- `Archive.html` page head contains: `<a class="btn btn-ghost" href="Duplicates.html">Дубликаты</a>` — mutual cross-link between the two clients sub-pages.
- `Duplicates.html` page head contains: `<a class="btn btn-ghost" href="Archive.html">Архив</a>` — same.
- **There is NO link to the archive from `Clients.html` in the template.** However the project needs an entry point. Recommendation: add a secondary «Архив» ghost button (with archive icon) to `ClientsPageHead.tsx` / `ClientsToolbar.tsx` toolbar — this is the natural discoverable path. Touch: `src/pages/clients/components/ClientsPageHead.tsx` or `ClientsToolbar.tsx` (add one ghost-button linking to `ROUTES.clientsArchive`).

### Data / mock spec

```ts
// src/features/clients/types.ts — add:
export type ArchiveReason = 'expired' | 'inactive' | 'deleted';

export interface ArchivedClient {
  id: string;
  initials: string;
  color: string;        // avatar gradient CSS string
  name: string;
  phone: string;
  archiveReason: ArchiveReason;
  /** ISO date string when moved to archive. */
  archivedAt: string;
  /** Human-readable relative label, e.g. "абонемент истёк", "не был 64 дня". */
  agoLabel: string;
}
```

**Recommendation: parallel type, not extending `Client`.** The active `Client` carries
complex plan/visit/trainer display objects used only on the active list. An archived client
needs none of that; the fields would all be `null`. A lean `ArchivedClient` type is cleaner
and avoids polluting `Client` with `archivedAt?` and optional archive fields across all consumers.
When the backend arrives, a single endpoint returning `ArchivedClient[]` directly maps.

```ts
// src/features/clients/api.ts — add:
export const clientsKeys = {
  ...existing,
  archive: ['clients', 'archive'] as const,
};

export function useArchivedClients() {
  return useQuery({
    queryKey: clientsKeys.archive,
    queryFn: () => mockResponse<ArchivedClient[]>(archivedClientsData),
  });
}
```

```ts
// src/mocks/clients-archive.ts — create:
// 8 ArchivedClient entries matching Archive.html mock data.
// Register in src/mocks/index.ts: export * from './clients-archive';
```

---

## Duplicates

### Regions

| Region | Description |
|---|---|
| Page head | h1 «Дубликаты клиентов», subtitle, «Архив» link + «Сканировать снова» primary button |
| Scan banner | Amber-tinted status strip: groups found count + scan criteria + «Проверено N · N мин назад» meta |
| Groups list | One `DuplicateGroup` card per pair/cluster |
| Group card head | Match label (icon + text, e.g. «Совпадает телефон»), confidence badge (Высокая/Средняя), «Не дубликат» ghost + «Объединить» primary |
| Candidate columns | 2-column grid (1fr 1fr); left = «основная» (accent-tinted bg); columns collapse to 1 on ≤720px |
| Candidate detail | Avatar + name + reference ID (monospace) + field rows (Телефон, Email, Визиты, Абонемент, Создан) with match-hit field highlighted in danger colour |
| Empty state | Icon + «Дубликатов не найдено» + subtitle + link to /clients |
| Loading state | 2-group skeleton |
| Error state | Icon + «Не удалось проверить дубликаты» + «Повторить» |
| Merge modal | Dialog: title, radio option list (pick primary card), info callout (visits + payments merge; secondary card deleted; action irreversible), Cancel + «Объединить» confirm |
| Toast | Bottom center: «Карточки объединены» (no undo), «Отмечено: не дубликат» |

### Confidence badge styles

| `confidence` value | Label | CSS token mapping |
|---|---|---|
| `high` | Высокая вероятность | `bg-danger-soft text-danger` |
| `medium` | Средняя вероятность | `bg-warning-soft text-warning-deep` |

### Match criteria types (from template data)

`'phone'` · `'email'` · `'name'` — which field triggered the match; used to highlight
`match-hit` field in candidate detail rows.

### Decomposition table

| Template region | Target layer | Component/file | Notes |
|---|---|---|---|
| Page root | `pages/clients-duplicates/ClientsDuplicatesPage.tsx` | page root | No table/selection — groups paradigm |
| Page head | `pages/clients-duplicates/components/DuplicatesPageHead.tsx` | page-local | |
| Scan banner | `pages/clients-duplicates/components/ScanBanner.tsx` | page-local | Amber callout strip |
| Groups list | `pages/clients-duplicates/components/DuplicateGroupList.tsx` | page-local | Maps `DuplicateGroup[]` |
| Single group card | `pages/clients-duplicates/components/DuplicateGroupCard.tsx` | page-local | head + 2-col candidates. Dismiss animation: CSS `opacity-0 scale-[0.98]` + remove after 280ms |
| Candidate pane | `pages/clients-duplicates/components/DuplicateCandidate.tsx` | page-local | Avatar, ref ID, field rows, «основная» tag, pick button |
| Merge modal | `pages/clients-duplicates/components/MergeModal.tsx` | page-local | shadcn `Dialog`. Props: `group`, `onMerge(primaryId)`, `onCancel`. Radio state for primary card selection. |
| Empty/error states | `components/feedback/EmptyState` | **reuse** | |
| Toast | `sonner` `toast()` | library | |

There is **no** `DataTable` or `BulkBar` on this screen — the interaction model is
group-by-group, not a flat selectable list.

### Route snippet

(Same block as shown in the Archive section above — both are inserted together before `ROUTES.client()`.)

### Entry points

- `Duplicates.html` head contains `<a class="btn btn-ghost" href="Archive.html">Архив</a>` — mutual cross-link.
- `Archive.html` head contains `<a class="btn btn-ghost" href="Duplicates.html">Дубликаты</a>` — the Archive page is the primary entry into Duplicates.
- No direct link from `Clients.html` template. Recommendation: same «Архив» ghost button in `ClientsPageHead`/`ClientsToolbar` could include a secondary «Дубликаты» link, or the Archive page itself serves as the hub.

### Data / mock spec

```ts
// src/features/clients/types.ts — add:
export type MatchCriteria = 'phone' | 'email' | 'name';
export type DuplicateConfidence = 'high' | 'medium';

export interface DuplicateCandidate {
  id: string;           // e.g. 'CL-00482'
  name: string;
  initials: string;
  color: string;        // avatar gradient CSS string
  phone: string;
  email: string;
  visitsLabel: string;  // e.g. '124 визита'
  planLabel: string;    // e.g. '«12 месяцев» · активен'
  createdLabel: string; // e.g. '14 апр 2025'
  /** The field that triggered the match — highlighted in UI. */
  matchHit: MatchCriteria;
}

export interface DuplicateGroup {
  id: string;
  matchCriteria: MatchCriteria;
  matchLabel: string;   // e.g. 'Совпадает телефон'
  confidence: DuplicateConfidence;
  candidates: [DuplicateCandidate, DuplicateCandidate];  // always exactly 2 in current design
  /** Which candidate id is suggested as primary. */
  suggestedPrimaryId: string;
}

export interface ClientDuplicatesData {
  groups: DuplicateGroup[];
  scannedCount: number;
  /** ISO date of last scan. */
  lastScannedAt: string;
}
```

```ts
// src/features/clients/api.ts — add:
export const clientsKeys = {
  ...existing,
  duplicates: ['clients', 'duplicates'] as const,
};

export function useClientDuplicates() {
  return useQuery({
    queryKey: clientsKeys.duplicates,
    queryFn: () => mockResponse<ClientDuplicatesData>(clientDuplicatesData),
  });
}
```

```ts
// src/mocks/clients-duplicates.ts — create:
// 3 DuplicateGroup entries matching Duplicates.html mock data (g1/g2/g3).
// Register in src/mocks/index.ts: export * from './clients-duplicates';
```

---

## Trainers archive

### Regions

| Region | Description |
|---|---|
| Page head | h1 «Архив тренеров», subtitle, «Вся команда» link (→ /trainers) + «Очистить корзину» danger ghost |
| Filter tabs | Pill tabs: Все (14), Уволены (7), На паузе (4), Отклонённые заявки (3) |
| Panel toolbar | Search input (placeholder «Поиск по имени или специализации…»), count label |
| Bulk bar | Same as clients archive |
| Table head | Checkbox · Тренер · Причина · В архиве · Действия |
| Table rows | Avatar+name+**specialization** (not phone), reason badge, archive date+context label, «Вернуть» button |
| Empty/error/loading states | Same pattern as clients archive |
| Restore modal | Dialog: «Вернуть тренера в команду?» / «Вернуть N тренеров?», info callout (schedule + payout history preserved; trainer NOT auto-assigned to classes), Cancel + confirm |
| Toast | «Тренер возвращён в команду» + «Отменить» (undo) |

**Key visual difference from clients archive:** the subline under trainer name is
`specialization + experience` (e.g. «Функционал · 6 лет»), not a phone number.

### Reason badge styles

| `archiveReason` value | Label | CSS token mapping |
|---|---|---|
| `left` | Уволен | `bg-danger-soft text-danger` |
| `pause` | На паузе | `bg-warning-soft text-warning-deep` |
| `rejected` | Заявка отклонена | `bg-surface-3 text-fg-muted` |

### Decomposition table

| Template region | Target layer | Component/file | Notes |
|---|---|---|---|
| Page root | `pages/trainers-archive/TrainersArchivePage.tsx` | page root | |
| Page head | `pages/trainers-archive/components/TrainerArchivePageHead.tsx` | page-local | |
| Filter tabs (pill) | `components/data/FilterTabs` with pill variant | same decision as clients archive | |
| Search + count | `components/data/Toolbar` `SearchInput` | **reuse as-is** | |
| Bulk bar | `components/data/BulkBar` | **reuse as-is** | |
| Table | `components/data/DataTable` | **reuse as-is** | Columns: checkbox · trainer (avatar+name+spec) · reason badge · archive date · actions |
| Reason badge | `pages/trainers-archive/components/TrainerArchiveReasonBadge.tsx` | page-local | Different reason set from client archive; keep separate |
| Archive date cell | Can **share** `ArchiveDateCell` if extracted to `components/data/` | promote if both screens exist simultaneously | |
| Restore modal | `pages/trainers-archive/components/RestoreTrainersModal.tsx` | page-local | Different callout text (schedule, not plan) |
| Empty/error states | `components/feedback/EmptyState` | **reuse** | |
| Toast | `sonner` `toast()` | library | |
| Mobile card | `pages/trainers-archive/components/TrainerArchiveCard.tsx` | page-local | |

### Route snippet

Insert in `src/app/router.tsx` **after** `ROUTES.trainers` and **before** `ROUTES.trainer()`:

```ts
// --- AFTER the /trainers route, BEFORE ROUTES.trainer() ---
{
  path: ROUTES.trainersArchive,
  lazy: async () => ({
    Component: (await import('@/pages/trainers-archive/TrainersArchivePage')).TrainersArchivePage,
  }),
  handle: { breadcrumb: ['Тренеры', 'Архив'] },
},
```

### Entry points (template evidence)

- `Trainers-Archive.html` page head: `<a class="btn btn-ghost" href="Trainers.html">Вся команда</a>` — back-link to active trainers list.
- **No link to the archive from `Trainers.html` template is present.** Same recommendation as clients: add a ghost «Архив» button to `TrainersPage` toolbar/head. Touch: `src/pages/trainers/TrainersPage.tsx` or its `TrainersPageHead` component.

### Data / mock spec

```ts
// src/features/trainers/types.ts — add:
export type TrainerArchiveReason = 'left' | 'pause' | 'rejected';

export interface ArchivedTrainer {
  id: string;
  initials: string;
  avatarGradient: string;  // matches Trainer.avatarGradient pattern
  name: string;
  /** e.g. 'Функционал · 6 лет' */
  specializationAndExperience: string;
  archiveReason: TrainerArchiveReason;
  /** ISO date string. */
  archivedAt: string;
  /** Human-readable context, e.g. 'уволена по собств.', 'в декрете', 'нет сертификатов'. */
  contextLabel: string;
}
```

**Recommendation: parallel type again, not extending `Trainer`.** Active `Trainer` has
heatmap, earnings, KPI, rating — none needed in the archive list.

```ts
// src/features/trainers/api.ts — add:
export const trainersKeys = {
  ...existing,
  archive: ['trainers', 'archive'] as const,
};

export function useArchivedTrainers() {
  return useQuery({
    queryKey: trainersKeys.archive,
    queryFn: () => mockResponse<ArchivedTrainer[]>(archivedTrainersData),
  });
}
```

```ts
// src/mocks/trainers-archive.ts — create:
// 6 ArchivedTrainer entries matching Trainers-Archive.html mock data.
// Register in src/mocks/index.ts: export * from './trainers-archive';
```

---

## Shared pattern & promotions

### The archive list pattern

All three archive screens share:
- `FilterTabs` (pill variant) → `components/data/FilterTabs`
- `SearchInput` + `Toolbar` → `components/data/Toolbar`
- `BulkBar` → `components/data/BulkBar`
- `DataTable` with checkbox selection → `components/data/DataTable` + `useTableSelection`
- `EmptyState` for 0-results + empty-archive → `components/feedback/EmptyState`
- Toast for restore/purge confirmation

**Promotions required before building these screens:**

1. **`FilterTabs` pill variant:** The existing `FilterTabs` renders underlined tab style.
   These archive screens use pill-shaped tabs (rounded border, bg-fill on active).
   Add `variant: 'underline' | 'pill'` prop to `FilterTabs`. This is a `components/data`
   shared component change — do it once at the start of the first archive screen build.

2. **`ArchiveDateCell`** (date + ago subline): if building clients archive before trainers
   archive, start page-local and promote to `components/data/ArchiveDateCell` when the
   second archive screen is started. (Follows «build shared at first use» memory rule.)

3. **`BulkBar` accent variant:** Archive bulk bars are `bg-primary-soft` tinted (accent),
   not the default neutral `bg-surface-2`. Consider `variant="accent"` prop — or a `className`
   override at call site (simpler short-term). Decide at first screen build.

### The restore modal pattern

Both client and trainer archives have a restore Dialog with:
- Dynamic title (single vs bulk)
- Scrollable list of subjects to restore  
- Info callout (domain-specific text)
- Cancel + confirm actions

These are different enough in callout text and plural forms that keeping them as separate
page-local components is the right call. Do NOT pre-abstract a `RestoreModal` shared primitive.

---

## Routing & entry points

### Complete insertion into `src/app/router.tsx`

The router comment already states the rule: *«Статические подмаршруты регистрируются ДО соответствующих `:id`-маршрутов»*.

Current order in router.tsx (relevant section):
```
ROUTES.clients        ← line 38
ROUTES.client()       ← line 44   ← must stay here
ROUTES.trainers       ← line 62
ROUTES.trainer()      ← line 68   ← must stay here
```

**Insertion plan:**

```ts
// AFTER ROUTES.clients (line ~43), BEFORE ROUTES.client():
{ path: ROUTES.clientsArchive,     lazy: ..., handle: { breadcrumb: ['Клиенты', 'Архив'] } },
{ path: ROUTES.clientsDuplicates,  lazy: ..., handle: { breadcrumb: ['Клиенты', 'Дубликаты'] } },

// AFTER ROUTES.trainers (line ~67), BEFORE ROUTES.trainer():
{ path: ROUTES.trainersArchive,    lazy: ..., handle: { breadcrumb: ['Тренеры', 'Архив'] } },
```

### Sidebar nav

**No sidebar changes needed.** All three screens are sub-pages (bread-crumb style), not
top-level nav items. They are reached via in-page actions, not sidebar links. The sidebar
«Клиенты» and «Тренеры» items continue to point to `ROUTES.clients` and `ROUTES.trainers`.

### Entry point additions needed (not in nav-items.ts)

| From page | Touch location | Action to add |
|---|---|---|
| `ClientsPage` | `ClientsPageHead.tsx` or toolbar | Ghost button «Архив» → `ROUTES.clientsArchive` |
| `TrainersPage` | `TrainersPage` head/toolbar | Ghost button «Архив» → `ROUTES.trainersArchive` |
| `ClientsArchivePage` | Page head (already in spec above) | «Дубликаты» → `ROUTES.clientsDuplicates` |
| `ClientsDuplicatesPage` | Page head (already in spec above) | «Архив» → `ROUTES.clientsArchive` |
| `TrainersArchivePage` | Page head (already in spec above) | «Вся команда» → `ROUTES.trainers` |

---

## Backend questions

These must be answered before the mock → real API switchover, but can be left open during mock phase.

1. **Soft-delete model:** Is «В архиве» the same as soft-delete (`deleted_at` timestamp)?
   Or is archiving a separate explicit state (`archived_at`) distinct from deletion?
   The template shows three reasons: `expired` (automatic), `inactive` (automatic?), `deleted` (manual).
   Who triggers each?

2. **Restore window & auto-purge:** Template subtitle says «Записи старше 12 месяцев
   очищаются автоматически.» Is this enforced server-side? Is there a way to disable it
   per-client (VIP clients, legal hold)? Does the 12-month clock start at `archived_at`?

3. **«Удалить навсегда» / «Очистить корзину»:** The «Очистить корзину» button appears to
   hard-delete only the `deleted` (В корзине) subset — not `expired`/`inactive` records.
   Is that correct? Or does it purge the entire archive? What are the GDPR/legal
   implications (visit history, payment records)?

4. **Merge semantics — field-level vs whole-record:**
   - Does merge always take ALL fields from the primary card (whole-record), or can
     administrators choose which fields to keep field-by-field?
   - The current template shows whole-record: pick a primary card, everything transfers.
     Field-level merge UI would be a substantially different (larger) component.

5. **Merge — what is merged exactly:**
   - Visit history: does it physically move visit records to the primary's ID?
   - Payment records: same question.
   - Membership/plan: if both cards have active plans, which one wins?
   - Notes: concatenated or primary wins?

6. **Merge — secondary card fate:** Template callout says «Карточка будет удалена.
   Действие необратимо.» Does the secondary card go to the archive first (with `deleted` reason),
   or is it hard-deleted immediately? The «necessary» label suggests hard-delete.

7. **Duplicate detection trigger:** Is it run on every new client save? On a schedule?
   Only on-demand (the «Сканировать снова» button)? The template suggests on-demand +
   event-driven, but this affects whether the scan result is stored or computed fresh.

8. **Trainer archive — «Отклонённые заявки» (rejected applications):**
   Are these trainer-applicants who never became full trainers? Do they have any
   visit/payment history, or only application metadata? This affects the data model.

9. **Audit trail:** The app has `/settings/audit`. Do archive, restore, and merge actions
   write audit log entries? If yes, what payload does each action produce?

10. **Bulk restore — pagination:** If 847 clients are in the archive and an admin selects
    all (across pages), what does «Восстановить» mean for records not yet loaded?
    Current mock is single-page; multi-page bulk restore needs backend support (restore by filter).

### Mock phase behaviour (local-only)

During mock phase, actions update the `QueryClient` cache optimistically:

```ts
// Restore: remove IDs from archive list
queryClient.setQueryData(clientsKeys.archive, (old: ArchivedClient[]) =>
  old.filter(c => !restoredIds.includes(c.id))
);

// Dismiss duplicate group: remove group from list
queryClient.setQueryData(clientsKeys.duplicates, (old: ClientDuplicatesData) => ({
  ...old,
  groups: old.groups.filter(g => g.id !== dismissedGroupId),
}));

// Merge: same as dismiss (secondary card gone, primary stays in clients)
queryClient.setQueryData(clientsKeys.duplicates, (old: ClientDuplicatesData) => ({
  ...old,
  groups: old.groups.filter(g => g.id !== mergedGroupId),
}));

// Purge «В корзине»: remove deleted subset
queryClient.setQueryData(clientsKeys.archive, (old: ArchivedClient[]) =>
  old.filter(c => c.archiveReason !== 'deleted')
);
```

---

## Effort estimate

| Screen | Size | Rationale |
|---|---|---|
| Архив клиентов | **M** | Flat list + `DataTable` + selection machinery all exist. New: pill `FilterTabs` variant, `ArchivedClient` type, restore Dialog, mock data. 1–2 days. |
| Дубликаты клиентов | **M** | No table — group-card paradigm is novel, but each card is small. New: `DuplicateGroup` type, `ScanBanner`, `DuplicateGroupCard`, `MergeModal`, mock data. Dismiss animation is trivial CSS. 1–2 days. |
| Архив тренеров | **S** | Near-identical to clients archive. Shared `DataTable`/`BulkBar`/`FilterTabs` (once pill variant exists). New: `ArchivedTrainer` type, trainer-specific reason badge + restore callout text. ~1 day. |

---

## Suggested build order

1. **Архив клиентов first** — largest consumer of the pattern; forces the `FilterTabs` pill
   variant decision and creates the `ArchivedClient` type. Validates the restore Dialog pattern.

2. **Дубликаты клиентов second** — different interaction model (groups vs list), so builds
   independently without waiting for trainers archive. Clarifies merge-semantics questions
   with the team before backend work starts.

3. **Архив тренеров last** — smallest. By this point `FilterTabs` pill variant exists;
   reuse is maximal. The only new things are trainer-specific type and callout copy.
