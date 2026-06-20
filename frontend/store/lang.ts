'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Lang = 'ja' | 'en'

interface LangState {
  lang: Lang
  setLang: (lang: Lang) => void
}

export const useLangStore = create<LangState>()(
  persist(
    (set) => ({
      lang: 'ja',
      setLang: (lang) => set({ lang }),
    }),
    {
      name: 'lang-storage',
    }
  )
)
