'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface RateState {
  usdJpyRate: number
  lastUpdated: number
  setRate: (rate: number) => void
}

export const useRateStore = create<RateState>()(
  persist(
    (set) => ({
      usdJpyRate: 150,
      lastUpdated: 0,
      setRate: (rate) => set({ usdJpyRate: rate, lastUpdated: Date.now() }),
    }),
    {
      name: 'rate-storage',
    }
  )
)
