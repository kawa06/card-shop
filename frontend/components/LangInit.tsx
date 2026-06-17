'use client'

import { useEffect } from 'react'
import { useLangStore } from '@/store/lang'

export function LangInit() {
  const { lang, setLang } = useLangStore()

  useEffect(() => {
    // Sync with localStorage on mount (zustand persist handles it already,
    // but this ensures immediate DOM lang attribute update)
    const stored = localStorage.getItem('lang-storage')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        if (parsed.state?.lang && parsed.state.lang !== lang) {
          setLang(parsed.state.lang)
        }
      } catch { /* ignore */ }
    }
    document.documentElement.lang = lang === 'en' ? 'en' : 'ja'
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang === 'en' ? 'en' : 'ja'
  }, [lang])

  return null
}
