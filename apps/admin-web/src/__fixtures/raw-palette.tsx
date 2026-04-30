// FIXTURE: must trigger `no-restricted-syntax` raw-palette rule.
// Run via scripts/assert-eslint-fixtures.mjs.
import * as React from 'react'

export function RawPaletteFixture() {
  void React
  return (
    <div className="bg-white text-slate-900">
      <span className={`bg-blue-500 text-white`}>nope</span>
    </div>
  )
}
