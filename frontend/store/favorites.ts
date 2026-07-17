import { create } from 'zustand'
import { favoritesApi } from '@/lib/api'

interface FavoritesState {
  ids: number[]
  loaded: boolean
  loading: boolean
  fetchIds: () => Promise<void>
  toggle: (cardId: number) => Promise<boolean>
  isFavorite: (cardId: number) => boolean
  reset: () => void
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  ids: [],
  loaded: false,
  loading: false,

  fetchIds: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const res = await favoritesApi.getIds()
      set({ ids: res.data || [], loaded: true })
    } catch {
      set({ ids: [], loaded: true })
    } finally {
      set({ loading: false })
    }
  },

  toggle: async (cardId: number) => {
    const wasFavorite = get().isFavorite(cardId)
    if (wasFavorite) {
      await favoritesApi.remove(cardId)
      set({ ids: get().ids.filter((id) => id !== cardId) })
      return false
    }
    await favoritesApi.add(cardId)
    set({ ids: [...get().ids, cardId] })
    return true
  },

  isFavorite: (cardId: number) => get().ids.includes(cardId),

  reset: () => set({ ids: [], loaded: false, loading: false }),
}))
