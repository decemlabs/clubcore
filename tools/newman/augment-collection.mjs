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
 *
 * Cookie name note (load-bearing):
 *   CONTEXT.md/REQUIREMENTS.md incorrectly documented `cc_access`/`cc_refresh`.
 *   The real names (confirmed in apps/backend/app/core/security.py lines 223-254) are:
 *     sz_access      — httpOnly access token
 *     sz_refresh     — httpOnly refresh token
 *     sportzal_csrf  — non-httpOnly CSRF cookie (D-11-CSRF-DEFER carry-over; rename to
 *                      clubcore_csrf deferred to v2.0)
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

// Step 6 (write): byte-stable JSON.stringify + trailing newline (D-64-BYTE-STABLE)
const payload = JSON.stringify(collection, null, 2) + '\n'
fs.writeFileSync(OUTPUT, payload, 'utf-8')

console.log(`augment-collection: wrote ${OUTPUT}`)
console.log(`  folders: ${collection.item.map((f) => f.name).join(', ')}`)
console.log(`  variables: ${(collection.variable || []).map((v) => v.key).join(', ')}`)
const pmTestCount = (payload.match(/pm\.test\(/g) || []).length
const statusAssertCount = (payload.match(/pm\.response\.to\.have\.status/g) || []).length
console.log(`  pm.test() count: ${pmTestCount}`)
console.log(`  status assertions: ${statusAssertCount}`)
