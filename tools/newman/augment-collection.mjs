/**
 * augment-collection.mjs — Phase 65 Postman collection post-processor (D-65-AUGMENT)
 *
 * Reads tools/newman/base-collection.json (produced by `pnpm postman:gen`)
 * and writes the final .planning/handoff/v1.11-clubcore.postman_collection.json.
 *
 * Transformations applied (byte-stable on re-run per D-64-BYTE-STABLE):
 *   1. Remove the "Internal" folder (webhook + healthz) — D-46-08 / T-65-06
 *   2. Set collection-level variables: baseUrl, accessToken, csrfToken (placeholders)
 *   3. Inject collection-root prerequest event: X-CSRF-Token on every non-GET request
 *   4. Inject Login request test event: extract sportzal_csrf → csrfToken collection var
 *   5. Inject pm.response.to.have.status(...) on every request item
 *   6. Inject per-domain body-shape pm.test() on auth happy-path + 1 representative GET per domain
 *   7. Emit curated smoke folder (D-65-SMOKE-SCOPE, HND-04):
 *        login → auth/me → one safe GET per domain → idempotency replay pair
 *
 * Cookie name note (load-bearing):
 *   CONTEXT.md/REQUIREMENTS.md incorrectly documented `cc_access`/`cc_refresh`.
 *   The real names (confirmed in apps/backend/app/core/security.py lines 223-254) are:
 *     sz_access      — httpOnly access token
 *     sz_refresh     — httpOnly refresh token
 *     sportzal_csrf  — non-httpOnly CSRF cookie (D-11-CSRF-DEFER carry-over; rename to
 *                      clubcore_csrf deferred to v2.0)
 *
 * Smoke folder (D-65-SMOKE-SCOPE):
 *   Curated happy-path subset for `pnpm newman run --folder smoke`:
 *     1. Login (POST /api/v1/auth/login) — uses {{ownerEmail}} / {{password}} env vars;
 *        captures sportzal_csrf into csrfToken collection variable.
 *     2. GET /api/v1/auth/me — confirms session active.
 *     3. One safe GET per business domain (Users, Clients, Memberships, Visits, Schedule,
 *        Bookings, Trainers, Payments, Reports, Audit-log).
 *     4. Idempotency replay pair (POST /api/v1/memberships, Category-A, already-wired):
 *        - idem-1: first call with a deterministic Idempotency-Key; asserts status stored.
 *        - idem-2: replay call with SAME key + body; asserts exact same status (verbatim replay).
 *        Note: placeholder clientId/planId produce a 404 AppError on first call, which the
 *        idempotency middleware caches (IDM-06 AppError branch). The second call returns the
 *        verbatim cached 404 — proving the replay path is live. No DB mutation occurs.
 *   EXCLUDED: refunds, sells, destructive mutations (D-65-SMOKE-SCOPE).
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..')
const INPUT = path.join(REPO_ROOT, 'tools', 'newman', 'base-collection.json')
const OUTPUT = path.join(REPO_ROOT, '.planning', 'handoff', 'v1.11-clubcore.postman_collection.json')

// ---------------------------------------------------------------------------
// Expected success status per request name / method heuristics
// ---------------------------------------------------------------------------

/**
 * Derive expected HTTP success status from a request item's response examples.
 * Falls back to 201 for resource-creating POSTs, 200 for everything else.
 */
function expectedStatus(item) {
  const responses = item.response || []
  for (const r of responses) {
    if (r.code && r.code >= 200 && r.code < 300) {
      return r.code
    }
  }
  // Fallback heuristic
  const method = item.request?.method?.toUpperCase() || 'GET'
  return method === 'POST' ? 201 : 200
}

// ---------------------------------------------------------------------------
// Body-shape assertions (HND-03) — per representative request
// ---------------------------------------------------------------------------
// Map: url path suffix → assertion type
// 'list'  → pagination envelope { items (array), total (number) }
// 'data'  → { data } wrapper
// 'login' → auth envelope { email, role } (login response)
// 'me'    → { data } wrapper (single-resource auth/me)

const BODY_SHAPE_MAP = {
  // Auth happy-path
  '/api/v1/auth/login': 'login',
  '/api/v1/auth/me': 'me',
  // Business domains — one representative safe GET per domain
  '/api/v1/users': 'list',
  '/api/v1/clients': 'list',
  '/api/v1/membership-plans': 'list',
  '/api/v1/visits': 'list',
  '/api/v1/recurring-templates': 'list',
  '/api/v1/bookings': 'list',
  '/api/v1/trainers': 'list',
  '/api/v1/payments': 'list',
  '/api/v1/reports/clients': 'report',
  '/api/v1/audit-log': 'list',
}

/**
 * Return pm.test() body-shape assertion lines for a given shape type.
 * Returns [] if no body-shape assertion applies to this request.
 */
function bodyShapeLines(shapeType) {
  if (shapeType === 'list') {
    return [
      'pm.test("response has pagination envelope", function () {',
      '  const json = pm.response.json();',
      '  pm.expect(json).to.have.property("items").that.is.an("array");',
      '  pm.expect(json).to.have.property("total").that.is.a("number");',
      '});',
    ]
  }
  if (shapeType === 'data' || shapeType === 'me') {
    return [
      'pm.test("response has data wrapper", function () {',
      '  const json = pm.response.json();',
      '  pm.expect(json).to.have.property("data");',
      '});',
    ]
  }
  if (shapeType === 'login') {
    return [
      'pm.test("login response has expected fields", function () {',
      '  const json = pm.response.json();',
      '  pm.expect(json).to.have.property("email");',
      '  pm.expect(json).to.have.property("role");',
      '});',
      '// Extract sportzal_csrf cookie into csrfToken collection variable.',
      '// The sz_access and sz_refresh cookies are httpOnly — Postman\'s cookie jar',
      '// carries them automatically; we only need to capture sportzal_csrf for the',
      '// CSRF double-submit pattern (D-11-CSRF-DEFER). accessToken is derived from',
      '// the sz_access cookie in the jar (no manual extraction needed).',
      'const csrfCookie = pm.cookies.get("sportzal_csrf");',
      'if (csrfCookie) {',
      '  pm.collectionVariables.set("csrfToken", csrfCookie);',
      '  pm.collectionVariables.set("accessToken", csrfCookie); // marker: session active',
      '}',
    ]
  }
  if (shapeType === 'report') {
    return [
      'pm.test("report response has items array", function () {',
      '  const json = pm.response.json();',
      '  pm.expect(json).to.have.property("items").that.is.an("array");',
      '});',
    ]
  }
  return []
}

// ---------------------------------------------------------------------------
// URL path extractor
// ---------------------------------------------------------------------------
function getRawUrl(item) {
  return item.request?.url?.raw || ''
}

/**
 * Derive the canonical path from a request item.
 * The openapi-to-postmanv2 generator may or may not populate url.raw; fall back
 * to reconstructing the path from url.host + url.path arrays.
 *
 * Returns e.g. "/api/v1/clients" (no query string, no baseUrl prefix).
 */
function extractPath(item) {
  const url = item.request?.url
  if (!url) return ''

  // Prefer url.raw when available
  if (url.raw) {
    let raw = url.raw.replace(/^\{\{baseUrl\}\}/, '')
    const qi = raw.indexOf('?')
    if (qi !== -1) raw = raw.substring(0, qi)
    return raw
  }

  // Reconstruct from url.path array (filtering out path-param segments like ":id")
  const pathSegs = (url.path || []).filter(
    (seg) => typeof seg === 'string' && !seg.startsWith(':'),
  )
  if (pathSegs.length > 0) {
    return '/' + pathSegs.join('/')
  }
  return ''
}

// ---------------------------------------------------------------------------
// Walk all request items recursively
// ---------------------------------------------------------------------------
function walkRequests(items, visitor) {
  for (const item of items) {
    if (item.request) {
      visitor(item)
    }
    if (item.item) {
      walkRequests(item.item, visitor)
    }
  }
}

// ---------------------------------------------------------------------------
// Ensure an event slot exists (upsert by listen type)
// ---------------------------------------------------------------------------
function ensureEvent(item, listenType) {
  if (!item.event) item.event = []
  let ev = item.event.find((e) => e.listen === listenType)
  if (!ev) {
    ev = { listen: listenType, script: { type: 'text/javascript', exec: [] } }
    item.event.push(ev)
  }
  if (!ev.script) ev.script = { type: 'text/javascript', exec: [] }
  if (!ev.script.exec) ev.script.exec = []
  return ev
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
const raw = fs.readFileSync(INPUT, 'utf-8')
const collection = JSON.parse(raw)

// Step 1: Remove "Internal" folder (T-65-06 / D-46-08) and deduplicate tag folders.
// The openapi-to-postmanv2 generator creates duplicate tag folders when an operation
// has both "Reports" and "reports" tags (case-sensitive distinct folders in the tool).
// Dedup: keep first occurrence of each folder name (case-insensitive); remove "Internal".
{
  const seen = new Set()
  collection.item = collection.item.filter((f) => {
    const key = (f.name || '').toLowerCase()
    if (key === 'internal') return false // always exclude internal (T-65-06)
    if (seen.has(key)) return false // deduplicate case-variant duplicates
    seen.add(key)
    return true
  })
}

// Step 2: Set collection-level variables (merge with any existing baseUrl)
const existingVars = collection.variable || []
const varMap = Object.fromEntries(existingVars.map((v) => [v.key, v]))
const desiredVars = [
  { key: 'baseUrl', value: 'http://localhost:8000', type: 'default' },
  { key: 'accessToken', value: '', type: 'secret' },
  { key: 'csrfToken', value: '', type: 'secret' },
]
for (const dv of desiredVars) {
  if (!varMap[dv.key]) {
    varMap[dv.key] = dv
  } else {
    // keep existing value but ensure type is correct
    varMap[dv.key].type = dv.type
  }
}
// Preserve original order, then append new keys
const knownKeys = new Set(existingVars.map((v) => v.key))
const newKeys = desiredVars.filter((dv) => !knownKeys.has(dv.key))
collection.variable = [
  ...existingVars.map((v) => varMap[v.key]),
  ...newKeys.map((dv) => varMap[dv.key]),
]

// Step 3: Inject collection-root prerequest event (CSRF header for non-GET requests)
{
  if (!collection.event) collection.event = []
  let preReq = collection.event.find((e) => e.listen === 'prerequest')
  if (!preReq) {
    preReq = { listen: 'prerequest', script: { type: 'text/javascript', exec: [] } }
    collection.event.push(preReq)
  }
  if (!preReq.script) preReq.script = { type: 'text/javascript', exec: [] }
  if (!preReq.script.exec) preReq.script.exec = []

  // Only inject if not already present (byte-stable on re-run)
  const joined = preReq.script.exec.join('\n')
  if (!joined.includes('X-CSRF-Token')) {
    preReq.script.exec = [
      '// D-65-AUGMENT: Auto-inject X-CSRF-Token on every non-GET request.',
      '// The sportzal_csrf double-submit cookie (D-11-CSRF-DEFER) is captured into',
      '// the csrfToken collection variable by the Login request test script.',
      "if (pm.request.method !== 'GET') {",
      "  const csrf = pm.collectionVariables.get('csrfToken');",
      '  if (csrf) {',
      "    pm.request.headers.add({ key: 'X-CSRF-Token', value: csrf });",
      '  }',
      '}',
    ]
  }
}

// Steps 4 + 5 + 6: Walk all requests and inject assertions
walkRequests(collection.item, (item) => {
  const method = (item.request?.method || 'GET').toUpperCase()
  const rawUrl = getRawUrl(item)
  const urlPath = extractPath(item)
  const status = expectedStatus(item)

  // Step 5: Ensure test event with status assertion
  const testEv = ensureEvent(item, 'test')
  const joinedTest = testEv.script.exec.join('\n')

  // Step 4: Login cookie extraction (handle in the same test event)
  const isLoginRequest =
    method === 'POST' &&
    (urlPath === '/api/v1/auth/login' ||
      item.name === 'Login' ||
      rawUrl.endsWith('/auth/login') ||
      (item.request?.url?.path || []).join('/').endsWith('auth/login'))

  // Body-shape assertion for this URL (if any)
  // Only apply body-shape to the first GET of each domain path (exact match)
  const shapeType = BODY_SHAPE_MAP[urlPath]
  // For login, also apply on POST
  const wantsBodyShape =
    shapeType !== undefined &&
    (method === 'GET' || urlPath === '/api/v1/auth/login')

  // Rebuild exec only if needed (byte-stable: only rebuild if assertions not yet present)
  const hasStatusAssert = joinedTest.includes('pm.response.to.have.status')
  const hasCsrfExtract = joinedTest.includes('sportzal_csrf')
  const hasBodyShape = joinedTest.includes('pm.test(')

  if (!hasStatusAssert || (isLoginRequest && !hasCsrfExtract) || (wantsBodyShape && !hasBodyShape)) {
    const lines = []

    // Status assertion (always present)
    lines.push(`pm.response.to.have.status(${status});`)

    // Login-specific: sportzal_csrf extraction
    if (isLoginRequest && !hasCsrfExtract) {
      const loginShapeLines = bodyShapeLines('login')
      lines.push(...loginShapeLines)
    } else if (wantsBodyShape && !hasBodyShape) {
      // Body-shape assertion for the representative domain GET
      const shapeLines = bodyShapeLines(shapeType)
      lines.push(...shapeLines)
    }

    testEv.script.exec = lines
  }
})

// ---------------------------------------------------------------------------
// Step 7: Emit curated smoke folder (D-65-SMOKE-SCOPE / HND-04)
// ---------------------------------------------------------------------------
// The smoke folder is a top-level additive folder (not a sub-folder of any
// domain). It is idempotent: if a folder named "smoke" already exists it is
// removed and rebuilt from scratch so re-running is byte-stable.
//
// Smoke request list (documented per T-65-11 — coverage must not be silently
// truncated):
//   1.  Login — POST /api/v1/auth/login ({{ownerEmail}}/{{password}} env vars)
//   2.  Me    — GET  /api/v1/auth/me
//   3a. Users list         — GET /api/v1/users
//   3b. Clients list       — GET /api/v1/clients
//   3c. Membership-plans list — GET /api/v1/membership-plans
//   3d. Visits list        — GET /api/v1/visits
//   3e. Recurring-templates list — GET /api/v1/recurring-templates
//   3f. Bookings list      — GET /api/v1/bookings
//   3g. Trainers list      — GET /api/v1/trainers
//   3h. Payments list      — GET /api/v1/payments
//   3i. Reports/clients    — GET /api/v1/reports/clients
//   3j. Audit-log          — GET /api/v1/audit-log
//   4a. Idempotency replay first  — POST /api/v1/memberships (Idempotency-Key: idem-smoke-replay-01)
//   4b. Idempotency replay second — POST /api/v1/memberships (same key; asserts same status)
//
// EXCLUDED (D-65-SMOKE-SCOPE): refunds, sells, destructive mutations.
{
  // Remove any pre-existing smoke folder (idempotent rebuild)
  collection.item = collection.item.filter((f) => (f.name || '').toLowerCase() !== 'smoke')

  // Helper: build a minimal Postman v2.1 GET request item
  function makeGetItem(name, path) {
    return {
      name,
      request: {
        method: 'GET',
        url: {
          raw: '{{baseUrl}}' + path,
          host: ['{{baseUrl}}'],
          path: path.replace(/^\//, '').split('/'),
          query: [],
          variable: [],
        },
        header: [{ key: 'Accept', value: 'application/json' }],
        auth: null,
      },
      event: [
        {
          listen: 'test',
          script: {
            type: 'text/javascript',
            exec: ['pm.response.to.have.status(200);'],
          },
        },
      ],
    }
  }

  // 1. Login (uses {{ownerEmail}} / {{password}} env vars from Newman smoke env)
  const smokeLogin = {
    name: 'smoke: Login ({{ownerEmail}})',
    description: 'D-65-SMOKE-SCOPE step 1: authenticate with fixture credentials from Newman smoke env. Captures sportzal_csrf into csrfToken collection variable for subsequent CSRF-protected requests.',
    request: {
      method: 'POST',
      url: {
        raw: '{{baseUrl}}/api/v1/auth/login',
        host: ['{{baseUrl}}'],
        path: ['api', 'v1', 'auth', 'login'],
        query: [],
        variable: [],
      },
      header: [
        { key: 'Content-Type', value: 'application/json' },
        { key: 'Accept', value: 'application/json' },
      ],
      body: {
        mode: 'raw',
        raw: '{\n  "email": "{{ownerEmail}}",\n  "password": "{{password}}"\n}',
        options: { raw: { headerFamily: 'json', language: 'json' } },
      },
      auth: null,
    },
    event: [
      {
        listen: 'test',
        script: {
          type: 'text/javascript',
          exec: [
            'pm.response.to.have.status(200);',
            'pm.test("login response has expected fields", function () {',
            '  const json = pm.response.json();',
            '  pm.expect(json).to.have.property("email");',
            '  pm.expect(json).to.have.property("role");',
            '});',
            '// Extract sportzal_csrf cookie into csrfToken collection variable.',
            '// The sz_access and sz_refresh cookies are httpOnly — cookie jar carries them.',
            'const csrfCookie = pm.cookies.get("sportzal_csrf");',
            'if (csrfCookie) {',
            '  pm.collectionVariables.set("csrfToken", csrfCookie);',
            '  pm.collectionVariables.set("accessToken", csrfCookie);',
            '}',
          ],
        },
      },
    ],
  }

  // 2. GET /api/v1/auth/me — confirm session
  const smokeMe = makeGetItem('smoke: Auth/Me (session check)', '/api/v1/auth/me')

  // 3. One safe GET per business domain
  const smokeDomainGets = [
    makeGetItem('smoke: Users list', '/api/v1/users'),
    makeGetItem('smoke: Clients list', '/api/v1/clients'),
    makeGetItem('smoke: Membership-plans list', '/api/v1/membership-plans'),
    makeGetItem('smoke: Visits list', '/api/v1/visits'),
    makeGetItem('smoke: Recurring-templates list', '/api/v1/recurring-templates'),
    makeGetItem('smoke: Bookings list', '/api/v1/bookings'),
    makeGetItem('smoke: Trainers list', '/api/v1/trainers'),
    makeGetItem('smoke: Payments list', '/api/v1/payments'),
    makeGetItem('smoke: Reports/clients', '/api/v1/reports/clients'),
    makeGetItem('smoke: Audit-log list', '/api/v1/audit-log'),
  ]

  // 4a. Idempotency replay — first call
  // Uses Category-A endpoint POST /api/v1/memberships (create_membership, already-wired).
  // Placeholder client/plan UUIDs produce a 404 AppError → cached by idempotency middleware
  // (IDM-06 AppError branch). No DB mutation on 404. Key is deterministic for byte-stability.
  // The SAME Idempotency-Key is reused in 4b to demonstrate verbatim replay.
  const SMOKE_IDEM_KEY = 'smoke-idem-replay-01-v1.11'
  const SMOKE_IDEM_BODY = JSON.stringify(
    {
      clientId: '00000000-0000-4000-8000-000000000001',
      planId: '00000000-0000-4000-8000-000000000002',
    },
    null,
    2,
  )

  const smokeIdem1 = {
    name: 'smoke: idem-1 — create_membership first call (captures status)',
    description: 'D-65-SMOKE-SCOPE step 4a: first call to Category-A POST /api/v1/memberships with deterministic Idempotency-Key. Placeholder IDs produce a 404 AppError cached by the idempotency middleware (IDM-06 AppError branch). No DB mutation. Captures response status in smokeIdemStatus collection variable for replay assertion.',
    request: {
      method: 'POST',
      url: {
        raw: '{{baseUrl}}/api/v1/memberships',
        host: ['{{baseUrl}}'],
        path: ['api', 'v1', 'memberships'],
        query: [],
        variable: [],
      },
      header: [
        { key: 'Content-Type', value: 'application/json' },
        { key: 'Accept', value: 'application/json' },
        { key: 'Idempotency-Key', value: SMOKE_IDEM_KEY },
      ],
      body: {
        mode: 'raw',
        raw: SMOKE_IDEM_BODY,
        options: { raw: { headerFamily: 'json', language: 'json' } },
      },
      auth: null,
    },
    event: [
      {
        listen: 'test',
        script: {
          type: 'text/javascript',
          exec: [
            '// idem-1: capture first-call status for replay assertion in idem-2.',
            '// Expected: 404 plan_not_found (placeholder UUIDs; AppError → cached).',
            '// The idempotency middleware stores this response so idem-2 returns verbatim.',
            'pm.test("idem-1 returns a status that will be cached for replay", function () {',
            '  pm.expect(pm.response.code).to.be.oneOf([200, 201, 404, 409, 422]);',
            '});',
            'pm.collectionVariables.set("smokeIdemStatus", pm.response.code);',
            'pm.collectionVariables.set("smokeIdemBody", pm.response.text());',
          ],
        },
      },
    ],
  }

  // 4b. Idempotency replay — second call (SAME key + SAME body)
  const smokeIdem2 = {
    name: 'smoke: idem-2 — create_membership replay (same key, asserts verbatim)',
    description: 'D-65-SMOKE-SCOPE step 4b: replay of idem-1 with SAME Idempotency-Key and SAME body. The backend must return the verbatim cached response (same status + body) without re-executing the handler. Asserts replay status == idem-1 status and body == idem-1 body (T-65-11 verbatim replay proof).',
    request: {
      method: 'POST',
      url: {
        raw: '{{baseUrl}}/api/v1/memberships',
        host: ['{{baseUrl}}'],
        path: ['api', 'v1', 'memberships'],
        query: [],
        variable: [],
      },
      header: [
        { key: 'Content-Type', value: 'application/json' },
        { key: 'Accept', value: 'application/json' },
        { key: 'Idempotency-Key', value: SMOKE_IDEM_KEY },
      ],
      body: {
        mode: 'raw',
        raw: SMOKE_IDEM_BODY,
        options: { raw: { headerFamily: 'json', language: 'json' } },
      },
      auth: null,
    },
    event: [
      {
        listen: 'test',
        script: {
          type: 'text/javascript',
          exec: [
            '// idem-2: replay with same Idempotency-Key + same body.',
            '// The idempotency middleware must return the verbatim cached response.',
            'const expectedStatus = pm.collectionVariables.get("smokeIdemStatus");',
            'const expectedBody = pm.collectionVariables.get("smokeIdemBody");',
            'pm.test("idem-2 replay returns same status as idem-1 (verbatim replay)", function () {',
            '  pm.expect(pm.response.code).to.equal(Number(expectedStatus));',
            '});',
            'pm.test("idem-2 replay returns same body as idem-1 (verbatim replay)", function () {',
            '  pm.expect(pm.response.text()).to.equal(expectedBody);',
            '});',
          ],
        },
      },
    ],
  }

  // Assemble smoke folder
  const smokeFolder = {
    name: 'smoke',
    description: [
      'D-65-SMOKE-SCOPE / HND-04: Curated Newman smoke harness. Run via `pnpm newman run --folder smoke`.',
      '',
      'Coverage (14 requests):',
      '  1.  Login (POST /api/v1/auth/login) — fixture credentials via {{ownerEmail}}/{{password}} Newman env vars',
      '  2.  GET /api/v1/auth/me — session confirmation',
      '  3a. GET /api/v1/users',
      '  3b. GET /api/v1/clients',
      '  3c. GET /api/v1/membership-plans',
      '  3d. GET /api/v1/visits',
      '  3e. GET /api/v1/recurring-templates',
      '  3f. GET /api/v1/bookings',
      '  3g. GET /api/v1/trainers',
      '  3h. GET /api/v1/payments',
      '  3i. GET /api/v1/reports/clients',
      '  3j. GET /api/v1/audit-log',
      '  4a. POST /api/v1/memberships [Idempotency-Key: smoke-idem-replay-01-v1.11] — first call',
      '  4b. POST /api/v1/memberships [Idempotency-Key: smoke-idem-replay-01-v1.11] — replay (same key+body)',
      '',
      'SCOPE (D-65-SMOKE-SCOPE): safe GETs + one idempotency replay only.',
      'Financial mutations and destructive operations are outside scope.',
      'Prerequisites: docker compose up + seed_verification_fixtures.py (SEED_VERIFY_OWNER_PASSWORD set).',
      'Invoke: SEED_VERIFY_OWNER_PASSWORD=<pwd> pnpm newman run --env-var "password=$SEED_VERIFY_OWNER_PASSWORD" --folder smoke',
      '',
      'Local handoff smoke only — not a CI gate (D-11-NEWMAN-LOCAL).',
    ].join('\n'),
    item: [smokeLogin, smokeMe, ...smokeDomainGets, smokeIdem1, smokeIdem2],
  }

  // Append smoke folder at the end of collection.item (additive, not replacing domains)
  collection.item.push(smokeFolder)
}

// Step 7 (write): byte-stable JSON.stringify + trailing newline (D-64-BYTE-STABLE)
const payload = JSON.stringify(collection, null, 2) + '\n'
fs.writeFileSync(OUTPUT, payload, 'utf-8')

console.log(`augment-collection: wrote ${OUTPUT}`)
console.log(`  folders: ${collection.item.map((f) => f.name).join(', ')}`)
console.log(`  variables: ${(collection.variable || []).map((v) => v.key).join(', ')}`)
const pmTestCount = (payload.match(/pm\.test\(/g) || []).length
const statusAssertCount = (payload.match(/pm\.response\.to\.have\.status/g) || []).length
console.log(`  pm.test() count: ${pmTestCount}`)
console.log(`  status assertions: ${statusAssertCount}`)
const reportedSmokeFolder = collection.item.find((f) => f.name === 'smoke')
console.log(
  `  smoke folder requests: ${reportedSmokeFolder ? reportedSmokeFolder.item.length : 'MISSING'}`,
)
