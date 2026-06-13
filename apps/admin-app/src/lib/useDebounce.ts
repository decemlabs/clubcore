import { useEffect, useState } from 'react'

/**
 * Debounce hook — returns a debounced copy of `value` that only updates
 * after `delay` ms of inactivity (Phase 101 CLI-01: server-side search gate).
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
