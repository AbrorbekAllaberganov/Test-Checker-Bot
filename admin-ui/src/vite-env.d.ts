/// <reference types="vite/client" />

/**
 * `import.meta.env` uchun turlar.
 * Bu yerda faqat loyihada haqiqatda ishlatiladigan o'zgaruvchilar e'lon
 * qilinadi — noto'g'ri nom yozilsa TypeScript darrov ogohlantiradi.
 */
interface ImportMetaEnv {
  /** Backend manzili. Bo'sh bo'lsa so'rovlar nisbiy yo'l bilan ketadi. */
  readonly VITE_API_BASE_URL?: string
  /** Dev server proksi maqsadi (faqat `npm run dev` uchun). */
  readonly VITE_API_PROXY_TARGET?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
