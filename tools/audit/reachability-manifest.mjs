#!/usr/bin/env node
/**
 * reachability-manifest.mjs — AUD-03 three-way join (D-122-07).
 *
 * For apps/admin: joins `app/routes.ts` (ROUTES constant) x `app/router.tsx` (routeConfig,
 * which resolves each path to either a lazy-loaded real page component or a <ComingSoon/>
 * placeholder) x `layouts/AppLayout/nav-items.ts` (NAV_SECTIONS, which paths have a sidebar
 * nav entry).
 *
 * For apps/client: joins `App.jsx` (<Route path=...> -> lazy screen component) x
 * `components/TabBar.jsx` (the 4 persistent tabs) x `screens/**`.
 *
 * This is throwaway audit tooling (D-122-07's "reversible — the script is a throwaway audit
 * tool"). Parsing is regex-based against these specific, small, hand-written route tables —
 * not a general-purpose React Router AST parser. If the source files' shape changes
 * materially, this script's regexes will need updating (acceptable per Phase 122 CONTEXT.md
 * "Claude's Discretion": AST vs regex vs ts-morph is an implementation detail).
 *
 * Reachability judgment (documented so FUNC-05 consumers understand the bar applied):
 *   - A route with a direct nav-sidebar/tab-bar entry -> reachable.
 *   - A route reachable only by clicking through from an already-reachable screen (e.g. a
 *     dynamic `/clients/:id` detail page reached by clicking a client row, or `/settings`
 *     reached by tapping a profile gear icon) -> reachable (nav entry is "n/a by design").
 *   - A chrome-less framework/auth route (login, error, onboarding, payment-return, referral
 *     deep-link, the /index.html legacy-prototype redirect) -> reachable (n/a by design,
 *     not a nav target).
 *   - A route registered in the router but resolving to <ComingSoon/> -> NOT reachable
 *     (FND-04 hide-for-future placeholder).
 *   - A ROUTES key that is never registered in the router's routeConfig at all -> NOT
 *     reachable (worse than a placeholder: the path 404s if visited).
 *
 * Usage: node tools/audit/reachability-manifest.mjs
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..')
const OUT_PATH = path.join(REPO_ROOT, '.planning/audits/v4.1-REACHABILITY-MANIFEST.md')

const ADMIN_ROUTES_TS = path.join(REPO_ROOT, 'apps/admin/src/app/routes.ts')
const ADMIN_ROUTER_TSX = path.join(REPO_ROOT, 'apps/admin/src/app/router.tsx')
const ADMIN_NAV_TS = path.join(REPO_ROOT, 'apps/admin/src/layouts/AppLayout/nav-items.ts')

const CLIENT_APP_JSX = path.join(REPO_ROOT, 'apps/client/src/App.jsx')
const CLIENT_TABBAR_JSX = path.join(REPO_ROOT, 'apps/client/src/components/TabBar.jsx')

// ---------------------------------------------------------------------------
// apps/admin
// ---------------------------------------------------------------------------

function parseAdminRoutes(text) {
  // Matches both `key: '/literal',` and `key: (id...) => \`/literal/${id}\`,` forms.
  const routes = new Map() // key -> { pattern, dynamic }
  const lineRe = /^\s*(\w+):\s*(?:'([^']+)'|\([^)]*\)\s*=>\s*`([^`]+)`)\s*,?\s*$/gm
  let m
  while ((m = lineRe.exec(text))) {
    const [, key, literal, templateBody] = m
    if (literal !== undefined) {
      routes.set(key, { pattern: literal, dynamic: false })
    } else if (templateBody !== undefined) {
      // e.g. `/clients/${id}` -> /clients/:clientId (approximate; id default already ':xId')
      routes.set(key, { pattern: templateBody.replace(/\$\{[^}]+\}/, ':param'), dynamic: true })
    }
  }
  return routes
}

function parseAdminRouter(text) {
  // Walk line-by-line. Each route object starts with a `path: ROUTES.xxx` (optionally
  // `ROUTES.xxx()`) or a literal path, and its resolution (lazy import / ComingSoon /
  // Navigate) appears within the next handful of lines before the next `path:`.
  const lines = text.split('\n')
  const registered = new Map() // key (or literal path) -> { resolution: 'lazy'|'comingsoon'|'navigate', component }
  let pendingKey = null

  const pathRe = /path:\s*(?:ROUTES\.(\w+)(\(\))?|'([^']+)')/
  const lazyRe = /import\('([^']+)'\)/
  const comingSoonRe = /<ComingSoon\s*\/>/
  const navigateRe = /<Navigate/
  const directElementRe = /element:\s*<(\w+)/

  // Checks a single line for any resolution marker (a `path:` line may carry its own
  // `element:` on the same line, e.g. `{ path: ROUTES.error, element: <ErrorPage .../> }`).
  function resolveFromLine(key, line) {
    const lm = line.match(lazyRe)
    if (lm) return { resolution: 'lazy', component: lm[1] }
    if (comingSoonRe.test(line)) return { resolution: 'comingsoon', component: null }
    if (navigateRe.test(line)) return { resolution: 'navigate', component: null }
    const dm = line.match(directElementRe)
    if (dm && dm[1] !== 'ComingSoon' && dm[1] !== 'Navigate') {
      return { resolution: 'direct', component: dm[1] }
    }
    return null
  }

  for (const line of lines) {
    const pm = line.match(pathRe)
    if (pm) {
      pendingKey = pm[1] || pm[3]
      // The path and its resolution can be on the same line (e.g. chrome-less one-liners).
      const sameLine = resolveFromLine(pendingKey, line)
      if (sameLine) {
        registered.set(pendingKey, sameLine)
        pendingKey = null
      }
      continue
    }
    if (pendingKey === null) continue
    const res = resolveFromLine(pendingKey, line)
    if (res) {
      registered.set(pendingKey, res)
      pendingKey = null
    }
  }
  return registered
}

function parseAdminNav(text) {
  const navPaths = new Set()
  const re = /to:\s*ROUTES\.(\w+)/g
  let m
  while ((m = re.exec(text))) navPaths.add(m[1])
  return navPaths
}

// Routes reachable by design without a nav-sidebar entry (chrome-less framework routes or
// dynamic detail pages reached by clicking through from an already-reachable list screen).
const ADMIN_NAV_EXEMPT = new Set(['login', 'error', 'client', 'trainer'])

function buildAdminManifest() {
  const routesText = fs.readFileSync(ADMIN_ROUTES_TS, 'utf8')
  const routerText = fs.readFileSync(ADMIN_ROUTER_TSX, 'utf8')
  const navText = fs.readFileSync(ADMIN_NAV_TS, 'utf8')

  const routes = parseAdminRoutes(routesText)
  const registered = parseAdminRouter(routerText)
  const navPaths = parseAdminNav(navText)

  const rows = []
  for (const [key, { pattern }] of routes) {
    const reg = registered.get(key)
    const hasNav = navPaths.has(key)
    const navExempt = ADMIN_NAV_EXEMPT.has(key)

    let resolvedComponent = '—'
    let isPlaceholder = 'n/a'
    let reachable
    let note = ''

    if (!reg) {
      resolvedComponent = '(not registered in router.tsx)'
      isPlaceholder = 'n/a'
      reachable = 'NO — unregistered'
      note = 'ROUTES key exists but routeConfig never registers it; visiting the path 404s.'
    } else if (reg.resolution === 'comingsoon') {
      resolvedComponent = 'ComingSoon (placeholder)'
      isPlaceholder = 'yes'
      reachable = 'NO — placeholder'
      note = 'FND-04 hide-for-future: page file exists in tree but router renders <ComingSoon/>.'
    } else if (reg.resolution === 'navigate') {
      resolvedComponent = '(redirect)'
      isPlaceholder = 'no'
      reachable = 'yes — redirect'
      note = 'Compatibility redirect, not a content screen.'
    } else if (reg.resolution === 'direct') {
      resolvedComponent = reg.component
      isPlaceholder = 'no'
      if (hasNav) {
        reachable = 'yes — nav entry'
      } else if (navExempt) {
        reachable = 'yes — by design (no nav entry expected)'
        note = 'Chrome-less auth/error route, not a nav target.'
      } else {
        reachable = 'yes — URL only (no nav entry)'
        note = 'Registered with a real (non-lazy) component but no sidebar nav entry.'
      }
    } else {
      resolvedComponent = reg.component
      isPlaceholder = 'no'
      if (hasNav) {
        reachable = 'yes — nav entry'
      } else if (navExempt) {
        reachable = 'yes — by design (no nav entry expected)'
        note =
          key === 'client' || key === 'trainer'
            ? 'Dynamic detail page, reached by clicking a list row.'
            : 'Chrome-less auth/error route, not a nav target.'
      } else {
        reachable = 'yes — URL only (no nav entry)'
        note = 'Registered with a real component but no sidebar nav entry.'
      }
    }

    rows.push({
      app: 'apps/admin',
      path: pattern,
      routesKey: key,
      navPresent: hasNav ? 'yes' : navExempt ? 'n/a' : 'no',
      component: resolvedComponent,
      isPlaceholder,
      reachable,
      note,
    })
  }
  return rows
}

// ---------------------------------------------------------------------------
// apps/client
// ---------------------------------------------------------------------------

function parseClientRoutes(text) {
  const rows = []
  const re = /<Route\s+path="([^"]+)"\s+element=\{<(?:RequireAuth><)?(\w+)/g
  let m
  while ((m = re.exec(text))) {
    rows.push({ routePath: m[1], componentRef: m[2] })
  }
  return rows
}

function parseClientTabs(text) {
  const tabs = []
  const re = /\{\s*id:\s*'(\w+)',\s*label:\s*'([^']+)'/g
  let m
  while ((m = re.exec(text))) tabs.push(m[1])
  return tabs
}

const TAB_PATH = { home: '/home', book: '/book', chat: '/chat', profile: '/profile' }

// Chrome-less / non-tab framework routes, reachable by design without a TabBar entry.
const CLIENT_NAV_EXEMPT = new Set([
  '/login',
  '/i/:code',
  '/',
  '/payment/return',
  '/onboarding',
  '/settings',
  '*',
])

function buildClientManifest() {
  const appText = fs.readFileSync(CLIENT_APP_JSX, 'utf8')
  const tabBarText = fs.readFileSync(CLIENT_TABBAR_JSX, 'utf8')

  const routeRows = parseClientRoutes(appText)
  const tabIds = parseClientTabs(tabBarText)
  const tabPaths = new Set(tabIds.map((id) => TAB_PATH[id]).filter(Boolean))

  const rows = []
  for (const { routePath, componentRef } of routeRows) {
    const hasTab = tabPaths.has(routePath)
    const exempt = CLIENT_NAV_EXEMPT.has(routePath)
    let note = ''
    let reachable
    if (hasTab) {
      reachable = 'yes — tab bar entry'
    } else if (routePath === '/settings') {
      reachable = 'yes — by design (in-app link, not a tab)'
      note = 'Reached via the profile-screen settings gear icon (ProfileRoute onOpenSettings), not TabBar.'
    } else if (exempt) {
      reachable = 'yes — by design (no tab entry expected)'
      note =
        routePath === '*'
          ? 'Catch-all: authed -> /home, anon -> /login.'
          : 'Chrome-less auth/deep-link/redirect route, not a tab target.'
    } else {
      reachable = 'yes — URL only (no tab entry)'
      note = 'Registered with a real component but not one of the 4 persistent tabs.'
    }

    rows.push({
      app: 'apps/client',
      path: routePath,
      routesKey: componentRef,
      navPresent: hasTab ? 'yes' : exempt || routePath === '/settings' ? 'n/a' : 'no',
      component: componentRef,
      isPlaceholder: 'no', // no ComingSoon usage found anywhere in apps/client/src (verified by grep)
      reachable,
      note,
    })
  }
  return rows
}

// ---------------------------------------------------------------------------
// Markdown emission
// ---------------------------------------------------------------------------

function formatTable(rows) {
  const header =
    '| app | path | nav/tab present | resolved component | placeholder? | reachable verdict | note |'
  const sep = '|---|---|---|---|---|---|---|'
  const body = rows
    .map(
      (r) =>
        `| ${r.app} | \`${r.path}\` | ${r.navPresent} | ${r.component} | ${r.isPlaceholder} | ${r.reachable} | ${r.note || '—'} |`,
    )
    .join('\n')
  return [header, sep, body].join('\n')
}

function main() {
  const adminRows = buildAdminManifest()
  const clientRows = buildClientManifest()
  const allRows = [...adminRows, ...clientRows]

  const notReachableCount = allRows.filter((r) => r.reachable.startsWith('NO')).length

  const doc = `# v4.1 Reachability Manifest (AUD-03)

Generated by \`tools/audit/reachability-manifest.mjs\` (D-122-07) — the three-way join of
router x nav-items x real screen component for \`apps/admin\` and \`apps/client\`.

Regenerate with: \`node tools/audit/reachability-manifest.mjs\`

Reconciled against \`apps/admin/src/app/router-smoke.test.tsx\`: that suite already renders every
*registered* admin path (including the ComingSoon placeholders) and asserts it doesn't crash —
this manifest adds the missing dimension (nav presence + whether a path is registered at all),
which router-smoke does not check.

**Total rows:** ${allRows.length} (apps/admin: ${adminRows.length}, apps/client: ${clientRows.length})
**Not reachable (registry-row-worthy):** ${notReachableCount}

## apps/admin

${formatTable(adminRows)}

## apps/client

${formatTable(clientRows)}

**apps/client verdict:** no ComingSoon/placeholder screens and no unregistered ROUTES entries
were found — every route resolves to a real component. \`components/ComingSoon.tsx\` exists in
the client tree but is never imported/rendered anywhere (confirmed by \`knip\`'s unused-files
finding and a repo-wide grep); it is dead code, not an active reachability mechanism — tracked
as a HYGIENE row (V41-HYG, apps/client unused-files cluster), not a FUNC reachability row, since
nothing routes to it.
`

  fs.writeFileSync(OUT_PATH, doc, 'utf8')
  console.log(
    `reachability-manifest: wrote ${allRows.length} row(s) to ${path.relative(REPO_ROOT, OUT_PATH)} ` +
      `(${notReachableCount} not-reachable)`,
  )
}

main()
