'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api'

type Props = {
  /** Admin API path without /api prefix, e.g. /admin/orders/1/barcode.svg */
  apiPath: string
  alt: string
  className?: string
}

export function AdminAuthenticatedSvgImage({ apiPath, alt, className }: Props) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false

    ;(async () => {
      try {
        const res = await apiClient.get(apiPath, {
          responseType: 'blob',
          headers: { Accept: 'image/svg+xml' },
        })
        const blob =
          res.data instanceof Blob
            ? res.data
            : new Blob([res.data], { type: 'image/svg+xml' })
        if (!blob.type.includes('svg')) {
          throw new Error('invalid svg response')
        }
        url = URL.createObjectURL(blob)
        if (!cancelled) setObjectUrl(url)
      } catch {
        if (!cancelled) setFailed(true)
      }
    })()

    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [apiPath])

  if (failed) {
    return <p className="text-xs text-red-600 text-center">バーコードを読み込めませんでした</p>
  }
  if (!objectUrl) {
    return <div className={`animate-pulse bg-gray-100 rounded ${className ?? 'h-16 w-full'}`} aria-hidden />
  }
  // eslint-disable-next-line @next/next/no-img-element -- blob URL from authenticated admin SVG fetch
  return <img src={objectUrl} alt={alt} className={className} />
}
