import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/**
 * Some jsdom builds ship a localStorage object whose prototype methods
 * aren't reachable from our code. Install a plain in-memory shim keyed on
 * window so tests have a reliable Storage contract.
 */
function installLocalStorageShim() {
  const store = new Map<string, string>()
  const shim: Storage = {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? (store.get(key) as string) : null),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (key: string) => {
      store.delete(key)
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value))
    },
  }
  Object.defineProperty(window, 'localStorage', {
    value: shim,
    writable: true,
    configurable: true,
  })
}

installLocalStorageShim()

/**
 * jsdom does not implement the scrolling methods exposed by real browser
 * elements. Components schedule smooth scrolling in requestAnimationFrame,
 * so a busy full-suite run can execute that callback before cleanup and turn
 * an otherwise passing test into an unhandled TypeError.
 */
Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
  value: () => undefined,
  writable: true,
  configurable: true,
})

beforeEach(() => {
  // Reset persisted state between tests
  try {
    window.localStorage.clear()
  } catch {
    /* noop */
  }
  document.documentElement.className = ''
})

afterEach(() => {
  cleanup()
})
