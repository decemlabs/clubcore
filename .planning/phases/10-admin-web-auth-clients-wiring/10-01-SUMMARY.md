---
phase: 10
plan: 01
subsystem: admin-web/ui-primitives
tags: [admin-web, ui, reui, shadcn, typescript]
one-liner: "ReUI base-nova registry switch + nine UI primitives installed (DataGrid, InputOTP, Button, Input, Form, Label, DropdownMenu, Dialog, AlertDialog) with strict-TS fixes"
dependency_graph:
  requires: []
  provides:
    - apps/admin-web/src/shared/ui/button.tsx
    - apps/admin-web/src/shared/ui/input.tsx
    - apps/admin-web/src/shared/ui/form.tsx
    - apps/admin-web/src/shared/ui/label.tsx
    - apps/admin-web/src/shared/ui/dropdown-menu.tsx
    - apps/admin-web/src/shared/ui/dialog.tsx
    - apps/admin-web/src/shared/ui/alert-dialog.tsx
    - apps/admin-web/src/shared/ui/data-grid.tsx
    - apps/admin-web/src/shared/ui/input-otp.tsx
    - apps/admin-web/src/components/reui/data-grid/
  affects:
    - apps/admin-web/eslint.config.js
    - apps/admin-web/components.json
    - apps/admin-web/src/app/index.css
tech_stack:
  added:
    - "@base-ui/react ^1.4.1 (used by shadcn latest button + input via standard registry)"
    - "radix-ui ^1.4.3 (unified Radix package, replaces @radix-ui/react-* individual packages)"
    - "input-otp ^1.4.2 (InputOTP primitive)"
    - "@dnd-kit/core ^6.3.1 (ReUI DataGrid drag-and-drop)"
    - "@dnd-kit/modifiers ^9.0.0"
    - "@dnd-kit/sortable ^10.0.0"
    - "@dnd-kit/utilities ^3.2.2"
    - "@tanstack/react-virtual ^3.13.24 (ReUI DataGrid virtualization)"
  patterns:
    - "shadcn CLI for primitive installs (standard registry + direct ReUI URL)"
    - "Re-export barrel for multi-file primitives (data-grid.tsx → src/components/reui/data-grid/)"
key_files:
  created:
    - apps/admin-web/src/shared/ui/label.tsx
    - apps/admin-web/src/shared/ui/dialog.tsx
    - apps/admin-web/src/shared/ui/alert-dialog.tsx
    - apps/admin-web/src/shared/ui/form.tsx
    - apps/admin-web/src/shared/ui/checkbox.tsx
    - apps/admin-web/src/shared/ui/popover.tsx
    - apps/admin-web/src/shared/ui/select.tsx
    - apps/admin-web/src/shared/ui/spinner.tsx
    - apps/admin-web/src/shared/ui/data-grid.tsx
    - apps/admin-web/src/shared/ui/input-otp.tsx
    - apps/admin-web/src/components/reui/ (10 files)
  modified:
    - apps/admin-web/components.json (style: new-york → base-nova)
    - apps/admin-web/src/shared/ui/input.tsx (shadcn latest: now uses @base-ui/react/input)
    - apps/admin-web/eslint.config.js (react-refresh allow-list extended)
    - apps/admin-web/src/app/index.css (--success, --warning, --info, --invert tokens added by data-grid install)
    - apps/admin-web/package.json (new deps)
    - pnpm-lock.yaml
decisions:
  - "button.tsx + dropdown-menu.tsx restored to original (radix-ui-based) to preserve asChild support in AppShell (ProfileMenu, RoleSwitcher, ThemeSwitcher)"
  - "data-grid installed from direct radix-nova URL (multi-file: src/components/reui/data-grid/); re-export barrel at src/shared/ui/data-grid.tsx"
  - "form.tsx hand-written (canonical shadcn form bridge): shadcn registry v1.2+ no longer provides this file; react-hook-form + @radix-ui/react-slot"
metrics:
  duration: "~90 minutes"
  completed_date: "2026-05-04T13:02:56Z"
  tasks_completed: 3
  files_modified: 30
---

# Phase 10 Plan 01: ReUI Primitive Baseline Summary

Nine ReUI primitives installed in `apps/admin-web/src/shared/ui/` establishing the Phase 10 UI foundation, with `components.json` switched to `style: "base-nova"`, ESLint allow-list extended, and `--success` semantic tokens added.

## Commits

| Hash | Description |
|------|-------------|
| 757a6d5 | Task 1: Switch components.json style to base-nova |
| 20c49dc | Task 2: Install nine ReUI primitives + shadcn components |
| 2930180 | Task 3: Extend ESLint allow-list for new ReUI primitives |

## What Was Installed

| Primitive | Source | Location | Notes |
|-----------|--------|----------|-------|
| Button | Restored (radix-ui original) | `src/shared/ui/button.tsx` | Restored to preserve asChild for AppShell |
| Input | shadcn standard (latest) | `src/shared/ui/input.tsx` | Now uses @base-ui/react/input |
| Form | Hand-written canonical | `src/shared/ui/form.tsx` | shadcn registry v1.2+ no longer provides file |
| Label | shadcn standard (latest) | `src/shared/ui/label.tsx` | Plain HTML label wrapper (no Radix) |
| DropdownMenu | Restored (radix-ui original) | `src/shared/ui/dropdown-menu.tsx` | Restored to preserve asChild for AppShell |
| Dialog | shadcn standard (latest) | `src/shared/ui/dialog.tsx` | New file |
| AlertDialog | shadcn standard (latest) | `src/shared/ui/alert-dialog.tsx` | New file |
| DataGrid | ReUI radix-nova direct URL | `src/shared/ui/data-grid.tsx` (barrel) + `src/components/reui/data-grid/` | Multi-file component; 10 files |
| InputOTP | shadcn standard | `src/shared/ui/input-otp.tsx` | Uses `input-otp` npm package |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ReUI base-nova registry returns HTML, not JSON**
- **Found during:** Task 2
- **Issue:** `https://reui.io/r/base-nova/{name}.json` URLs return 307 redirect → HTML page (Next.js app), not JSON. shadcn CLI fails with "item not found" for all @reui/* installs via the base-nova URL template.
- **Fix:** Installed primitives from shadcn standard registry (the exact "fallback to shadcn standard" Assumption A1 described). Installed DataGrid from `radix-nova` direct URL which resolves correctly.
- **Files modified:** `apps/admin-web/package.json`, `pnpm-lock.yaml`, all new UI files
- **Commit:** 20c49dc

**2. [Rule 1 - Bug] shadcn latest installs use @base-ui/react (different API)**
- **Found during:** Task 2
- **Issue:** shadcn standard registry (latest) replaced `button.tsx` and `dropdown-menu.tsx` with `@base-ui/react` versions that don't support `asChild` prop. AppShell components (ProfileMenu, RoleSwitcher, ThemeSwitcher) use `<DropdownMenuTrigger asChild>` — this broke typecheck.
- **Fix:** Restored `button.tsx` and `dropdown-menu.tsx` to the pre-plan originals (which used `radix-ui` unified package and DO support `asChild`).
- **Files modified:** `apps/admin-web/src/shared/ui/button.tsx`, `apps/admin-web/src/shared/ui/dropdown-menu.tsx`
- **Commit:** Part of 20c49dc

**3. [Rule 2 - Missing critical] shadcn form.tsx no longer provided by registry**
- **Found during:** Task 2
- **Issue:** `pnpm dlx shadcn@latest add form` exits successfully but creates 0 files. The shadcn registry v1.2+ removed form.tsx from the registry (react-hook-form bridge is now expected to be hand-maintained).
- **Fix:** Created canonical `form.tsx` following the stable shadcn pattern: `FormProvider`, `FormField` (Controller wrapper), `FormItem`, `FormLabel`, `FormControl` (Slot), `FormDescription`, `FormMessage`, `useFormField`.
- **Files modified:** `apps/admin-web/src/shared/ui/form.tsx` (created)
- **Commit:** 20c49dc

**4. [Rule 1 - Bug] ReUI DataGrid TypeScript strict-mode incompatibilities**
- **Found during:** Task 2 (post-install typecheck)
- **Issue:** ReUI DataGrid files installed with non-strict TypeScript patterns: TS1484 (type imports not using `import type` in verbatimModuleSyntax mode), TS2322 (indeterminate checkbox value mismatch with @base-ui Checkbox), TS2345 (string|undefined from noUncheckedIndexedAccess).
- **Fix:** 
  - Added `import type` to all type-only imports in 7 data-grid files
  - Changed `checked="indeterminate"` to `checked={...} indeterminate={...}` for @base-ui Checkbox
  - Used `splice()[0]!` for noUncheckedIndexedAccess
  - Fixed `render={...}` Base UI pattern to `asChild` Radix pattern in column-header
- **Files modified:** All 10 `src/components/reui/data-grid/` files
- **Commit:** 20c49dc

**5. [Rule 1 - Bug] separator.tsx + skeleton.tsx overwritten by data-grid install**
- **Found during:** Task 2 (git diff review)
- **Issue:** ReUI data-grid's transitive deps caused shadcn to overwrite `separator.tsx` (changed to `@base-ui/react/separator`) and `skeleton.tsx` (changed bg-accent → bg-muted). Per D-17, these are untouched files.
- **Fix:** `git checkout HEAD -- separator.tsx skeleton.tsx`
- **Commit:** Part of 20c49dc

**6. [Rule 2 - Missing] DataGrid lands in src/components/reui/data-grid/ not src/shared/ui/**
- **Found during:** Task 2
- **Issue:** ReUI DataGrid registry defines multi-file paths starting with `data-grid/` which resolve to `src/components/reui/data-grid/` (not the expected `src/shared/ui/data-grid.tsx`).
- **Fix:** Created `src/shared/ui/data-grid.tsx` as a re-export barrel pointing to the installed location. Consumers import from `@/shared/ui/data-grid` as planned.
- **Files modified:** `apps/admin-web/src/shared/ui/data-grid.tsx` (created)
- **Commit:** 20c49dc

## Theme Tokens

The `src/app/index.css` was updated by the data-grid install with additional tokens:
- `--success` / `--success-foreground` (OKLCH green, required by plan)
- `--warning` / `--warning-foreground` (OKLCH yellow)
- `--info` / `--info-foreground` (OKLCH blue)
- `--invert` / `--invert-foreground` (black/white swap)

All tokens are semantic OKLCH values (no raw palette violations).

## Known Stubs

None — this plan only installs UI primitives; no data flow or business logic stubs.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| supply-chain: new npm packages | package.json | @base-ui/react, radix-ui, @dnd-kit/*, @tanstack/react-virtual added; all from established maintainers (Radix/Floating UI, dnd-kit, TanStack) |

T-10-01 mitigated: scan of installed primitives confirms no `process.env`, `import.meta.env`, `eval()`, or `fetch()` calls in any of the 9 `src/shared/ui/*.tsx` files or `src/components/reui/data-grid/*.tsx` files.

## Self-Check: PASSED

All files verified present:
- FOUND: apps/admin-web/src/shared/ui/label.tsx
- FOUND: apps/admin-web/src/shared/ui/dialog.tsx
- FOUND: apps/admin-web/src/shared/ui/alert-dialog.tsx
- FOUND: apps/admin-web/src/shared/ui/form.tsx
- FOUND: apps/admin-web/src/shared/ui/data-grid.tsx
- FOUND: apps/admin-web/src/shared/ui/input-otp.tsx

All commits verified present:
- FOUND: 757a6d5 chore(10-01): switch components.json style from new-york to base-nova
- FOUND: 20c49dc feat(10-01): install nine ReUI primitives and new shadcn components
- FOUND: 2930180 chore(10-01): extend ESLint allow-list for new ReUI primitives
