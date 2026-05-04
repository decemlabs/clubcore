import { useEffect, useState } from 'react'

/**
 * Debounce a value by `delay` ms. Returns the most recently committed value;
 * resets the timer on every change.
 */
export function useDebounceValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}
