'use client'

import { useEffect } from 'react'
import { X } from 'lucide-react'

type ImageLightboxProps = {
  src: string | null
  onClose: () => void
}

export default function ImageLightbox({ src, onClose }: ImageLightboxProps) {
  useEffect(() => {
    if (!src) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [src, onClose])

  if (!src) return null

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        className="absolute top-4 right-4 text-white/90 hover:text-white"
        onClick={onClose}
        aria-label="Close"
      >
        <X className="h-8 w-8" />
      </button>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt=""
        className="max-h-[90vh] max-w-full rounded-lg object-contain shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      />
    </div>
  )
}
