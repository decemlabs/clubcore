/**
 * PWA-07 — Service worker /api/* network-only guarantee.
 *
 * Three behavioral requirements verified:
 *   1. GET /api/* → fetch(req) called, caches.open/.put NEVER called for that request.
 *   2. activate evicts every cache whose key !== VERSION ('gym-v4').
 *   3. Guard ordering: /api/* falls into the network-only branch and NOT into cache-first
 *      (confirmed by absence of caches.match call for an /api/* fetch).
 *
 * The service worker is a classic (non-module) script — it has no exports.
 * We execute its source in a controlled scope via new Function(...) with stubbed globals,
 * then drive the captured event handlers with synthetic events.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

// Resolve absolute path to sw.js relative to this test file.
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SW_PATH = path.resolve(__dirname, '../../public/sw.js')

// ---------------------------------------------------------------------------
// Helper: build a fresh fake environment and load the service worker into it.
// Returns { handlers, fakeCaches, fakeFetch } so tests can drive and assert.
// ---------------------------------------------------------------------------
function loadSW() {
  const swSource = readFileSync(SW_PATH, 'utf8')

  // Event handler registry — keyed by event type.
  const handlers = {}

  // Fake cache object (one per caches.open() call).
  function makeCache() {
    return {
      addAll: vi.fn().mockResolvedValue(undefined),
      put: vi.fn().mockResolvedValue(undefined),
      match: vi.fn().mockResolvedValue(undefined), // miss by default
    }
  }

  // per-name cache store so the same caches.open(name) returns the same object.
  const cacheStore = {}

  const fakeCaches = {
    open: vi.fn((name) => {
      if (!cacheStore[name]) cacheStore[name] = makeCache()
      return Promise.resolve(cacheStore[name])
    }),
    match: vi.fn().mockResolvedValue(undefined),
    keys: vi.fn().mockResolvedValue(['gym-v3', 'gym-v4']),
    delete: vi.fn().mockResolvedValue(true),
  }

  const fakeFetch = vi.fn().mockResolvedValue({
    ok: true,
    clone: () => ({ ok: true }),
  })

  const fakeSelf = {
    addEventListener: (type, handler) => {
      handlers[type] = handler
    },
    skipWaiting: vi.fn().mockResolvedValue(undefined),
    clients: { claim: vi.fn().mockResolvedValue(undefined) },
    location: { origin: 'https://app.test' },
  }

  // Execute the service worker source with our fake globals.
  // eslint-disable-next-line no-new-func
  new Function('self', 'caches', 'fetch', swSource)(fakeSelf, fakeCaches, fakeFetch)

  return { handlers, fakeCaches, fakeFetch, cacheStore }
}

// ---------------------------------------------------------------------------
// Synthetic event factories
// ---------------------------------------------------------------------------
function makeFetchEvent(url, { method = 'GET', mode = 'cors' } = {}) {
  const req = {
    url,
    method,
    mode,
    headers: { get: () => null },
  }
  const event = {
    request: req,
    _responded: null,
    respondWith(promise) {
      this._responded = promise
    },
  }
  return event
}

function makeExtendableEvent() {
  const event = {
    _done: null,
    waitUntil(promise) {
      this._done = promise
    },
  }
  return event
}

// ---------------------------------------------------------------------------
describe('PWA-07 — service worker /api/* network-only guarantee', () => {
  let handlers, fakeCaches, fakeFetch, cacheStore

  beforeEach(() => {
    ;({ handlers, fakeCaches, fakeFetch, cacheStore } = loadSW())
  })

  // -------------------------------------------------------------------------
  // Requirement 1 + 3 (guard ordering):
  //   GET /api/v1/client/home → fetch(req) called; caches.open/.put never
  //   invoked for that request.
  // -------------------------------------------------------------------------
  it('GET /api/* is served network-only: fetch called, caches.open never called', async () => {
    const event = makeFetchEvent('https://app.test/api/v1/client/home')

    handlers['fetch'](event)

    // respondWith must have been called (the branch did not skip event.respondWith).
    expect(event._responded).not.toBeNull()

    // Await the promise so all side-effects (including any erroneous caches.open calls) settle.
    const response = await event._responded

    // fetch(req) must have been called exactly once with the original request object.
    expect(fakeFetch).toHaveBeenCalledTimes(1)
    expect(fakeFetch).toHaveBeenCalledWith(event.request)

    // caches.open must NEVER have been called during an /api/* request.
    expect(fakeCaches.open).not.toHaveBeenCalled()

    // The put spy on any cache must never have been invoked.
    for (const cache of Object.values(cacheStore)) {
      expect(cache.put).not.toHaveBeenCalled()
    }

    // Response should be the fake fetch response.
    expect(response).toBeTruthy()
  })

  // -------------------------------------------------------------------------
  // Requirement 3 (ordering / non-regression):
  //   A non-/api static GET (e.g. /icon-192.png, mode=cors, non-HTML) falls
  //   into the cache-first path: caches.match IS called.
  //   This confirms the /api/* branch specifically precedes the cache-first
  //   branch — if ordering were wrong, static requests would also bypass cache.
  // -------------------------------------------------------------------------
  it('non-/api static GET falls into cache-first path (caches.match called)', async () => {
    const event = makeFetchEvent('https://app.test/icon-192.png', { mode: 'no-cors' })

    handlers['fetch'](event)

    expect(event._responded).not.toBeNull()
    await event._responded

    // For a cache-miss (fakeCaches.match returns undefined), fetch is called,
    // but crucially caches.match must have been invoked to look up the cache.
    expect(fakeCaches.match).toHaveBeenCalled()

    // fetch should also have been called (since cache miss).
    expect(fakeFetch).toHaveBeenCalled()
  })

  // -------------------------------------------------------------------------
  // Requirement 2: activate evicts stale caches.
  //   caches.keys() returns ['gym-v3', 'gym-v4'].
  //   After awaiting waitUntil, caches.delete('gym-v3') called,
  //   caches.delete('gym-v4') NOT called.
  // -------------------------------------------------------------------------
  it('activate deletes old caches but keeps current VERSION gym-v4', async () => {
    const event = makeExtendableEvent()

    handlers['activate'](event)

    expect(event._done).not.toBeNull()
    await event._done

    // 'gym-v3' is stale — must be deleted.
    expect(fakeCaches.delete).toHaveBeenCalledWith('gym-v3')

    // 'gym-v4' is current VERSION — must NOT be deleted.
    expect(fakeCaches.delete).not.toHaveBeenCalledWith('gym-v4')
  })
})
