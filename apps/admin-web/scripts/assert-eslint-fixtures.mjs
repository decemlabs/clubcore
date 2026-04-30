#!/usr/bin/env node
/**
 * Runs ESLint against src/__fixtures/* using scripts/eslint.fixtures.config.js and
 * asserts that each fixture trips the EXPECTED rule. If a fixture becomes clean,
 * the script fails — that means a guard-rail we rely on has silently stopped firing.
 *
 * Wired into `pnpm lint:fixtures`.
 */
import { ESLint } from 'eslint'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const ROOT = path.resolve(__dirname, '..')

/** @type {{ file: string; rule: string; }[]} */
const EXPECTED = [
  { file: 'src/__fixtures/raw-palette.tsx', rule: 'no-restricted-syntax' },
  { file: 'src/__fixtures/features/illegal-mock-import.ts', rule: 'import/no-restricted-paths' },
  { file: 'src/__fixtures/api-mode-leak.ts', rule: 'no-restricted-syntax' },
]

const eslint = new ESLint({
  overrideConfigFile: path.join(ROOT, 'scripts/eslint.fixtures.config.js'),
  cwd: ROOT,
})

let failed = false

for (const { file, rule } of EXPECTED) {
  const results = await eslint.lintFiles([file])
  const messages = results.flatMap((r) => r.messages)
  const hit = messages.some((m) => m.ruleId === rule)
  if (hit) {
    console.log(`OK   ${file} — triggered ${rule}`)
  } else {
    failed = true
    console.error(`FAIL ${file} — expected rule ${rule} to fire, got:`)
    for (const m of messages) {
      console.error(`       [${m.ruleId ?? '<parse>'}] ${m.message}`)
    }
    if (messages.length === 0) {
      console.error('       (no messages — fixture is clean, guard-rail may be broken)')
    }
  }
}

if (failed) {
  console.error('\nESLint fixture assertions FAILED — a lint rule we rely on is not firing.')
  process.exit(1)
}
console.log('\nAll ESLint fixtures triggered their expected rules.')
