#!/usr/bin/env node
/**
 * tools/audit/zod-wire-manifest.mjs — Phase 122 (122-05), AUD-05 / D-122-08.
 *
 * Mechanical, one-pass static coverage manifest across all
 * `apps/admin/src/features/*` domains. Emits one row per
 * (feature domain, API call-site, Zod schema, backend endpoint,
 * capture-fixture present y/n, contract-test present y/n).
 *
 * SCOPE NOTE (122-05 modified scope, approved by user 2026-07-26):
 * This run is STATIC ONLY. The local docker-compose backend cannot be
 * seeded this session (owner seed creds are permission-protected), so
 * there is no edge-case dataset to hit live and no captured response
 * bytes to diff against. This script therefore does NOT make any network
 * calls and does NOT compute divergences. It builds the coverage grid —
 * which call-sites exist, which Zod schema each parses through, whether
 * a capture/ fixture dir exists, whether a *.contract.test.ts exists —
 * and cross-references the call-site path against apps/backend/openapi.json
 * for REFERENCE ONLY (D-122-10: openapi.json is never the divergence
 * baseline; captured response bytes are — and that comparison is the
 * part deferred to a seeded re-run, rowed honestly in 1b-live.md).
 *
 * No Zod-codegen dependency introduced (orval/openapi-zod-client/zodios
 * banned per D-122-08 anti-feature list). Regex/string-scan based —
 * no ts-morph/AST dependency added; parsing-strategy discretion per
 * 122-CONTEXT.md "Claude's Discretion".
 */

import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(__dirname, '..', '..')
const FEATURES_DIR = join(REPO_ROOT, 'apps', 'admin', 'src', 'features')
const OPENAPI_PATH = join(REPO_ROOT, 'apps', 'backend', 'openapi.json')
const OUT_MD = join(REPO_ROOT, '.planning', 'audits', 'v4.1-ZOD-WIRE-MANIFEST.md')
const OUT_JSON = join(REPO_ROOT, '.planning', 'audits', 'v4.1-ZOD-WIRE-MANIFEST.json')

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isDir(p) {
  try {
    return statSync(p).isDirectory()
  } catch {
    return false
  }
}

/** Recursively list files under a directory (skip node_modules/dist, only .ts/.tsx). */
function listSourceFiles(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (isDir(full)) {
      if (entry === 'node_modules' || entry === 'dist') continue
      listSourceFiles(full, acc)
    } else if (/\.(ts|tsx)$/.test(entry)) {
      acc.push(full)
    }
  }
  return acc
}

/** Load apps/backend/openapi.json path set (reference-only cross-check, D-122-10). */
function loadOpenapiPaths() {
  if (!existsSync(OPENAPI_PATH)) return new Set()
  try {
    const raw = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'))
    return new Set(Object.keys(raw.paths ?? {}))
  } catch {
    return new Set()
  }
}

/**
 * Scan file content for staffRequest(...) call-sites.
 * Handles both single-line and multi-line call forms:
 *   staffRequest('get', '/api/v1/x', {...})
 *   staffRequest(
 *     'patch',
 *     '/api/v1/x/{id}',
 *     {...}
 *   )
 * Also tolerates `'patch' as never` / `'/path' as never` casts (auth domain).
 */
function findStaffRequestCallSites(content, relFile) {
  const sites = []
  const re =
    /staffRequest\(\s*['"](get|post|patch|put|delete)['"]\s*(?:as\s+never)?\s*,\s*['"]([^'"]+)['"]\s*(?:as\s+never)?/g
  let m
  while ((m = re.exec(content)) !== null) {
    const method = m[1]
    const endpoint = m[2]
    const lineNum = content.slice(0, m.index).split('\n').length
    // Look ahead up to 400 chars for a `.parse(` schema-name reference —
    // this is the mechanical (not perfect) proximity heuristic for pairing
    // the call-site with the Zod schema it validates through.
    const windowEnd = Math.min(content.length, m.index + 500)
    const window = content.slice(m.index, windowEnd)
    const parseMatch = window.match(/(\w+Schema)\.parse\(/)
    sites.push({
      file: relFile,
      line: lineNum,
      method: method.toUpperCase(),
      endpoint,
      schema: parseMatch ? parseMatch[1] : null,
    })
  }
  return sites
}

/** Scan file content for mockResponse(...) usage — marks a domain as mock-only if no staffRequest exists.
 *  Tolerates a generic type argument: `mockResponse<BranchesData>(...)`. */
function usesMockResponse(content) {
  return /\bmockResponse(?:<[^>]*>)?\(/.test(content)
}

/** Detect `import/export { ... } from '@/features/<other>/api'` delegation pattern.
 *  Anchored on a preceding `}` so JSDoc prose mentioning the same import path
 *  (e.g. "for colocation with LoadPage (import from '@/features/load/api', ...)")
 *  is not mistaken for a real delegation edge. */
function findDelegations(content, ownDomain) {
  const targets = new Set()
  const re = /}\s*from\s+['"]@\/features\/([\w-]+)\/api['"]/g
  let m
  while ((m = re.exec(content)) !== null) {
    if (m[1] !== ownDomain) targets.add(m[1])
  }
  return [...targets]
}

// ---------------------------------------------------------------------------
// Main walk
// ---------------------------------------------------------------------------

function main() {
  const openapiPaths = loadOpenapiPaths()
  const domains = readdirSync(FEATURES_DIR)
    .filter((d) => isDir(join(FEATURES_DIR, d)))
    .sort()

  const rows = []
  const domainSummaries = []

  for (const domain of domains) {
    const domainDir = join(FEATURES_DIR, domain)
    const files = listSourceFiles(domainDir)
    const relFiles = files.map((f) => f.slice(REPO_ROOT.length + 1))

    const captureDirPresent = isDir(join(domainDir, 'capture'))
    const contractTestFiles = relFiles.filter((f) => f.endsWith('.contract.test.ts'))
    const contractTestPresent = contractTestFiles.length > 0
    const schemasFilePresent = existsSync(join(domainDir, 'schemas.ts'))

    let callSites = []
    let delegatesTo = new Set()
    let mockOnly = false

    for (const f of files) {
      if (/\.test\.(ts|tsx)$/.test(f) || f.endsWith('.contract.test.ts')) continue
      if (f.includes(`${domain}/capture/`) || f.includes(`${domain}\\capture\\`)) continue
      const content = readFileSync(f, 'utf8')
      const relFile = f.slice(REPO_ROOT.length + 1)
      const sites = findStaffRequestCallSites(content, relFile)
      callSites.push(...sites)
      for (const t of findDelegations(content, domain)) delegatesTo.add(t)
      if (usesMockResponse(content)) mockOnly = true
    }

    // Wiring classification (informational column, not in the plan's locked
    // 6-column schema but useful triage context carried in the .json only).
    let wiring
    if (callSites.length > 0) wiring = 'real-backend'
    else if (delegatesTo.size > 0) wiring = `delegates-to:${[...delegatesTo].join(',')}`
    else if (mockOnly) wiring = 'mock-only'
    else wiring = 'static-no-query'

    if (callSites.length === 0) {
      // Still emit one manifest row for the domain so all 29 domains are
      // covered even when there is no direct call-site (delegated/mock/static).
      rows.push({
        domain,
        call_site: wiring === 'mock-only' || wiring === 'static-no-query' ? '(none — ' + wiring + ')' : '(none — ' + wiring + ')',
        method: null,
        endpoint: null,
        zod_schema: schemasFilePresent ? '(schemas.ts present, unused by call-site)' : '(no schemas.ts)',
        backend_endpoint_ref: null,
        capture_fixture_present: captureDirPresent ? 'y' : 'n',
        contract_test_present: contractTestPresent ? 'y' : 'n',
        wiring,
      })
    } else {
      for (const site of callSites) {
        const backendMatch = openapiPaths.has(site.endpoint)
        rows.push({
          domain,
          call_site: `${site.file}:${site.line}`,
          method: site.method,
          endpoint: site.endpoint,
          zod_schema: site.schema ?? (schemasFilePresent ? '(no .parse() paired within window)' : '(no schemas.ts)'),
          backend_endpoint_ref: backendMatch
            ? `openapi.json: ${site.method} ${site.endpoint} (present, reference-only)`
            : `openapi.json: NO MATCH for ${site.method} ${site.endpoint} (reference-only, not a divergence claim)`,
          capture_fixture_present: captureDirPresent ? 'y' : 'n',
          contract_test_present: contractTestPresent ? 'y' : 'n',
          wiring,
        })
      }
    }

    domainSummaries.push({
      domain,
      call_site_count: callSites.length,
      capture_fixture_present: captureDirPresent,
      contract_test_present: contractTestPresent,
      contract_test_files: contractTestFiles,
      wiring,
    })
  }

  // ---------------------------------------------------------------------
  // Emit JSON
  // ---------------------------------------------------------------------
  const gapDomains = domainSummaries.filter((d) => !d.capture_fixture_present || !d.contract_test_present)
  const patternDomains = domainSummaries.filter((d) => d.capture_fixture_present && d.contract_test_present)

  const json = {
    generated_at: new Date().toISOString(),
    generated_by: 'tools/audit/zod-wire-manifest.mjs',
    scope: 'STATIC ONLY — no live backend hit this run (122-05 modified scope; see SUMMARY)',
    domain_count: domains.length,
    domains_with_capture_and_contract_test: patternDomains.map((d) => d.domain),
    domains_missing_pattern: gapDomains.map((d) => d.domain),
    rows,
    domain_summaries: domainSummaries,
  }
  writeFileSync(OUT_JSON, JSON.stringify(json, null, 2) + '\n', 'utf8')

  // ---------------------------------------------------------------------
  // Emit Markdown
  // ---------------------------------------------------------------------
  const lines = []
  lines.push('# v4.1 Zod↔Wire Coverage Manifest')
  lines.push('')
  lines.push('**Phase:** 122-audit-registry-producing-read-only-pass (plan 122-05, AUD-05 / D-122-08/09)')
  lines.push(`**Generated:** ${json.generated_at}`)
  lines.push('**Generator:** `node tools/audit/zod-wire-manifest.mjs`')
  lines.push('')
  lines.push(
    '**SCOPE (modified, 122-05):** This manifest is STATIC coverage only. It does NOT hit the ' +
      'live backend and does NOT compute runtime divergences — the local docker-compose backend ' +
      'is up but could not be seeded this session (owner seed credentials are permission-protected), ' +
      'so there is no edge-case dataset to capture response bytes from. The runtime Zod↔wire ' +
      'divergence check (comparing captured live bytes against these schemas, D-122-10) is DEFERRED ' +
      '— see `.planning/audits/staging/1b-live.md` rows `V41-FUNC` for the honest deferred entries. ' +
      'The `apps/backend/openapi.json` cross-reference column below is reference-only, never a ' +
      'divergence baseline (D-122-10).',
  )
  lines.push('')
  lines.push(
    `**Ground truth (this run):** ${domains.length} feature domains walked. ` +
      `${patternDomains.length} have the full capture-fixture + contract-test pattern: ` +
      `${patternDomains.map((d) => d.domain).join(', ')}. ` +
      `${gapDomains.length} domains lack one or both — see the Coverage Gaps table below. ` +
      'This supersedes the roadmap\'s "~25/~20" estimate (D-122-09) with the measured number.',
  )
  lines.push('')
  lines.push('## Per-call-site manifest (one row per feature domain × API call-site)')
  lines.push('')
  lines.push(
    '| domain | call-site | method | endpoint | zod schema | backend endpoint (reference only) | capture-fixture present | contract-test present |',
  )
  lines.push('|---|---|---|---|---|---|---|---|')
  for (const r of rows) {
    lines.push(
      `| ${r.domain} | ${r.call_site} | ${r.method ?? '—'} | ${r.endpoint ?? '—'} | ${r.zod_schema} | ${r.backend_endpoint_ref ?? '—'} | ${r.capture_fixture_present} | ${r.contract_test_present} |`,
    )
  }
  lines.push('')
  lines.push('## Domain summary (the definitive Phase-124 input list, D-122-09)')
  lines.push('')
  lines.push('| domain | call-sites | capture-fixture present | contract-test present | wiring |')
  lines.push('|---|---|---|---|---|')
  for (const d of domainSummaries) {
    lines.push(
      `| ${d.domain} | ${d.call_site_count} | ${d.capture_fixture_present ? 'y' : 'n'} | ${d.contract_test_present ? 'y' : 'n'} | ${d.wiring} |`,
    )
  }
  lines.push('')
  lines.push('## Coverage gaps (domains lacking the full capture-fixture + contract-test pattern)')
  lines.push('')
  lines.push(`${gapDomains.length} of ${domains.length} domains — this is the Phase-124 FUNC-01 work list.`)
  lines.push('')
  lines.push('| domain | missing |')
  lines.push('|---|---|')
  for (const d of gapDomains) {
    const missing = []
    if (!d.capture_fixture_present) missing.push('capture-fixture')
    if (!d.contract_test_present) missing.push('contract-test')
    lines.push(`| ${d.domain} | ${missing.join(', ')} |`)
  }
  lines.push('')
  lines.push('## Deferred: runtime divergence check (AUD-05 empirical layer, D-122-10)')
  lines.push('')
  lines.push(
    'Not run this session — no seeded edge-case dataset available (see SCOPE above). ' +
      'Rowed as `deferred:blocked` in `.planning/audits/staging/1b-live.md`.',
  )
  lines.push('')

  writeFileSync(OUT_MD, lines.join('\n'), 'utf8')

  console.log(`Wrote ${OUT_MD}`)
  console.log(`Wrote ${OUT_JSON}`)
  console.log(`Domains walked: ${domains.length}`)
  console.log(`Full pattern (capture+contract-test): ${patternDomains.length} — ${patternDomains.map((d) => d.domain).join(', ')}`)
  console.log(`Gap domains: ${gapDomains.length}`)
}

main()
