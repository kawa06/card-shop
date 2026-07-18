import axios from 'axios'
import { getClerkSessionToken } from '@/lib/clerk-token'

declare module 'axios' {
  export interface AxiosRequestConfig {
    __retriedAfterAuth?: boolean
    __retriedWithClerk?: boolean
  }
}

const BASE_URL =
  typeof window !== 'undefined'
    ? '/api'
    : `${process.env.NEXT_PUBLIC_API_URL || 'https://backend-production-054e.up.railway.app'}/api`

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

let syncPromise: Promise<string | null> | null = null

const PROTECTED_API_PREFIXES = [
  '/cart',
  '/orders',
  '/favorites',
  '/payments',
  '/auth/me',
  '/auth/password',
  '/auth/phone',
  '/auth/request-verification',
]

const PUBLIC_API_PATHS = ['/payments/stripe/config']

function needsBackendAuth(url: string): boolean {
  if (PUBLIC_API_PATHS.some((path) => url.includes(path))) return false
  return PROTECTED_API_PREFIXES.some((prefix) => url.includes(prefix))
}

async function resolveRequestToken(url: string): Promise<string | null> {
  if (typeof window === 'undefined') return null

  // Admin routes use Clerk session via the Next.js proxy (never backend JWT).
  if (url.includes('/admin/')) {
    return getClerkSessionToken()
  }

  if (needsBackendAuth(url)) {
    if (!syncPromise) {
      syncPromise = import('@/store/auth')
        .then(({ useAuthStore }) => useAuthStore.getState().ensureBackendAuth())
        .finally(() => {
          syncPromise = null
        })
    }
    const backendToken = await syncPromise
    if (backendToken) return backendToken
    return getClerkSessionToken()
  }

  return localStorage.getItem('auth_token')
}

// Request interceptor to add auth token
apiClient.interceptors.request.use(async (config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  if (typeof window !== 'undefined') {
    const url = config.url || ''
    const isAdminRoute = url.includes('/admin/')
    const token = await resolveRequestToken(url)

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    } else if (isAdminRoute || needsBackendAuth(url)) {
      delete config.headers.Authorization
    } else {
      const fallback = localStorage.getItem('auth_token')
      if (fallback) {
        config.headers.Authorization = `Bearer ${fallback}`
      }
    }
  }
  return config
})

// Response interceptor: retry once after re-sync when backend JWT is stale.
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error?.config
    const status = error?.response?.status
    const url = typeof config?.url === 'string' ? config.url : ''

    if (
      status === 401 &&
      config &&
      !config.__retriedAfterAuth &&
      needsBackendAuth(url)
    ) {
      config.__retriedAfterAuth = true
      const { useAuthStore } = await import('@/store/auth')
      useAuthStore.getState().clearBackendToken()
      const token = await useAuthStore.getState().ensureBackendAuth({ force: true })
      if (token) {
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${token}`
        return apiClient.request(config)
      }

      if (!config.__retriedWithClerk) {
        config.__retriedWithClerk = true
        const clerkToken = await getClerkSessionToken()
        if (clerkToken) {
          config.headers = config.headers || {}
          config.headers.Authorization = `Bearer ${clerkToken}`
          return apiClient.request(config)
        }
      }
    }

    return Promise.reject(error)
  }
)

function normalizeCardListParams(params?: {
  page?: number
  per_page?: number
  size?: number
  category_id?: number
  pack_id?: number
  search?: string
  q?: string
}) {
  if (!params) return undefined
  const { search, size, q, ...rest } = params
  return {
    ...rest,
    ...(q ?? search ? { q: q ?? search } : {}),
    ...(params.per_page ?? size ? { per_page: params.per_page ?? size } : {}),
  }
}

// Cards API
export const cardsApi = {
  getAll: (params?: {
    page?: number
    per_page?: number
    size?: number
    category_id?: number
    pack_id?: number
    search?: string
    q?: string
  }) => apiClient.get('/cards', { params: normalizeCardListParams(params) }),

  getById: (id: number) => apiClient.get(`/cards/${id}`),
}

// Categories API
export const categoriesApi = {
  getAll: () => apiClient.get('/categories'),
}

// Packs API
export const packsApi = {
  getAll: () => apiClient.get('/packs'),
}

// Announcements API
export const announcementsApi = {
  getAll: () => apiClient.get('/announcements'),
  create: (data: { title: string; content: string; is_active: boolean }) =>
    apiClient.post('/admin/announcements', data),
  update: (id: number, data: { title: string; content: string; is_active: boolean }) =>
    apiClient.put(`/admin/announcements/${id}`, data),
  delete: (id: number) => apiClient.delete(`/admin/announcements/${id}`),
}

// Auth API
export const authApi = {
  login: (data: { email: string; password: string }) =>
    apiClient.post('/auth/login', data),

  register: (data: { email: string; password: string; name: string; phone_number?: string; phone_verification_code?: string }) =>
    apiClient.post('/auth/register', data),

  me: () => apiClient.get('/auth/me'),

  updateProfile: (data: { 
    name?: string; 
    postal_code?: string; 
    country?: string;
    region?: string;
    city?: string;
    address_line1?: string;
    address_line2?: string;
    phone_number?: string;
  }) => apiClient.put('/auth/me', data),

  deleteAccount: () => apiClient.delete('/auth/me'),

  changePassword: (data: import('./types').PasswordChangeRequest) =>
    apiClient.put('/auth/password', data),

  requestVerification: () => apiClient.post('/auth/request-verification'),

  verifyEmail: (token: string) => apiClient.get(`/auth/verify/${token}`),

  sendPhoneOtp: (phone: string) => apiClient.post('/auth/phone/send', { phone }),

  verifyPhoneOtp: (phone: string, code: string) => apiClient.post('/auth/phone/verify', { phone, code }),
}

// Cart API
export const cartApi = {
  get: () => apiClient.get('/cart'),

  add: (data: { card_id: number; quantity: number }) =>
    apiClient.post('/cart', data),

  update: (itemId: number, data: { quantity: number }) =>
    apiClient.put(`/cart/${itemId}`, data),

  remove: (itemId: number) => apiClient.delete(`/cart/${itemId}`),
}

// Favorites API
export const favoritesApi = {
  getAll: () => apiClient.get('/favorites'),
  getIds: () => apiClient.get('/favorites/ids'),
  add: (cardId: number) => apiClient.post(`/favorites/${cardId}`),
  remove: (cardId: number) => apiClient.delete(`/favorites/${cardId}`),
}

// Orders API
export const ordersApi = {
  create: (data: { 
    shipping_address: string; 
    payment_method: string;
    shipping_method?: string;
    shipping_fee?: number;
    postal_code?: string;
    country?: string;
    region?: string;
    city?: string;
    address_line1?: string;
    address_line2?: string;
  }) => apiClient.post('/orders', data),

  getAll: () => apiClient.get('/orders'),

  getById: (id: number) => apiClient.get(`/orders/${id}`),
}

// Payments API
export const paymentsApi = {
  getStripeConfig: () => apiClient.get('/payments/stripe/config'),
  createStripeCheckout: (data: {
    postal_code?: string
    country?: string
    region?: string
    city?: string
    address_line1?: string
    address_line2?: string
    shipping_address?: string
    shipping_method?: string
    locale?: string
    checkout_type?: 'card' | 'bank_transfer'
  }) => apiClient.post('/payments/stripe/create-checkout-session', data),
  confirmStripeCheckout: (sessionId: string) =>
    apiClient.get('/payments/stripe/confirm', { params: { session_id: sessionId } }),
}

// Admin API
export const adminApi = {
  // Cards
  getAllCards: (params?: {
    page?: number
    per_page?: number
    q?: string
    is_active?: boolean
  }) => apiClient.get('/admin/cards', { params }),
  createCard: (data: Partial<import('./types').Card>) =>
    apiClient.post('/admin/cards', data),
  updateCard: (id: number, data: Partial<import('./types').Card>) =>
    apiClient.put(`/admin/cards/${id}`, data),
  updateCardShippingMethods: (id: number, allowed_shipping_methods: string | null) =>
    apiClient.patch(`/admin/cards/${id}/shipping-methods`, { allowed_shipping_methods }),
  deleteCard: (id: number) => apiClient.delete(`/admin/cards/${id}`),
  uploadImage: (file: File | Blob, filename: string) => {
    const form = new FormData()
    form.append('file', file, filename)
    return apiClient.post<{ url: string }>('/admin/uploads', form)
  },

  // Categories
  createCategory: (data: { name: string; description?: string; slug: string }) =>
    apiClient.post('/admin/categories', data),
  updateCategory: (id: number, data: { name: string; description?: string }) =>
    apiClient.put(`/admin/categories/${id}`, data),
  deleteCategory: (id: number) => apiClient.delete(`/admin/categories/${id}`),

  // Packs
  getAllPacks: () => apiClient.get('/admin/packs'),
  createPack: (data: { name: string; name_en?: string | null; slug: string; sort_order?: number }) =>
    apiClient.post('/admin/packs', data),
  updatePack: (id: number, data: { name?: string; name_en?: string | null; slug?: string; sort_order?: number }) =>
    apiClient.put(`/admin/packs/${id}`, data),
  deletePack: (id: number) => apiClient.delete(`/admin/packs/${id}`),

  // Orders
  getAllOrders: (params?: {
    payment_status?: string
    shipping_status?: string
    q?: string
  }) => apiClient.get('/admin/orders', { params }),
  getOrderById: (id: number) =>
    apiClient.get<import('./types').AdminOrderDetail>(`/admin/orders/${id}`),
  updateOrderStatus: (id: number, status: string) =>
    apiClient.put(`/admin/orders/${id}/status`, { status }),
  updateOrderShipping: (
    id: number,
    data: {
      shipping_status?: string
      shipping_carrier?: string | null
      tracking_number?: string | null
      shipped_at?: string | null
      admin_note?: string | null
    }
  ) => apiClient.patch(`/admin/orders/${id}/shipping`, data),
  confirmOrderPayment: (id: number) =>
    apiClient.post(`/admin/orders/${id}/confirm-payment`),
  sendPurchaseEmail: (id: number, force = false) =>
    apiClient.post(`/admin/orders/${id}/send-purchase-email`, null, { params: { force } }),
  sendShippingEmail: (id: number, force = false) =>
    apiClient.post(`/admin/orders/${id}/send-shipping-email`, null, { params: { force } }),
  cancelOrder: (id: number) =>
    apiClient.post(`/admin/orders/${id}/cancel`),
  extendPaymentDeadline: (id: number, hours: number) =>
    apiClient.patch(`/admin/orders/${id}/payment-deadline`, { hours }),
  getClickPostOrders: () =>
    apiClient.get<import('./types').AdminClickPostOrder[]>('/admin/orders/click-post'),
  exportClickPostCsv: (orderIds: number[], markExported = true) =>
    apiClient.post(
      '/admin/orders/click-post/export',
      { order_ids: orderIds, mark_exported: markExported },
      { responseType: 'blob' }
    ),

  // Announcements
  createAnnouncement: (data: {
    title: string
    content: string
    is_active: boolean
  }) => apiClient.post('/admin/announcements', data),
  updateAnnouncement: (
    id: number,
    data: { title: string; content: string; is_active: boolean }
  ) => apiClient.put(`/admin/announcements/${id}`, data),
  deleteAnnouncement: (id: number) =>
    apiClient.delete(`/admin/announcements/${id}`),

  // Users
  getAllUsers: () => apiClient.get('/admin/users'),

  // Shipping (admin proxy auth)
  updateShippingRate: (methodCode: string, data: Partial<import('./types').ShippingRate>) =>
    apiClient.patch(`/admin/shipping-rates/${methodCode}`, data),
  refreshShippingRates: () => apiClient.post('/admin/shipping-rates/refresh'),
}

// Exchange API
export const exchangeApi = {
  getRate: () => apiClient.get<{ rate: number; last_updated: number }>('/exchange-rate'),
}

// Shipping API
export const shippingApi = {
  getRates: () => apiClient.get<import('./types').ShippingRate[]>('/shipping-rates'),
  calculateRate: (params: { method: string; prefecture?: string; country?: string }) =>
    apiClient.get<import('./types').ShippingQuote>('/shipping-rates/calculate', { 
      params: { 
        method_code: params.method, 
        region: params.prefecture,
        country: params.country 
      } 
    }),
  refreshRates: () => apiClient.post('/shipping-rates/refresh'),
  updateRate: (methodCode: string, data: Partial<import('./types').ShippingRate>) =>
    apiClient.patch(`/shipping-rates/${methodCode}`, data),
  getOrigin: () => apiClient.get<{ key: string; value: string }>('/site-settings/shipping-origin'),
  updateOrigin: (value: string) => apiClient.post('/site-settings/shipping-origin', { value }),
}
