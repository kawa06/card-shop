'use client'

import { create } from 'zustand'
import { CartItem } from '@/lib/types'
import { cartApi } from '@/lib/api'

interface CartState {
  items: CartItem[]
  total: number
  isLoading: boolean
  fetchCart: () => Promise<void>
  addItem: (cardId: number, quantity: number) => Promise<void>
  updateItem: (itemId: number, quantity: number) => Promise<void>
  removeItem: (itemId: number) => Promise<void>
  clearCart: () => void
}

export const useCartStore = create<CartState>((set) => ({
  items: [],
  total: 0,
  isLoading: false,

  fetchCart: async () => {
    set({ isLoading: true })
    try {
      const res = await cartApi.get()
      const items = Array.isArray(res.data) ? res.data : []
      const total = items.reduce((sum, item) => sum + (item.card?.price || 0) * item.quantity, 0)
      set({ items, total, isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },

  addItem: async (cardId: number, quantity: number) => {
    try {
      await cartApi.add({ card_id: cardId, quantity })
      const res = await cartApi.get()
      const items = Array.isArray(res.data) ? res.data : []
      const total = items.reduce((sum, item) => sum + (item.card?.price || 0) * item.quantity, 0)
      set({ items, total })
    } catch (error) {
      throw error
    }
  },

  updateItem: async (itemId: number, quantity: number) => {
    try {
      await cartApi.update(itemId, { quantity })
      const res = await cartApi.get()
      const items = Array.isArray(res.data) ? res.data : []
      const total = items.reduce((sum, item) => sum + (item.card?.price || 0) * item.quantity, 0)
      set({ items, total })
    } catch (error) {
      throw error
    }
  },

  removeItem: async (itemId: number) => {
    try {
      await cartApi.remove(itemId)
      const res = await cartApi.get()
      const items = Array.isArray(res.data) ? res.data : []
      const total = items.reduce((sum, item) => sum + (item.card?.price || 0) * item.quantity, 0)
      set({ items, total })
    } catch (error) {
      throw error
    }
  },

  clearCart: () => {
    set({ items: [], total: 0 })
  },
}))
