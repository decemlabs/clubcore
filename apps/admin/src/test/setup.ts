import '@testing-library/jest-dom/vitest';

// Node 25 + jsdom incompatibility: jsdom replaces globalThis.AbortController/AbortSignal
// with its own implementations, but globalThis.Request remains undici's (not replaced by jsdom).
// When React Router v6's data-router calls `new Request(url, { signal: jsdomAbortSignal })`,
// undici's Request constructor rejects jsdom's AbortSignal via a strict instanceof check
// against its internal (closure-scoped) AbortSignal class.
// Fix: replace globalThis.Request with a thin wrapper that strips the signal arg
// before delegating to undici's constructor. The smoke tests only verify that the
// component renders — they don't exercise request cancellation.
const _OriginalRequest = globalThis.Request;
class _PatchedRequest extends _OriginalRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init && 'signal' in init) {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { signal: _signal, ...rest } = init;
      super(input, rest);
    } else {
      super(input, init);
    }
  }
}
globalThis.Request = _PatchedRequest as unknown as typeof Request;

// jsdom не реализует эти API; страницы (Recharts, ScrollspyNav, use-mobile)
// требуют их при монтировании.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
globalThis.IntersectionObserver =
  IntersectionObserverStub as unknown as typeof IntersectionObserver;

if (!window.matchMedia) {
  window.matchMedia = ((_query: string) => ({
    matches: false,
    media: _query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
