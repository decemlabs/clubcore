#!/usr/bin/env node
/**
 * merge-registry.mjs — concurrent-write merge for the v4.1 defect registry (D-122-04).
 *
 * The three audit sub-passes (1a static hygiene, 1b live-backend hunt, 1c infra triage) never
 * write `.planning/audits/v4.1-DEFECT-REGISTRY.md` directly. Each appends rows to its own
 * staging file under `.planning/audits/staging/`. This script reads all three staging files and
 * routes EACH ROW to a registry section by reading that row's own `category` column
 * (FUNC / HYGIENE / INFRA) — NOT by which staging file it came from. A single staging file may
 * legitimately hold rows of more than one category (e.g. sub-pass 1a produces both HYGIENE rows
 * and reachability-manifest rows whose category is FUNC).
 *
 * Guarantees:
 *   - Idempotent: re-running with unchanged staging input produces byte-identical registry output.
 *   - Preserves existing row IDs verbatim (never rewrites, renumbers, or reorders an ID).
 *   - Refuses to run if any two rows (anywhere across the three staging files) share an ID.
 *   - Asserts every emitted row's `category` column agrees with the registry section it lands
 *     under, erroring on any mismatch.
 *
 * Usage:
 *   node tools/audit/merge-registry.mjs              # merge staging -> registry
 *   node tools/audit/merge-registry.mjs --self-test   # run in-memory fixture routing tests
 *
 * See tools/audit/README.md for the full staging -> merge -> freeze protocol.
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..')
const STAGING_DIR = path.join(REPO_ROOT, '.planning/audits/staging')
const REGISTRY_PATH = path.join(REPO_ROOT, '.planning/audits/v4.1-DEFECT-REGISTRY.md')

const STAGING_FILES = ['1a-hygiene.md', '1b-live.md', '1c-infra.md']
const CATEGORIES = ['FUNC', 'HYGIENE', 'INFRA']
const COLUMN_COUNT = 11 // id, category, severity, anchor, repro, evidence, disposition,
// owning_phase, blocks/blocked_by, locked_invariant_risk, reason (D-122-03)

/** Split a single `| a | b | c |` markdown table line into trimmed cell strings. */
function splitRow(line) {
  let body = line.trim()
  if (body.startsWith('|')) body = body.slice(1)
  if (body.endsWith('|')) body = body.slice(0, -1)
  return body.split('|').map((c) => c.trim())
}

/**
 * Parse a staging file's markdown table into an array of row cell-arrays.
 * Skips the leading HTML comment, the header row, and the separator row.
 * Non-table lines reset the header/separator tracking (only one table is expected per file).
 */
function parseStagingRows(text, label) {
  const lines = text.split('\n')
  const rows = []
  let sawHeader = false
  let sawSeparator = false
  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line.startsWith('|')) {
      sawHeader = false
      sawSeparator = false
      continue
    }
    if (!sawHeader) {
      sawHeader = true
      continue
    }
    if (!sawSeparator) {
      sawSeparator = true
      continue
    }
    const cells = splitRow(line)
    if (cells.length !== COLUMN_COUNT) {
      throw new Error(
        `${label}: row does not have ${COLUMN_COUNT} columns (got ${cells.length}): ${line}`,
      )
    }
    rows.push(cells)
  }
  return rows
}

/**
 * Route rows (from multiple labeled staging sources) into their registry sections by each row's
 * own `category` column. Throws on duplicate IDs (across all sources) or unknown categories.
 */
function routeRows(rowsBySource) {
  const sections = { FUNC: [], HYGIENE: [], INFRA: [] }
  const seenIds = new Map() // id -> source label, for duplicate detection

  for (const [sourceLabel, rows] of rowsBySource) {
    for (const row of rows) {
      const [id, category] = row
      if (seenIds.has(id)) {
        throw new Error(
          `Duplicate row ID '${id}' found in both '${seenIds.get(id)}' and '${sourceLabel}'`,
        )
      }
      seenIds.set(id, sourceLabel)

      if (!CATEGORIES.includes(category)) {
        throw new Error(
          `Row '${id}' (from '${sourceLabel}') has unknown category '${category}' — must be one of ${CATEGORIES.join('/')}`,
        )
      }
      sections[category].push(row)
    }
  }

  assertSectionIntegrity(sections)
  return sections
}

/**
 * Assert every row placed in a section has a `category` column that matches that section's key.
 * This is the mechanical guard against a routing bug silently placing a row under the wrong
 * table — required even though correct routing makes this a no-op in the happy path.
 */
function assertSectionIntegrity(sections) {
  for (const category of CATEGORIES) {
    for (const row of sections[category]) {
      const [id, rowCategory] = row
      if (rowCategory !== category) {
        throw new Error(
          `Row '${id}' is placed under '## ${category}' but its category column reads '${rowCategory}'`,
        )
      }
    }
  }
}

function formatRow(cells) {
  return `| ${cells.join(' | ')} |`
}

/**
 * Rewrite the registry's three category table bodies (FUNC/HYGIENE/INFRA) with rows from
 * `sections`, preserving everything else (frontmatter, schema legend, table headers/separators,
 * the Discovered-during-fix section) byte-for-byte.
 */
function rebuildRegistry(originalText, sections) {
  const lines = originalText.split('\n')
  const output = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    output.push(line)
    const headingMatch = line.match(/^## (FUNC|HYGIENE|INFRA)$/)

    if (headingMatch) {
      const category = headingMatch[1]
      i++

      // Preserve blank lines between the heading and the table header.
      while (i < lines.length && lines[i].trim() === '') {
        output.push(lines[i])
        i++
      }

      // Table header row.
      if (i >= lines.length || !lines[i].trim().startsWith('|')) {
        throw new Error(`Expected table header immediately after '## ${category}' heading`)
      }
      output.push(lines[i])
      i++

      // Table separator row.
      if (i >= lines.length || !lines[i].trim().startsWith('|')) {
        throw new Error(`Expected table separator immediately after '## ${category}' header row`)
      }
      output.push(lines[i])
      i++

      // Skip any existing data rows — they are fully regenerated from staging below.
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        i++
      }

      for (const row of sections[category]) {
        output.push(formatRow(row))
      }
      continue // re-process lines[i] (blank line or next heading) on the next outer iteration
    }

    i++
  }

  return output.join('\n')
}

function runMerge() {
  const rowsBySource = STAGING_FILES.map((filename) => {
    const filePath = path.join(STAGING_DIR, filename)
    const text = fs.readFileSync(filePath, 'utf8')
    return [filename, parseStagingRows(text, filename)]
  })

  const sections = routeRows(rowsBySource)

  const originalRegistry = fs.readFileSync(REGISTRY_PATH, 'utf8')
  const updatedRegistry = rebuildRegistry(originalRegistry, sections)
  fs.writeFileSync(REGISTRY_PATH, updatedRegistry, 'utf8')

  const totalRows = CATEGORIES.reduce((sum, c) => sum + sections[c].length, 0)
  console.log(
    `merge-registry: wrote ${totalRows} row(s) ` +
      `(FUNC=${sections.FUNC.length}, HYGIENE=${sections.HYGIENE.length}, INFRA=${sections.INFRA.length})`,
  )
}

// ---------------------------------------------------------------------------
// Self-test: in-memory fixture, no filesystem writes.
// ---------------------------------------------------------------------------

function runSelfTest() {
  let failures = 0

  function check(name, fn) {
    try {
      fn()
      console.log(`  ok - ${name}`)
    } catch (err) {
      failures++
      console.error(`  FAIL - ${name}: ${err.message}`)
    }
  }

  console.log('merge-registry --self-test')

  // Fixture: a FUNC-category row occupying the 1a staging position (proves routing is by the
  // row's own `category` column, not by which staging file it came from), plus one HYGIENE row
  // in 1a and one INFRA row in 1c.
  const funcRowInStaging1a = [
    'V41-FUNC-999',
    'FUNC',
    'Minor',
    'apps/admin/src/app/router.tsx:1',
    'self-test repro',
    'self-test evidence',
    'open',
    '124',
    '—',
    'no',
    '',
  ]
  const hygRowInStaging1a = [
    'V41-HYG-999',
    'HYGIENE',
    'Minor',
    'apps/admin/src/App.tsx:1',
    'self-test repro',
    'self-test evidence',
    'open',
    '125',
    '—',
    'no',
    '',
  ]
  const infraRowInStaging1c = [
    'V41-INFRA-999',
    'INFRA',
    'Minor',
    'infra/runbooks/production.md:1',
    'self-test repro',
    'self-test evidence',
    'open',
    '126',
    '—',
    'no',
    '',
  ]

  check('FUNC row placed in 1a-hygiene.md routes to FUNC section', () => {
    const sections = routeRows([
      ['1a-hygiene.md (fixture)', [funcRowInStaging1a, hygRowInStaging1a]],
      ['1b-live.md (fixture)', []],
      ['1c-infra.md (fixture)', [infraRowInStaging1c]],
    ])
    if (!sections.FUNC.some((r) => r[0] === 'V41-FUNC-999')) {
      throw new Error('expected V41-FUNC-999 in sections.FUNC')
    }
    if (sections.HYGIENE.some((r) => r[0] === 'V41-FUNC-999')) {
      throw new Error('V41-FUNC-999 incorrectly routed to sections.HYGIENE')
    }
  })

  check('HYGIENE row placed in 1a-hygiene.md routes to HYGIENE section', () => {
    const sections = routeRows([
      ['1a-hygiene.md (fixture)', [funcRowInStaging1a, hygRowInStaging1a]],
      ['1b-live.md (fixture)', []],
      ['1c-infra.md (fixture)', []],
    ])
    if (!sections.HYGIENE.some((r) => r[0] === 'V41-HYG-999')) {
      throw new Error('expected V41-HYG-999 in sections.HYGIENE')
    }
  })

  check('INFRA row placed in 1c-infra.md routes to INFRA section', () => {
    const sections = routeRows([
      ['1a-hygiene.md (fixture)', []],
      ['1b-live.md (fixture)', []],
      ['1c-infra.md (fixture)', [infraRowInStaging1c]],
    ])
    if (!sections.INFRA.some((r) => r[0] === 'V41-INFRA-999')) {
      throw new Error('expected V41-INFRA-999 in sections.INFRA')
    }
  })

  check('duplicate row ID across staging files throws', () => {
    let threw = false
    try {
      routeRows([
        ['1a-hygiene.md (fixture)', [funcRowInStaging1a]],
        ['1b-live.md (fixture)', [funcRowInStaging1a]], // same ID, different source
        ['1c-infra.md (fixture)', []],
      ])
    } catch {
      threw = true
    }
    if (!threw) throw new Error('expected a duplicate-ID error to be thrown')
  })

  check('unknown category value throws', () => {
    const badRow = ['V41-BAD-001', 'NOT-A-CATEGORY', 'Minor', 'x', 'x', 'x', 'open', '123', '—', 'no', '']
    let threw = false
    try {
      routeRows([['fixture', [badRow]], ['fixture2', []], ['fixture3', []]])
    } catch {
      threw = true
    }
    if (!threw) throw new Error('expected an unknown-category error to be thrown')
  })

  check('a row whose section placement disagrees with its category column errors', () => {
    // Simulate a corrupted routing result: a row tagged FUNC deliberately placed under HYGIENE.
    const corrupted = {
      FUNC: [],
      HYGIENE: [['V41-FUNC-999', 'FUNC', 'Minor', 'x', 'x', 'x', 'open', '124', '—', 'no', '']],
      INFRA: [],
    }
    let threw = false
    try {
      assertSectionIntegrity(corrupted)
    } catch {
      threw = true
    }
    if (!threw) throw new Error('expected a category/section mismatch error to be thrown')
  })

  check('rebuildRegistry is idempotent for unchanged sections', () => {
    const fixtureRegistry = [
      '---',
      'milestone: v4.1',
      '---',
      '',
      '## FUNC',
      '',
      '| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |',
      '|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|',
      '',
      '## HYGIENE',
      '',
      '| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |',
      '|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|',
      '',
      '## INFRA',
      '',
      '| id | category | severity | anchor | repro | evidence | disposition | owning_phase | blocks/blocked_by | locked_invariant_risk | reason |',
      '|----|----------|----------|--------|-------|----------|--------------|---------------|--------------------|-------------------------|--------|',
      '',
      '## Discovered during fix',
      '',
    ].join('\n')

    const sections = { FUNC: [funcRowInStaging1a], HYGIENE: [], INFRA: [] }
    const once = rebuildRegistry(fixtureRegistry, sections)
    const twice = rebuildRegistry(once, sections)
    if (once !== twice) {
      throw new Error('rebuildRegistry is not idempotent on unchanged input')
    }
    if (!once.includes('V41-FUNC-999')) {
      throw new Error('rebuildRegistry did not emit the fixture row')
    }
  })

  if (failures > 0) {
    console.error(`\nmerge-registry --self-test: ${failures} check(s) FAILED`)
    process.exit(1)
  }
  console.log('\nmerge-registry --self-test: all checks passed')
}

// ---------------------------------------------------------------------------

const args = process.argv.slice(2)
if (args.includes('--self-test')) {
  runSelfTest()
} else {
  runMerge()
}
