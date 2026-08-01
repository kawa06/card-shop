'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useLangStore } from '@/store/lang'
import { apiClient } from '@/lib/api'

interface CacheEntry {
  text: string
  target: string
  translated: string
  ts: number
}

// v2 ignores old entries that cached untranslated Japanese after provider failures.
const CACHE_KEY = 'oripa_translation_cache_v2'
const CACHE_TTL_MS = 1000 * 60 * 60 * 24 * 30 // 30 days

function getCache(): Record<string, CacheEntry> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function setCache(cache: Record<string, CacheEntry>) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(cache))
  } catch {
    // quota exceeded, ignore
  }
}

function cacheKey(text: string, target: string): string {
  return `${target}::${text}`
}

let pendingBatch: { text: string; resolve: (value: string) => void }[] = []
let batchTimer: ReturnType<typeof setTimeout> | null = null

async function flushBatch() {
  if (batchTimer) {
    clearTimeout(batchTimer)
    batchTimer = null
  }
  const current = pendingBatch
  pendingBatch = []
  if (current.length === 0) return

  const texts = current.map((c) => c.text)
  const target = useLangStore.getState().lang === 'en' ? 'EN' : 'JA'

  const cache = getCache()
  const results: string[] = []
  const missed: { idx: number; text: string }[] = []

  for (let i = 0; i < current.length; i++) {
    const key = cacheKey(current[i].text, target)
    const entry = cache[key]
    if (entry && Date.now() - entry.ts < CACHE_TTL_MS) {
      results[i] = entry.translated
    } else {
      missed.push({ idx: i, text: current[i].text })
    }
  }

  if (missed.length > 0) {
    try {
      const res = await apiClient.post('/translate', {
        texts: missed.map((m) => m.text),
        target,
      })
      const translations: string[] = res.data.translations || []
      for (let i = 0; i < missed.length; i++) {
        const original = missed[i].text
        const translated = translations[i] ?? original
        results[missed[i].idx] = translated
        const key = cacheKey(original, target)
        if (translated !== original) {
          cache[key] = { text: original, target, translated, ts: Date.now() }
        }
      }
      setCache(cache)
    } catch {
      for (const m of missed) {
        results[m.idx] = m.text
      }
    }
  }

  for (let i = 0; i < current.length; i++) {
    current[i].resolve(results[i])
  }
}

function requestTranslation(text: string): Promise<string> {
  return new Promise((resolve) => {
    pendingBatch.push({ text, resolve })
    if (batchTimer) clearTimeout(batchTimer)
    batchTimer = setTimeout(() => {
      flushBatch()
    }, 50)
  })
}

export function useTranslation(text: string | undefined | null): string {
  const { lang } = useLangStore()
  const [translated, setTranslated] = useState(text || '')
  const prevRef = useRef<string>('')

  useEffect(() => {
    if (!text) {
      setTranslated('')
      return
    }
    if (lang === 'ja') {
      setTranslated(text)
      return
    }
    const key = text + '|' + lang
    if (prevRef.current === key) return
    prevRef.current = key

    let cancelled = false
    requestTranslation(text).then((res) => {
      if (!cancelled) setTranslated(res)
    })
    return () => {
      cancelled = true
    }
  }, [text, lang])

  return translated
}

export function useBatchTranslation(texts: string[]): string[] {
  const { lang } = useLangStore()
  const [results, setResults] = useState<string[]>(texts)
  const prevRef = useRef<string>('')

  const run = useCallback(async () => {
    if (lang === 'ja') {
      setResults(texts)
      return
    }
    const target = 'EN'
    const cache = getCache()
    const out: string[] = []
    const missed: { idx: number; text: string }[] = []

    for (let i = 0; i < texts.length; i++) {
      const t = texts[i] || ''
      const key = cacheKey(t, target)
      const entry = cache[key]
      if (entry && Date.now() - entry.ts < CACHE_TTL_MS) {
        out[i] = entry.translated
      } else {
        missed.push({ idx: i, text: t })
      }
    }

    if (missed.length > 0) {
      try {
        const res = await apiClient.post('/translate', {
          texts: missed.map((m) => m.text),
          target,
        })
        const translations: string[] = res.data.translations || []
        for (let i = 0; i < missed.length; i++) {
          const original = missed[i].text
          const translated = translations[i] ?? original
          out[missed[i].idx] = translated
          const key = cacheKey(original, target)
          if (translated !== original) {
            cache[key] = { text: original, target, translated, ts: Date.now() }
          }
        }
        setCache(cache)
      } catch {
        for (const m of missed) {
          out[m.idx] = m.text
        }
      }
    }

    setResults(out)
  }, [texts, lang])

  useEffect(() => {
    const key = texts.join('||') + '|' + lang
    if (prevRef.current === key) return
    prevRef.current = key
    run()
  }, [run, texts, lang])

  return results
}
