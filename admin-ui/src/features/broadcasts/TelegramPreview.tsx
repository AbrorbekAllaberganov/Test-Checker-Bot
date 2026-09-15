import { useMemo } from 'react'

/**
 * Telegram xabarining taxminiy ko'rinishi.
 *
 * XAVFSIZLIK: matn admin tomonidan yoziladi, lekin baribir `innerHTML`
 * ishlatmaymiz — teglarni O'ZIMIZ ajratib, faqat Telegram qo'llaydigan
 * to'plamni (b/i/u/s/code/a) React elementiga aylantiramiz. Shu bilan
 * <script> yoki onerror kabi narsalar hech qachon bajarilmaydi.
 */

/** Telegram qo'llab-quvvatlaydigan inline teglar. */
const ALLOWED = new Set(['b', 'strong', 'i', 'em', 'u', 's', 'code', 'pre', 'a'])

type Node = string | { tag: string; href?: string; children: Node[] }

function parse(input: string): Node[] {
  const root: { tag: string; href?: string; children: Node[] } = {
    tag: 'root',
    children: [],
  }
  const stack = [root]
  const tagPattern = /<(\/?)([a-zA-Z]+)((?:\s+href="[^"]*")?)\s*>/g

  let lastIndex = 0
  let match: RegExpExecArray | null

  function push(node: Node) {
    stack[stack.length - 1]!.children.push(node)
  }

  while ((match = tagPattern.exec(input)) !== null) {
    const [full, closing, rawTag, attrs] = match
    const tag = rawTag!.toLowerCase()

    if (match.index > lastIndex) {
      push(input.slice(lastIndex, match.index))
    }
    lastIndex = match.index + full.length

    if (!ALLOWED.has(tag)) {
      // Ruxsat etilmagan teg — oddiy matn sifatida ko'rsatiladi.
      push(full)
      continue
    }

    if (closing) {
      // Faqat mos ochilgan teg bo'lsa yopamiz.
      if (stack.length > 1 && stack[stack.length - 1]!.tag === tag) {
        stack.pop()
      }
    } else {
      const hrefMatch = attrs?.match(/href="([^"]*)"/)
      const node = {
        tag,
        href: hrefMatch?.[1],
        children: [] as Node[],
      }
      push(node)
      stack.push(node)
    }
  }

  if (lastIndex < input.length) push(input.slice(lastIndex))
  return root.children
}

function render(nodes: Node[], keyPrefix = ''): React.ReactNode[] {
  return nodes.map((node, index) => {
    const key = `${keyPrefix}-${index}`

    if (typeof node === 'string') {
      // Qator uzilishlarini saqlaymiz.
      return <span key={key}>{node}</span>
    }

    const children = render(node.children, key)

    switch (node.tag) {
      case 'b':
      case 'strong':
        return <strong key={key}>{children}</strong>
      case 'i':
      case 'em':
        return <em key={key}>{children}</em>
      case 'u':
        return <u key={key}>{children}</u>
      case 's':
        return <s key={key}>{children}</s>
      case 'code':
      case 'pre':
        return (
          <code key={key} className="rounded bg-black/20 px-1 py-0.5 text-[11px]">
            {children}
          </code>
        )
      case 'a':
        // Havola ko'rsatiladi, lekin bosilmaydi — bu faqat ko'rinish.
        return (
          <span key={key} className="text-sky-300 underline" title={node.href}>
            {children}
          </span>
        )
      default:
        return <span key={key}>{children}</span>
    }
  })
}

export function TelegramPreview({
  title,
  body,
}: {
  title: string
  body: string
}) {
  const content = useMemo(() => {
    const text = title.trim() ? `<b>${title}</b>\n\n${body}` : body
    return render(parse(text))
  }, [title, body])

  return (
    <div className="rounded-lg bg-[#17212b] p-4">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-[#2b5278] px-3 py-2">
        {body.trim() || title.trim() ? (
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-white">
            {content}
          </p>
        ) : (
          <p className="text-sm italic text-white/50">Xabar matni bu yerda ko'rinadi…</p>
        )}
      </div>
    </div>
  )
}
