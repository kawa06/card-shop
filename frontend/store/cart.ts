'use client'

import { create } from 'zustand'
import { CartItem } from '@/lib/types'
import { cartApi } from '@/lib/api'

function computeTotal(items: CartItem[]): number {
  return items.reduce((sum, item) => sum + (item.card?.price || 0) * item.quantity, 0)
}

function mergeCartItem(items: CartItem[], updated: CartItem): CartItem[] {
  const byId = items.findIndex((i) => i.id === updated.id)
  if (byId >= 0) {
    const next = [...items]
    next[byId] = updated
    return next
  }
  const byCard = items.findIndex((i) => i.card_id === updated.card_id)
  if (byCard >= 0) {
    const next = [...items]
    next[byCard] = updated
    return next
  }
  return [...items, updated]
}

interface CartState {
  items: CartItem[]
  total: number
  isLoading: boolean
  isLoaded: boolean
  fetchCart: (force?: boolean) => Promise<void>
  addItem: (cardId: number, quantity: number) => Promise<void>
  updateItem: (itemId: number, quantity: number) => Promise<void>
  removeItem: (itemId: number) => Promise<void>
  clearCart: () => void
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  total: 0,
  isLoading: false,
  isLoaded: false,

  fetchCart: async (force = false) => {
    if (get().isLoaded && !force) return
    set({ isLoading: true })
    try {
      const res = await cartApi.get()
      const items = Array.isArray(res.data) ? res.data : []
      set({ items, total: computeTotal(items), isLoading: false, isLoaded: true })
    } catch {
      set({ isLoading: false })
    }
  },

  addItem: async (cardId: number, quantity: number) => {
    const res = await cartApi.add({ card_id: cardId, quantity })
    set((state) => {
      const items = mergeCartItem(state.items, res.data)
      return { items, total: computeTotal(items), isLoaded: true }
    })
  },

  updateItem: async (itemId: number, quantity: number) => {
    const res = await cartApi.update(itemId, { quantity })
    set((state) => {
      const items = mergeCartItem(state.items, res.data)
      return { items, total: computeTotal(items), isLoaded: true }
    })
  },

  removeItem: async (itemId: number) => {
    await cartApi.remove(itemId)
    set((state) => {
      const items = state.items.filter((i) => i.id !== itemId)
      return { items, total: computeTotal(items), isLoaded: true }
    })
  },

  clearCart: () => {
    set({ items: [], total: 0, isLoaded: true })
  },
}))
