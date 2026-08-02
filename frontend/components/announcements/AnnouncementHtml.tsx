'use client'

import { useMemo } from 'react'
import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3',
  'ul', 'ol', 'li', 'a', 'img', 'hr', 'span', 'div',
]

const ALLOWED_ATTR = ['href', 'target', 'rel', 'src', 'alt', 'title', 'class', 'style', 'loading']

export function sanitizeAnnouncementHtml(html: string): string {
  return DOMPurify.sanitize(html || '', {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
  })
}

type AnnouncementHtmlProps = {
  html: string
  className?: string
  onImageClick?: (src: string) => void
}

export default function AnnouncementHtml({ html, className = '', onImageClick }: AnnouncementHtmlProps) {
  const safeHtml = useMemo(() => sanitizeAnnouncementHtml(html), [html])

  return (
    <div
      className={`announcement-html prose prose-sm max-w-none text-gray-700 leading-relaxed ${className}`}
      dangerouslySetInnerHTML={{ __html: safeHtml }}
      onClick={(event) => {
        const target = event.target as HTMLElement
        if (target.tagName === 'IMG' && onImageClick) {
          onImageClick((target as HTMLImageElement).src)
        }
      }}
    />
  )
}
