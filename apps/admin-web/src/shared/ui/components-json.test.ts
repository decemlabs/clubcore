import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

interface ComponentsJson {
  $schema?: string
  style: string
  rsc: boolean
  tsx: boolean
  tailwind: {
    config: string
    css: string
    baseColor: string
    cssVariables: boolean
    prefix: string
  }
  aliases: Record<string, string>
  iconLibrary: string
  registries?: Record<string, string>
}

const raw = readFileSync(resolve(__dirname, '../../../components.json'), 'utf8')
const json = JSON.parse(raw) as ComponentsJson

describe('components.json lock', () => {
  it('uses the base-nova style and neutral base color', () => {
    expect(json.style).toBe('base-nova')
    expect(json.tailwind.baseColor).toBe('neutral')
  })

  it('points Tailwind CSS at src/app/index.css with cssVariables=true', () => {
    expect(json.tailwind.css).toBe('src/app/index.css')
    expect(json.tailwind.cssVariables).toBe(true)
  })

  it('binds aliases to the FSD-lite shared tree', () => {
    expect(json.aliases.components).toBe('@/shared/ui')
    expect(json.aliases.ui).toBe('@/shared/ui')
    expect(json.aliases.lib).toBe('@/shared/lib')
    expect(json.aliases.utils).toBe('@/shared/lib/cn')
    expect(json.aliases.hooks).toBe('@/shared/lib/hooks')
  })

  it('uses lucide as the icon library', () => {
    expect(json.iconLibrary).toBe('lucide')
  })

  it('registers the @reui registry', () => {
    expect(json.registries?.['@reui']).toBe('https://reui.io/r/{style}/{name}.json')
  })
})
