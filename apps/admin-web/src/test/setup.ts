import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/**
 * Some jsdom builds ship a localStorage object whose prototype methods
 * aren't reachable from our code (persist middleware captures the instance
 * at module-load time). Install a plain in-memory shim keyed on window so
 * tests have a reliable Storage contract.
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
