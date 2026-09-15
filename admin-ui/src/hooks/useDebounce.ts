import { useEffect, useState } from 'react'

/**
 * Qiymatni kechiktirib qaytaradi.
 *
 * Qidiruv maydonida har harf uchun so'rov yubormaslik uchun ishlatiladi:
 * foydalanuvchi yozishni to'xtatganidan `delay` ms keyin qiymat yangilanadi.
 */
export function useDebounce<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debounced
}
