/**
 * Phase-94 WR-07: secure-context-safe UUIDv4 generator.
 *
 * `crypto.randomUUID()` is only defined in secure contexts (HTTPS / localhost).
 * A PWA served over plain HTTP on a LAN IP for on-device testing, or an older
 * WebView, would otherwise throw `TypeError: crypto.randomUUID is not a function`
 * inside the message-send path — a silent hard failure that looks like a backend
 * error and leaves the user unable to send anything.
 *
 * Use this helper everywhere an idempotency key / client-side UUID is needed.
 */
export function uuidV4(): string {
  // Preferred path: native, cryptographically strong, available in secure contexts.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }

  // Fallback: RFC-4122 v4 using crypto.getRandomValues when available,
  // else Math.random (idempotency keys do not require crypto-grade randomness).
  const bytes = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes)
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256)
  }
  // Set version (4) and variant (10xx) bits. `?? 0` satisfies
  // noUncheckedIndexedAccess; indices 0..15 always exist on a 16-byte array.
  bytes[6] = ((bytes[6] ?? 0) & 0x0f) | 0x40
  bytes[8] = ((bytes[8] ?? 0) & 0x3f) | 0x80

  let hex = ''
  for (let i = 0; i < 16; i++) {
    hex += ((bytes[i] ?? 0) + 0x100).toString(16).slice(1)
  }
  return (
    hex.slice(0, 8) + '-' +
    hex.slice(8, 12) + '-' +
    hex.slice(12, 16) + '-' +
    hex.slice(16, 20) + '-' +
    hex.slice(20, 32)
  )
}
