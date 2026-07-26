# Stack Research — v4.1 Codebase Hardening (tooling additions)

**Domain:** Mechanical-defect-detection tooling for an existing, fully-shipped full-stack CRM (FastAPI + two React SPAs) undergoing a quality/tech-debt milestone. No new product features.
**Researched:** 2026-07-26
**Confidence:** HIGH (all versions verified live via exa/npm/pypi/GitHub releases, current as of 2026-07-26; repo claims verified by reading actual source, not the milestone brief)

**Repo-reality correction (verified by reading source, not assumed):** the milestone brief describes `apps/admin` as "React 19 + Vite 6." The actual `apps/admin/package.json` pins `react@^18.3.1`, `vite@^5.4.14`, `react-router-dom@^6.28.2` (not TanStack Router — that stack lives only in the deleted `admin-web`). `apps/client` is `react@18.3.1` + `vite@^6.0.0`. All version/compat notes below are grounded in the real files, not the brief. This is exactly the kind of drift the audit phase should log as a DEFECT (stale CLAUDE.md / PROJECT.md tech-stack prose) — flagging it here rather than silently propagating it.

**Also verified by reading source — two "already have it" corrections to the question's premise:**
1. `Makefile:helm-validate` already pipes `helm template | kubeconform -strict -ignore-missing-schemas -kubernetes-version 1.29.0`. Kubeconform is **not a gap** — see §(d).
2. `infra/scripts/restore-verify.sh` already does a fail-closed, row-count-verified, auto-cleanup CNPG restore round-trip to a scratch namespace. This is **materially more specific** than any generic K8s test-framework's default assertions — see §(d) "what NOT to add."

---

## (a) Frontend-schema-vs-backend-contract drift

### Root cause, verified in code

`apps/admin/src/api/client.ts::staffRequest()` returns `Promise<unknown>` — the OpenAPI-generated `paths` type only constrains the URL/method, never the response shape. Each of the 17 `features/*/schemas.ts` files (`apps/admin/src/features/{clients,memberships,visits,plans,...}/schemas.ts`) hand-writes a **second, independent** Zod schema for the same wire shape already described in `packages/api-client/src/schema.d.ts` (generated from `apps/backend/openapi.json` via `openapi-typescript`). Nothing cross-checks these two descriptions of the same contract against each other. `apps/client` doesn't even have this second line of defense — it has zero `zod` dependency, so its `client_auth`/`client_portal` consumers have no runtime shape validation at all.

This is why the two real incidents (v3.0/v3.1 UAT) passed every existing gate: `tsc` type-checked the hand-written Zod-inferred type against itself (self-consistent, not against the generated contract); the OpenAPI drift gate only proves `openapi.json`/`schema.d.ts` are regenerated from the Pydantic models — it proves nothing about what the ASGI app actually **returns** at runtime, nor about whether the hand-written Zod schema on the FE matches either.

Closing this gap needs **two independent, complementary layers** — a static one (FE-authoring mistakes) and a live one (backend-implementation-vs-its-own-spec mistakes). Recommended in priority order:

### 1. Compile-time Zod-vs-generated-type equality assertion — HIGHEST PRIORITY, ZERO NEW DEPENDENCIES

The project already has the exact mechanism needed: `packages/api-client/src/schema.contract.test.ts` uses an `AssertNonNever<T>` type helper + a `_checks` tuple to fail `tsc`/`vitest` at compile time when an OpenAPI path goes missing. Extend this **same pattern** with a structural-equality variant and apply it per domain, where the Zod schemas actually live:

```ts
// add once, e.g. packages/api-client/src/assert-equal.ts
export type AssertEqual<A, B> = (<T>() => T extends A ? 1 : 2) extends
  (<T>() => T extends B ? 1 : 2) ? true : false
```

Then in each `apps/admin/src/features/<domain>/schemas.ts`, add one line per hand-written response schema:

```ts
import type { paths } from '@clubcore/api-client'
import type { AssertEqual } from '@clubcore/api-client/assert-equal'

type _ClientWireShape = paths['/api/v1/clients/{client_id}']['get']['responses']['200']['content']['application/json']['data']
type _ClientSchemaMatchesWire = AssertEqual<z.infer<typeof ClientSchema>, _ClientWireShape>
const _check: _ClientSchemaMatchesWire = true // fails tsc if the two diverge
```

- **What it catches:** the exact class of bug in the v3.0/v3.1 incidents where the FE Zod schema and the backend-declared OpenAPI type structurally disagree (wrong optionality, wrong union, renamed field, `number` vs `string | number`) — the moment either side changes, without a human noticing.
- **Cost:** zero new packages, zero new CI job (rides the existing `tsc -b --noEmit` step in the `admin`/`client`/`api-client` CI jobs). One afternoon to retrofit into the 17 existing schema files.
- **Limit:** only catches drift **the OpenAPI spec itself already documents correctly**. It cannot catch a case where the backend's actual runtime response violates its own declared spec — that needs layer 2.
- **Where:** `apps/admin/src/features/*/schemas.ts` (17 files); mirror the pattern into `apps/client` once `zod` is introduced there (see below).

### 2. Schemathesis — backend responses vs. its own OpenAPI schema (new backend dependency)

| Package | Version (verified) | Purpose |
|---|---|---|
| `schemathesis` | **4.22.4** (PyPI, 2026-07-08) | Property-based testing that generates inputs from `apps/backend/openapi.json`/the live ASGI schema and asserts every real response conforms to what the spec declares |

- **Integration:** `schemathesis.openapi.from_asgi("/openapi.json", app)` directly against the FastAPI ASGI app (no network, works with the project's `httpx ASGITransport` testing convention) — add a `apps/backend/tests/test_schema_contract.py`:
  ```python
  import schemathesis
  from app.main import app
  schema = schemathesis.openapi.from_asgi("/openapi.json", app)

  @schema.parametrize()
  def test_api_contract(case):
      case.call_and_validate()
  ```
- **What it catches:** 500s on edge-case inputs, and — critically for this question — **responses that don't match the documented schema**, i.e. exactly the failure mode where the backend silently serves a shape its own `openapi.json` doesn't actually describe (which layer 1 cannot see, because layer 1 trusts the spec). Requires `fastapi>=0.86.0`, `httpx<1.0,>=0.22.0`, `pytest-asyncio<2.0,>=1.0` — all already satisfied by the pinned backend stack (FastAPI 0.115+, httpx, pytest-asyncio).
- **Cost:** one new dev-dependency (`uv add --dev schemathesis`), one new test file, add as a step in the existing `backend` CI job (not a new parallel job) right after `pytest`.
- **Caution:** turn off destructive/mutating-endpoint fuzzing by default (`case.call_and_validate()` on state-changing routes against a real Postgres/Redis test DB can leave garbage data) — scope the first pass to `GET`-only operations, or run in a dedicated schema-isolated test DB the pytest suite already provisions. Do not let this become an unbounded fuzzing project — cap it at "does every response conform to the schema," not full security fuzzing (that's a different, separate concern).

### 3. Formalize the "≥1 live-backend contract test per domain" convention that already exists as project practice

`PROJECT.md` already records the v3.1 lesson ("обязателен в gate: ≥1 contract-тест на домен, парсящий РЕАЛЬНЫЙ ответ backend") as a **decision**, not a tool gap. This is process discipline, not a package: a small helper (`apps/admin/src/test/liveContract.ts`, no new dependency) that points `staffRequest`/`clientRequest` at a running `docker compose up` backend (seeded DB) instead of jsdom/MSW mocks, and `Schema.parse()`s the real response in a `*.live.test.ts` file excluded from the default `vitest run` (only run manually / in the audit phase, since it needs a live stack). Codify this as **one file per domain**, mirroring the 17 `schemas.ts` files, so the audit phase has a mechanical "does the hand-written Zod schema survive a real HTTP round-trip" check that is independent of both layers above (it catches integration-level surprises — e.g., an nginx/proxy layer mangling a header, a cookie not round-tripping — that neither a type-checker nor an in-process ASGI schema test can see).

### What NOT to add for (a)

| Avoid | Why | Use instead |
|---|---|---|
| `orval` (8.22.0) generating Zod from OpenAPI as a wholesale replacement for the 17 hand-written schema files | The hand-written schemas encode form-validation rules the OpenAPI spec doesn't have (Russian error messages, regex, min-lengths for `ClientCreateSchema` etc. — see `apps/admin/src/features/clients/schemas.ts` lines 57+). A full swap is a rewrite of every `features/*/api.ts` consumer mid-hardening-milestone — this is scope growth, not convergence, and risks reintroducing exactly the kind of regression this milestone exists to close. Revisit for **new** domains only, never migrate existing ones in v4.1. |
| `openapi-zod-client` (1.18.3) / `zodios` client generation | Same rewrite-cost problem as orval, plus it replaces the existing hand-rolled `staffRequest`/`clientRequest` transport (cookie/CSRF/refresh-rotation logic is bespoke and security-sensitive — not something to regenerate). |
| `typed-openapi` | Same category as above — a client-generation tool, not a drift-detector. Out of scope. |
| Pact / consumer-driven contract testing | Designed for N independent services with separate deploy cycles and a contract broker. This is one monolith + two frontends in one repo, one release cadence — Pact's broker/versioning machinery solves a coordination problem this project doesn't have. |
| Prism (mock server) | Solves "develop the frontend before the backend exists" — the backend has existed and been live since v2.0. Not a drift-detector. |
| MSW (Mock Service Worker) as a *drift-detection* tool | MSW is excellent for isolating unit tests from the network, which is what the existing `vitest` suites already do — but a mock, by construction, cannot detect that the mock itself has drifted from reality. Keep MSW/manual mocks for unit tests; drift-detection must hit a **real** backend (layers 2 and 3 above). |

---

## (b) Dead code, duplication, and unused exports

### TypeScript / pnpm workspace (apps/admin, apps/client, packages/api-client, packages/ui)

| Tool | Version (verified) | Catches | Integration point |
|---|---|---|---|
| **Knip** | **6.20.0** (npm, 2026-06-24) | Unused files, unused exports (including framework-aware — understands Vite/React entry points, lazy-loaded routes when configured), unused/missing `package.json` dependencies across pnpm workspaces. This is the actively-maintained standard; it supersedes ts-prune. | Root `knip.json` with `workspaces` entries for `apps/admin`, `apps/client`, `packages/api-client`, `packages/ui`; explicit `entry` globs for each app's `main.tsx`/`vite.config.ts`/`vitest.config.ts` **and** the `lazy: async () => (await import('...'))` route entries in `apps/admin/src/app/router.tsx` (Knip's static analysis will false-positive on dynamic `import()` targets unless they're declared as entry points — this repo's lazy-route pattern is exactly the shape Knip's docs warn needs explicit entry configuration). |
| ~~ts-prune~~ | — | Deprecated in the ecosystem in favor of Knip (Knip's own docs and multiple 2026 sources recommend migrating; ts-prune has had no meaningful releases since). **Do not add ts-prune.** |

**Rollout, not a permanent CI gate on day one:** run `npx knip` once during the audit phase, triage every finding into the DEFECT registry (file + severity + category), fix. Only wire it into `admin`/`client` CI jobs (as an additional step, not a new parallel job) **after** a clean baseline exists — added blind to a CI gate on day one in a codebase with dynamic-import lazy routes and workspace-shared `packages/ui`/`packages/api-client` will produce enough false positives that the team stops reading the output, which is the one outcome this research is explicitly told to avoid.

### Duplication (cross-language: TS + Python in one pass)

| Tool | Version (verified) | Notes |
|---|---|---|
| `jscpd` | **5.0.12** (npm, Rust engine, 2026-07-08) | Rewritten in Rust — 24-37x faster than the old Node engine, self-contained binary, supports TypeScript/TSX **and** Python in the same run. Run once, repo-root, excluding `node_modules`/`dist`/generated files (`schema.d.ts`, `openapi.json`, `routeTree.gen.ts`-equivalents) with `--min-tokens 50 --min-lines 5` to avoid flagging small, idiomatic react-hook-form/Zod boilerplate as "duplication." |

Treat as a **one-shot audit tool**, not a gate: duplication metrics have a real false-positive rate in this codebase specifically (17 near-identical `schemas.ts` files, 20+ near-identical `features/*/api.ts` TanStack Query hook files — these are **intentional** convention-driven repetition per the project's own `features/<domain>/{types.ts,api.ts,components/}` layering rule, not tech debt). Human-triage every finding into the DEFECT registry; do not block CI on a duplication threshold.

### Python (apps/backend)

| Tool | Version (verified) | Catches | Why it's additive, not duplicative of ruff |
|---|---|---|---|
| `vulture` | **2.16** (PyPI, 2026-03-25) | Whole unused functions/classes/methods that are defined but never referenced anywhere in the project — requires cross-file reachability analysis. | Ruff's `F401`/`F841` catch unused **imports/local variables** per-file; it does not do whole-project "is this function ever called" analysis. Vulture is genuinely additive, not redundant. Run `uv run vulture apps/backend/app --min-confidence 80`, triage into DEFECT registry. Use `--min-confidence 100` only if promoting to a permanent (non-blocking) pre-commit hook later. |
| `deptry` | **0.25.1** (PyPI, 2026-03-18) | Unused declared dependencies (`DEP002`), missing-but-imported dependencies (`DEP001`), dev-deps imported in production code (`DEP004`), transitive-only deps relied on directly (`DEP003`) — reads `pyproject.toml` + `uv`'s resolved env directly. | Ruff has no dependency-graph awareness at all. Cheap, low-false-positive (unlike Knip/jscpd), safe to wire straight into the existing `backend` CI job as one more step after `ruff check` (not a new parallel job) once the initial cleanup pass is done. |

### What NOT to add for (b)

| Avoid | Why |
|---|---|
| `ts-prune` | Superseded by Knip; adding both is pure redundancy. |
| `madge` (circular-dependency graphing) | `apps/admin`/`apps/client` already enforce the exact boundary this would check via ESLint's `import/no-restricted-paths` (per `eslint.config.js`, already ADR-locked in `CLAUDE.md`). Adding a second tool to re-verify a rule the linter already enforces on every CI run is duplicate coverage, not new coverage. If the ESLint rule itself is suspected of gaps, that's a code-review finding for the boundary rule, not a case for a new dependency-graph tool. |
| `pylint` R0801 (duplicate-code) as a **second** Python duplication detector | `jscpd` already covers Python in the same cross-language pass; running both means triaging two divergent duplication reports for the same files. |
| Wiring Knip/jscpd into CI as **blocking** gates on day one | Guaranteed false-positive noise (dynamic imports, intentional per-domain repetition) the team will learn to ignore — directly the anti-pattern this research is asked to avoid. Gate only after a clean, human-triaged baseline. |

---

## (c) Browser-driven UAT automation (route sweep against a live backend)

### What's already proven to work here — keep it

`apps/admin` already has `src/app/router-smoke.test.tsx`, a vitest+jsdom suite that renders every registered route — but against **mocks**, not the live backend, so it cannot catch wire-shape drift or a route silently still pointing at `ComingSoon`. Separately, prior milestones (v3.0/v3.1) closed schema-drift bugs via **interactive chrome-devtools-mcp / agent-browser sessions against a live `docker compose up` stack** — this already-proven, zero-new-tooling workflow is the right mechanism for the **exploratory, human/agent-in-the-loop audit pass** (finding unknown-unknowns, judging visual correctness). Keep using it for that job — this environment's `agent-browser` skill is the direct continuation of that same pattern.

### The genuine gap: a mechanically re-runnable regression check

What's missing is a **deterministic, no-LLM-in-the-loop** script that can be re-run after every fix batch to prove "no new placeholder / crash / console error appeared," which an interactive agent session cannot cheaply provide on repeat.

| Package | Version (verified) | Purpose |
|---|---|---|
| `@playwright/test` | **1.62.0** (npm, 2026-07-24) | Deterministic, scriptable browser driver + assertion/test-runner in one package. |

**Integration (bespoke script, not a framework buildout):**
- New root-level `e2e/route-sweep.spec.ts` (single spec, not a whole Playwright project per app) that:
  1. Reads the **actual route sources of truth already in the repo** — `apps/admin/src/app/routes.ts` (`ROUTES` constant) + `apps/admin/src/app/nav-items.ts` + the `lazy:` registrations in `app/router.tsx` — so the route list can never silently drift from what the app really registers. Do the same for `apps/client`'s `react-router` route table.
  2. For each route, navigates against a **live `docker compose up` backend** (seeded DB, real login), and asserts:
     - no `page.on('pageerror')` (uncaught exception / React error boundary trip),
     - no `page.on('console', msg => msg.type() === 'error')`,
     - no failed network response in the 4xx/5xx range except an explicit allow-list (expected 401s pre-login, etc.),
     - the rendered DOM does **not** match the project's `ComingSoon`/placeholder marker (a stable `data-testid` or heading text) when the route is supposed to be wired — this is the exact FND-04-class bug (wired-but-unreachable / wired-but-still-a-placeholder) the milestone names explicitly.
  3. Install **Chromium only** (`npx playwright install --with-deps chromium`) — no reason to pay for Firefox/WebKit in a solo-maintainer internal CRM; keeps the footprint small.
- **Run it as an on-demand script** (`pnpm e2e:route-sweep`), invoked manually during the audit phase and again after each fix-batch to prove no regression — **not** wired into the PR-blocking CI (it needs a live multi-container stack with seeded data, which is heavier and slower than the existing 5 CI gates and would either need `services:` containers for two frontends+backend in GitHub Actions, or become the next flaky gate everyone learns to skip). If continuous coverage is wanted later, wire it as a manual `workflow_dispatch` GitHub Action, never a required PR check.

### What NOT to add for (c)

| Avoid | Why |
|---|---|
| Cypress | Functionally redundant with Playwright for this use case (single-browser, console/network assertions); no reason to run two E2E runners in a solo-maintainer project. |
| Selenium / WebdriverIO | Legacy relative to Playwright's built-in auto-waiting, tracing, and console/network hooks — more code for the same result. |
| TestCafe | Same category, less active development than Playwright. |
| BackstopJS / Percy / Chromatic (visual regression / pixel-diffing) | Solves a **different** problem (design-fidelity drift), not this milestone's target (crashes / blank screens / unreachable routes). This milestone is explicitly hardening, not a design-QA pass — visual regression tooling is scope creep here. |
| A full Storybook + component-test pipeline | No Storybook exists in this repo today; introducing one plus story-level tests is a net-new investment unrelated to "walk every route against a live backend," which is a route-level, not component-level, concern. |
| Wiring the route sweep into the PR-blocking CI from day one | Needs a live stateful multi-container stack; adding that as a **required** check either slows every PR materially or becomes the next ignored-flaky-gate anti-pattern. Keep it as an on-demand / manual-dispatch tool that proves fixes, not a merge gate. |

---

## (d) Kubernetes / Helm / backup-restore verification beyond what's already there

**Important finding from reading the actual repo (not assumed from the prompt):** the project already has more than "helm lint / terraform validate / make -n":

- `Makefile:helm-validate` already runs `helm template ... | kubeconform -strict -ignore-missing-schemas -kubernetes-version 1.29.0` — **kubeconform is already in the stack.** Do not re-recommend it; it's correctly wired to k3d's target version.
- `infra/scripts/restore-verify.sh` already implements a fail-closed, auto-cleanup, row-count-verified CNPG restore round-trip to a **scratch namespace** (never touches the live cluster) — this is materially more specific and better-engineered than the default assertions any generic Kubernetes test framework would give out of the box.
- `infra/scripts/smoke.sh` already implements an 8-check "looks-done-but-isn't" smoke (WS-upgrade-through-Traefik, PWA SW cache headers, DNS-per-pod, TZ=UTC, migrate-Job-Succeeded, Redis AOF) — again, project-specific checks a generic tool wouldn't know to write.

Given that, the honest answer biased against sprawl is: **most of the "missing" tooling for this milestone isn't tooling at all — it's actually *running* the already-built scripts against a real k3d cluster** (which is exactly what the milestone's "locally-provable production readiness" direction already targets). The one genuinely new, low-cost, zero-new-dependency addition:

### Extend the trivy usage that already exists, from image-scan-only to IaC-config-scan

`infra/scripts/scan-images.sh` already wraps `trivy image --severity HIGH,CRITICAL` with a graceful degrade-if-absent / `REQUIRE_TRIVY=1` fail-closed-in-CI pattern. Trivy (already a project dependency, not a new tool) has a **second scanning mode** for exactly this milestone's remaining gap:

| Capability | Command | Catches |
|---|---|---|
| `trivy config` (misconfiguration scanner) | `trivy config infra/terraform infra/helm/clubcore` | Missing resource limits, privileged/root containers, missing NetworkPolicy, hardcoded secrets in Terraform/Helm, overly-permissive RBAC, deprecated/insecure Kubernetes API fields — across Terraform, Helm charts, and rendered Kubernetes manifests in one pass. Natively understands Helm charts and Terraform HCL — no need to pre-render with `helm template` first (though `trivy config <(helm template ...)` also works if a raw-manifest pass is preferred). |

**Integration:** add `infra/scripts/scan-iac.sh` mirroring the exact existing pattern in `scan-images.sh` (same graceful-degrade / `REQUIRE_TRIVY` semantics, same tool, zero new dependency to install or vet), and a `make scan-iac` target next to the existing `make scan`. This is the single highest-conviction (d) recommendation because it reuses an already-vetted tool with an already-proven integration pattern in this exact repo.

### What NOT to add for (d)

| Avoid | Why |
|---|---|
| `helm/chart-testing` (ct) — verified **v3.14.0** (2025-10-08) | `ct`'s main value (`ct lint`/`ct install` across **many changed charts** in a monorepo of charts, diffed against a target branch) doesn't apply — this project has exactly **one** umbrella chart. `ct install`'s "deploy into a live cluster and wait for readiness" is already superseded by the project's own `deploy-local.sh` + `smoke.sh`, which check project-specific behavior (WS upgrade, PWA cache headers) `ct` knows nothing about. Adding it would mean maintaining two partially-overlapping "does the chart actually deploy" mechanisms. |
| `kuttl` (KUbernetes Test TooL) — verified **v0.26.0** (2026-05-11) | Its natural application here is exactly what `restore-verify.sh` already does (declarative "apply this, assert that state") — but the existing bash script is *already* fail-closed, row-count-verified, and self-cleaning, i.e. **already exceeds** what a first-pass kuttl `TestAssert` (typically just "Cluster reaches Ready") would give. Porting a working, well-tested, project-specific script into a second declarative-YAML system fragments the source of truth for the milestone's most safety-critical script (BAK-03) without adding verification power. Not worth it in a convergence-focused milestone. |
| `tflint` | Marginal value here: its highest-value rulesets are cloud-provider-specific (AWS/GCP/Azure best practices), which don't apply to this project's on-prem/bare-metal `k3s` Terraform modules (`infra/terraform/{host,cluster}`). Its generic ruleset (unused declarations, deprecated syntax) has real but small value, largely superseded by adding `trivy config` (which also flags Terraform misconfigurations, with a tool already in the stack). Skip in favor of the trivy extension above; revisit only if `terraform validate` false-negatives are actually observed during the audit. |
| Velero | The project already has a complete, working backup mechanism (CNPG barman + Redis snapshot + SeaweedFS backup CronJobs + the verified restore script). Introducing a second, general-purpose backup tool would duplicate/compete with working infrastructure — pure scope growth for a milestone whose stated goal is hardening, not re-architecting backups. |
| Polaris / Datree / OPA-Gatekeeper / Conftest (policy-as-code engines) | These solve a multi-team, multi-cluster compliance-governance problem. This is a solo-maintainer, single-cluster, one-gym pet project; policy-as-code investment here is tooling the team (of one) will not act on repeatedly — directly the anti-pattern this research must avoid. `trivy config` already gives the highest-value subset (security misconfiguration) without a second policy DSL to learn. |
| kube-bench / kube-hunter (live-cluster security audit tools) | Require and target a **running production-like** cluster with a threat model beyond "is this locally provable" — explicitly out of scope per the milestone's own boundary (no real hardware, no production credentials). |
| Terratest (Go-based IaC test framework) | Steep new-language investment (Go) for a Python/TypeScript-only team, for value largely already covered by `terraform validate`/`terraform plan` + the trivy extension above. Not worth the maintenance-language sprawl in a convergence milestone. |

---

## Cross-Cutting: Sequencing Recommendation for the Roadmap

1. **Audit phase (read-only, seeds the DEFECT registry):** run Knip, jscpd, vulture, deptry once each (all one-shot, no CI wiring yet); run the Playwright route-sweep once against a live seeded backend; run `trivy config` once against `infra/`. Every finding becomes a DEFECT-registry row with severity + category + file, per the milestone's own stated audit-phase contract.
2. **Fix phase:** for every schema-drift fix, land it together with (a) the compile-time `AssertEqual` guard for that domain and (b) — if the domain doesn't already have one — a live-contract test per the existing v3.1 convention. This is the "contract-тест против РЕАЛЬНОГО ответа backend" the project has already decided on; this research just gives it two concrete, low-cost implementation mechanisms.
3. **Only after a clean baseline:** consider wiring Knip/jscpd/deptry as additional **steps inside the existing 5 CI jobs** (never new parallel jobs) — deptry is safe to wire immediately (low false-positive rate); Knip/jscpd should stay manual/local until the baseline is clean, given this repo's dynamic-import lazy routes and intentional per-domain repetition.
4. **Schemathesis** goes into the `backend` CI job as a new step (GET-only scope first) once the initial pass finds no destructive-endpoint side effects worth worrying about.
5. **Playwright route-sweep** and **trivy config / k3d validation** stay manual/on-demand tools used to *prove* the audit-phase findings are fixed — never new required PR gates. This keeps the existing 5-gate CI surface exactly as fast and deterministic as it is today, which matches the milestone's explicit call to converge, not grow.

## Version Compatibility

| Package A | Compatible with | Notes |
|---|---|---|
| `schemathesis@4.22.4` | `fastapi>=0.86.0`, `httpx<1.0,>=0.22.0`, `pytest-asyncio<2.0,>=1.0` | All already satisfied by the pinned backend stack (FastAPI 0.115+, httpx, pytest-asyncio per `CLAUDE.md`). |
| `@playwright/test@1.62.0` | Node >=20 | Matches the repo's pinned `engines.node >=20.0.0`. |
| `knip@6.20.0` | pnpm workspaces (native support), Vite, TypeScript 5.7 | No conflict with the repo's `typescript ~5.7.2` pin. |
| `AssertEqual`/`AssertNonNever` type-level checks | `zod@^3.24.1` (admin) | Pure TS type-level comparison; no runtime Zod version constraint. If `apps/client` ever adds `zod`, use the same major version to avoid `z.infer` shape differences between Zod 3/4. |
| `trivy config` | Existing pinned `trivy` install (`scan-images.sh`) | Same binary already used for `trivy image`; no separate install. |

## Sources

- npm registry (`@playwright/test`, `knip`, `jscpd`, `openapi-zod-client`, `orval`) — versions verified live, 2026-07-26.
- PyPI (`schemathesis`, `vulture`, `deptry`) — versions verified live, 2026-07-26.
- GitHub Releases (`helm/chart-testing`, `kudobuilder/kuttl`, `yannh/kubeconform`) — versions verified live, 2026-07-26.
- `schemathesis.readthedocs.io/en/latest/guides/python-apps/` — ASGI/FastAPI direct-testing pattern.
- `trivy.dev/docs/latest/coverage/iac/terraform/` + `aquasecurity/trivy` docs — `trivy config` misconfiguration-scanner capabilities.
- `knip.dev` (unused exports / monorepo support docs).
- Direct repo inspection (HIGH confidence, ground truth): `apps/admin/package.json`, `apps/client/package.json`, `apps/admin/src/api/client.ts`, `apps/admin/src/features/clients/{schemas,api}.ts`, `packages/api-client/src/schema.contract.test.ts`, `.github/workflows/ci.yml`, `Makefile`, `infra/scripts/{restore-verify,smoke,scan-images}.sh`, `infra/helm/clubcore/Chart.yaml`.

---
*Stack research for: v4.1 Codebase Hardening — mechanical defect-detection tooling*
*Researched: 2026-07-26*
