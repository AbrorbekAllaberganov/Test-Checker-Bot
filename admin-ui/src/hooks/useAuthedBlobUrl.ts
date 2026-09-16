import { useEffect, useState } from 'react'

import { api } from '@/api/client'

interface AuthedBlobState {
  blobUrl: string | null
  /** Serverdan kelgan MIME (masalan `application/pdf`) — bo'sh bo'lishi mumkin. */
  contentType: string
  /** PDF bo'lsa `<img>` emas, `<iframe>` kerak. */
  isPdf: boolean
  loading: boolean
  error: boolean
}

/**
 * Auth talab qiladigan fayl URL'ini brauzer ichidagi blob URL'ga aylantiradi.
 *
 * Skan suratlari endi `/api/admin/scans/{id}/file/{kind}` dan keladi va
 * Bearer token talab qiladi. `<img src>` header yubora olmaydi — shu sababli
 * faylni axios (interceptor token qo'shadi, 401 da refresh qiladi) bilan
 * yuklab, `URL.createObjectURL` qilamiz. Komponent yo'qolganda yoki URL
 * o'zgarganda eski blob bo'shatiladi.
 *
 * Skan PDF ham bo'lishi mumkin (bot `application/pdf` hujjatni qabul qiladi) —
 * shu sababli MIME ham qaytariladi, chaqiruvchi PDF'ni `<iframe>` da
 * ko'rsatishi uchun.
 */
export function useAuthedBlobUrl(url: string | null | undefined): AuthedBlobState {
  const [state, setState] = useState<AuthedBlobState>({
    blobUrl: null,
    contentType: '',
    isPdf: false,
    loading: Boolean(url),
    error: false,
  })

  useEffect(() => {
    if (!url) {
      setState({ blobUrl: null, contentType: '', isPdf: false, loading: false, error: false })
      return
    }

    let cancelled = false
    let created: string | null = null
    setState({ blobUrl: null, contentType: '', isPdf: false, loading: true, error: false })

    api
      .get<Blob>(url, { responseType: 'blob' })
      .then((response) => {
        if (cancelled) return
        // `responseType: 'blob'` da header ham, blob.type ham MIME beradi;
        // proksi header'ni yo'qotsa ikkinchisi qoladi.
        const contentType = String(
          response.headers?.['content-type'] ?? response.data.type ?? '',
        ).toLowerCase()
        created = URL.createObjectURL(response.data)
        setState({
          blobUrl: created,
          contentType,
          isPdf: contentType.includes('pdf'),
          loading: false,
          error: false,
        })
      })
      .catch(() => {
        if (!cancelled) {
          setState({
            blobUrl: null,
            contentType: '',
            isPdf: false,
            loading: false,
            error: true,
          })
        }
      })

    return () => {
      cancelled = true
      if (created) URL.revokeObjectURL(created)
    }
  }, [url])

  return state
}
