import axios from 'axios'
import { getClerkSessionToken } from '@/lib/clerk-token'
import type {
  Announcement,
  AnnouncementAdmin,
  AnnouncementFeedResponse,
  AnnouncementFormData,
} from './types'

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
  '/inquiries',
  '/points',
  '/me/oripa-entries',
]

function needsOripaUserAuth(url: string): boolean {
  return url.includes('/oripas/') && url.includes('/purchase')
}

const PUBLIC_API_PATHS = ['/payments/stripe/config', '/inquiries/meta/categories']

function needsLiveUserAuth(url: string): boolean {
  if (!url.includes('/live/') || url.includes('/admin/')) return false
  if (url.includes('/comments')) return true
  if (url.includes('/auctions/') && url.includes('/bids')) return true
  if (url.includes('/offers')) return true
  return false
}

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

  if (needsLiveUserAuth(url) || needsOripaUserAuth(url) || needsBackendAuth(url)) {
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
    } else if (isAdminRoute || needsBackendAuth(url) || needsOripaUserAuth(url)) {
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
      needsBackendAuth(url) || needsOripaUserAuth(url)
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
  /** Legacy public banner list (home page) */
  getAll: (lang?: 'ja' | 'en') =>
    apiClient.get<Announcement[]>('/announcements', { params: lang ? { lang } : undefined }),
  getFeed: (params?: { lang?: 'ja' | 'en'; q?: string }) =>
    apiClient.get<AnnouncementFeedResponse>('/announcements/feed', { params }),
  getUnreadCount: () =>
    apiClient.get<{ count: number }>('/announcements/unread-count'),
  getById: (id: number, lang?: 'ja' | 'en') =>
    apiClient.get<Announcement>(`/announcements/${id}`, { params: lang ? { lang } : undefined }),
  create: (data: Partial<AnnouncementFormData> & {
    title?: string
    content?: string
    is_active?: boolean
    publish_at?: string | null
    expire_at?: string | null
    thumbnail?: string | null
  }) =>
    apiClient.post<AnnouncementAdmin>('/admin/announcements', data),
  update: (
    id: number,
    data: Partial<AnnouncementFormData> & {
      title?: string
      content?: string
      is_active?: boolean
      clear_publish_at?: boolean
      clear_expire_at?: boolean
      publish_at?: string | null
      expire_at?: string | null
      thumbnail?: string | null
    }
  ) => apiClient.put<AnnouncementAdmin>(`/admin/announcements/${id}`, data),
  delete: (id: number) => apiClient.delete(`/admin/announcements/${id}`),
  adminGetAll: (q?: string) =>
    apiClient.get<AnnouncementAdmin[]>('/admin/announcements', { params: q ? { q } : undefined }),
  adminGetById: (id: number) =>
    apiClient.get<AnnouncementAdmin>(`/admin/announcements/${id}`),
  uploadImage: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<{ url: string }>('/admin/announcements/upload-image', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  emailPreview: (id: number, params?: { audience_key?: string }) =>
    apiClient.get<{
      subject: string
      html: string
      text?: string
      recipient_count: number
      target_description: string
      recipients_sample: string[]
      template_key?: string
      template_name?: string
      audience_key?: string
      image_urls?: string[]
    }>(`/admin/announcements/${id}/email-preview`, { params }),
  sendEmail: (
    id: number,
    data: {
      confirm: boolean
      send_mode: 'immediate' | 'scheduled'
      scheduled_at?: string | null
      idempotency_key?: string
      audience_key?: string
      audience_params?: Record<string, unknown>
      template_key?: string
    }
  ) => apiClient.post(`/admin/announcements/${id}/send-email`, data),
}

// Auth API
export const authApi = {
  login: (data: { email: string; password: string }) =>
    apiClient.post('/auth/login', data),

  register: (data: { email: string; password: string; name: string; phone_number?: string; phone_verification_code?: string }) =>
    apiClient.post('/auth/register', data),

  me: () => apiClient.get('/auth/me'),

  updateProfile: (data: {
    name?: string
    family_name?: string
    given_name?: string
    family_name_kana?: string
    given_name_kana?: string
    birth_date?: string
    postal_code?: string
    country?: string
    region?: string
    city?: string
    address_line1?: string
    address_line2?: string
    phone_number?: string
  }) => apiClient.put('/auth/me', data),

  deleteAccount: () => apiClient.delete('/auth/me'),

  changePassword: (data: import('./types').PasswordChangeRequest) =>
    apiClient.put('/auth/password', data),

  requestVerification: () => apiClient.post('/auth/request-verification'),

  verifyEmail: (token: string) => apiClient.get(`/auth/verify/${token}`),

  sendPhoneOtp: (phone: string) => apiClient.post('/auth/phone/send', { phone }),

  verifyPhoneOtp: (phone: string, code: string) => apiClient.post('/auth/phone/verify', { phone, code }),

  verify2fa: (data: { challenge_id: number; user_id: number; code: string }) =>
    apiClient.post('/auth/2fa/verify', data),

  get2faSettings: () => apiClient.get<{ enabled: boolean; method?: string | null }>('/auth/2fa/settings'),

  update2faSettings: (enabled: boolean) =>
    apiClient.put('/auth/2fa/settings', { enabled }),

  getLoginHistory: () =>
    apiClient.get<Array<{ id: number; ip_address?: string | null; user_agent?: string | null; method: string; success: boolean; created_at: string }>>('/auth/login-history'),
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
    points_to_use?: number
    coupon_code?: string
  }) => apiClient.post('/payments/stripe/create-checkout-session', data),
  confirmStripeCheckout: (sessionId: string) =>
    apiClient.get('/payments/stripe/confirm', { params: { session_id: sessionId } }),
}


// Points API (Phase 3-4)
export const pointsApi = {
  getBalance: () => apiClient.get('/points/balance'),
  getHistory: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/points/history', { params }),
  checkoutPreview: (data: {
    items_subtotal: number
    shipping_fee?: number
    packaging_fee?: number
    discount_amount?: number
    requested_points?: number
  }) => apiClient.post('/points/checkout-preview', data),
}

export const adminPointsApi = {
  getSettings: () => apiClient.get('/admin/points/settings'),
  updateSettings: (data: Record<string, unknown>) => apiClient.patch('/admin/points/settings', data),
  getUser: (userId: number) => apiClient.get(`/admin/points/users/${userId}`),
  getUserHistory: (userId: number, params?: { limit?: number; offset?: number }) =>
    apiClient.get(`/admin/points/users/${userId}/history`, { params }),
  grant: (data: { user_id: number; amount: number; reason: string; expiration_days?: number; idempotency_key?: string }) =>
    apiClient.post('/admin/points/grant', data),
  deduct: (data: { user_id: number; amount: number; reason: string; idempotency_key?: string }) =>
    apiClient.post('/admin/points/deduct', data),
  getAuditLogs: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/admin/points/audit', { params }),
}

export const couponsApi = {
  listMine: () => apiClient.get('/coupons/mine'),
  checkoutPreview: (data: {
    coupon_code: string
    items_subtotal: number
    shipping_fee?: number
    packaging_fee?: number
    cart_items?: Array<{ card_id: number; category_id?: number | null; quantity: number; unit_price: number }>
    requested_points?: number
  }) => apiClient.post('/coupons/checkout-preview', data),
}

export const notificationsApi = {
  list: (params?: { limit?: number; offset?: number; unread_only?: boolean }) =>
    apiClient.get('/notifications', { params }),
  unreadCount: () => apiClient.get('/notifications/unread-count'),
  markRead: (id: number) => apiClient.post(`/notifications/${id}/read`),
  markAllRead: () => apiClient.post('/notifications/read-all'),
  getSettings: () => apiClient.get('/notifications/settings'),
  updateSettings: (data: Record<string, boolean>) => apiClient.patch('/notifications/settings', data),
}

export const adminUserNotificationsApi = {
  broadcast: (data: {
    title: string
    body: string
    user_id?: number
    action_url?: string
    category?: string
    type?: string
  }) => apiClient.post('/admin/user-notifications/broadcast', data),
}

export type AnalyticsDomain = 'sales' | 'live' | 'auctions' | 'coupons' | 'points' | 'inventory'

export type AnalyticsKpi = {
  from_at?: string | null
  to_at?: string | null
  paid_order_count: number
  paid_sales_yen: number
  avg_order_yen: number
  coupon_discount_yen: number
  points_used: number
  points_earned: number
  live_stream_count: number
  live_live_count: number
  auction_count: number
  auction_sold_count: number
  auction_gmv_yen: number
  coupon_active_count: number
  coupon_redemption_count: number
  new_members: number
  low_stock_products?: number
  out_of_stock_products?: number
  pending_restocks?: number
}

export type AnalyticsList = {
  domain: string
  total: number
  page: number
  size: number
  sort: string
  order: string
  items: Array<Record<string, unknown>>
  series?: Array<{ date: string; value: number }>
}

export const adminAnalyticsApi = {
  kpi: (params?: { from_at?: string; to_at?: string }) =>
    apiClient.get<AnalyticsKpi>('/admin/analytics/kpi', { params }),
  list: (domain: AnalyticsDomain, params?: Record<string, string | number | undefined>) =>
    apiClient.get<AnalyticsList>(`/admin/analytics/${domain}`, { params }),
  export: (params: Record<string, string>) =>
    apiClient.get('/admin/analytics/export', { params, responseType: 'blob' }),
}

export type InventoryAlertItem = {
  id: number
  product_id: number
  product_name?: string | null
  alert_type: string
  stock_quantity: number
  threshold: number
  status: string
  created_at: string
  resolved_at?: string | null
}

export type InventoryRestockItem = {
  id: number
  product_id: number
  product_name?: string | null
  requested_quantity: number
  received_quantity?: number | null
  status: string
  note?: string | null
  created_at: string
  updated_at?: string | null
  completed_at?: string | null
  current_stock?: number | null
}

export const adminInventoryApi = {
  listAlerts: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: InventoryAlertItem[] }>('/admin/inventory-alerts', { params }),
  resolveAlert: (id: number) => apiClient.post(`/admin/inventory-alerts/${id}/resolve`),
  listRestocks: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: InventoryRestockItem[] }>('/admin/inventory-restocks', { params }),
  createRestock: (data: { product_id: number; requested_quantity: number; note?: string }) =>
    apiClient.post<InventoryRestockItem>('/admin/inventory-restocks', data),
  getRestock: (id: number) => apiClient.get<InventoryRestockItem>(`/admin/inventory-restocks/${id}`),
  updateRestock: (id: number, data: Record<string, unknown>) =>
    apiClient.patch<InventoryRestockItem>(`/admin/inventory-restocks/${id}`, data),
  receiveRestock: (id: number, data?: { received_quantity?: number }) =>
    apiClient.post<InventoryRestockItem>(`/admin/inventory-restocks/${id}/receive`, data || {}),
}

export const adminOripaApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: Array<Record<string, unknown>> }>('/admin/oripas', { params }),
  create: (data: Record<string, unknown>) => apiClient.post('/admin/oripas', data),
  get: (id: number) => apiClient.get(`/admin/oripas/${id}`),
  update: (id: number, data: Record<string, unknown>) => apiClient.patch(`/admin/oripas/${id}`, data),
  remove: (id: number) => apiClient.delete(`/admin/oripas/${id}`),
  generateEntries: (id: number, data?: { force?: boolean }) =>
    apiClient.post(`/admin/oripas/${id}/generate-entries`, data || {}),
  listEntries: (id: number, params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: Array<Record<string, unknown>> }>(`/admin/oripas/${id}/entries`, { params }),
  linkEntry: (entryId: number, data: { linked_product_id?: number | null }) =>
    apiClient.patch(`/admin/oripa-entries/${entryId}`, data),
  bulkLink: (id: number, data: { start_number: number; product_ids: number[] }) =>
    apiClient.post(`/admin/oripas/${id}/entries/bulk-link`, data),
}

export const oripaApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: Array<Record<string, unknown>> }>('/oripas', { params }),
  get: (id: number) => apiClient.get(`/oripas/${id}`),
  purchase: (
    id: number,
    data: {
      quantity: number
      idempotency_key?: string
      points_to_use?: number
      coupon_code?: string
    }
  ) => apiClient.post(`/oripas/${id}/purchase`, data),
  getPurchase: (purchaseId: number) => apiClient.get(`/me/oripa-purchases/${purchaseId}`),
  myEntries: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: Array<Record<string, unknown>> }>('/me/oripa-entries', { params }),
}

export const adminShipmentsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<{ total: number; items: Array<Record<string, unknown>> }>('/admin/shipments', { params }),
  create: (data: {
    user_id: number
    entry_ids?: number[]
    order_ids?: number[]
    note?: string
  }) => apiClient.post('/admin/shipments', data),
  get: (id: number) => apiClient.get(`/admin/shipments/${id}`),
  update: (id: number, data: Record<string, unknown>) => apiClient.patch(`/admin/shipments/${id}`, data),
  logs: (id: number) => apiClient.get(`/admin/shipments/${id}/logs`),
  barcode: (id: number) => apiClient.get(`/admin/shipments/${id}/barcode`),
}

export const adminCouponsApi = {
  list: (params?: { q?: string; active_only?: boolean; limit?: number; offset?: number }) =>
    apiClient.get('/admin/coupons', { params }),
  create: (data: Record<string, unknown>) => apiClient.post('/admin/coupons', data),
  update: (id: number, data: Record<string, unknown>) => apiClient.patch(`/admin/coupons/${id}`, data),
  assign: (id: number, data: { user_id: number; note?: string }) =>
    apiClient.post(`/admin/coupons/${id}/assign`, data),
  exportCsv: () => apiClient.get('/admin/coupons/export.csv', { responseType: 'blob' }),
  getAuditLogs: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/admin/coupons/audit', { params }),
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
  getOrderBarcode: (id: number) =>
    apiClient.get<{ id: number; order_id: number; barcode_type: string; human_readable?: string | null }>(
      `/admin/orders/${id}/barcode`,
    ),
  getInvoiceSettings: () =>
    apiClient.get<import('./types').InvoiceConfigApi>('/admin/shop/invoice-settings'),
  updateInvoiceSettings: (data: {
    invoice_enabled?: boolean
    invoice_registration_number?: string | null
    invoice_issuer_name?: string | null
    default_tax_rate?: number
  }) => apiClient.put<import('./types').InvoiceConfigApi>('/admin/shop/invoice-settings', data),
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
      shipping_box_type?: string | null
      shipping_weight_g?: number | null
      shipping_size_label?: string | null
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
  getDashboardStats: () =>
    apiClient.get<import('./types').AdminDashboardStats>('/admin/dashboard/stats'),

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

export const inquiriesApi = {
  getUnreadCount: () => apiClient.get<{ count: number }>('/inquiries/unread-count'),
  getCategories: () => apiClient.get<{ value: string; label: string }[]>('/inquiries/meta/categories'),
  list: () => apiClient.get<import('./types').InquiryListItem[]>('/inquiries'),
  getById: (id: number) => apiClient.get<import('./types').InquiryDetail>(`/inquiries/${id}`),
  create: (data: import('./types').InquiryCreatePayload) =>
    apiClient.post<import('./types').InquiryDetail>('/inquiries', data),
  postMessage: (id: number, message: string) =>
    apiClient.post<import('./types').InquiryMessage>(`/inquiries/${id}/messages`, { message }),
  markRead: (id: number) => apiClient.post(`/inquiries/${id}/read`),
  getTemplates: () => apiClient.get<import('./types').InquiryTemplate[]>('/inquiries/templates'),
  previewTemplate: (templateId: number, payload: import('./types').InquiryCreatePayload) =>
    apiClient.post<{ body: string; warnings: string[] }>(
      `/inquiries/templates/${templateId}/preview`,
      payload
    ),
  uploadAttachments: (inquiryId: number, files: File[], messageId?: number) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return apiClient.post<import('./types').InquiryAttachment[]>(
      `/inquiries/${inquiryId}/attachments`,
      form,
      { params: messageId ? { message_id: messageId } : undefined }
    )
  },
}

export const adminInquiriesApi = {
  getStats: () => apiClient.get<import('./types').InquiryStats>('/admin/inquiries/stats'),
  list: (params?: { q?: string; status?: string; category?: string; priority?: string }) =>
    apiClient.get<import('./types').AdminInquiryListItem[]>('/admin/inquiries', { params }),
  getById: (id: number) => apiClient.get<import('./types').AdminInquiryDetail>(`/admin/inquiries/${id}`),
  reply: (id: number, data: import('./types').AdminInquiryReplyPayload) =>
    apiClient.post<import('./types').InquiryMessage>(`/admin/inquiries/${id}/reply`, data),
  update: (id: number, data: { status?: string; priority?: string; assigned_admin_id?: number | null }) =>
    apiClient.patch<import('./types').AdminInquiryListItem>(`/admin/inquiries/${id}`, data),
  getReplyTemplates: () => apiClient.get<import('./types').InquiryTemplate[]>('/admin/inquiries/templates'),
  previewTemplate: (templateId: number, inquiryId: number, reason?: string) =>
    apiClient.post<{ body: string; warnings: string[] }>(
      `/admin/inquiries/templates/${templateId}/preview`,
      null,
      { params: { inquiry_id: inquiryId, reason } }
    ),
  manageTemplates: (templateType?: string) =>
    apiClient.get<import('./types').InquiryTemplate[]>('/admin/inquiries/manage/templates', {
      params: templateType ? { template_type: templateType } : undefined,
    }),
  createTemplate: (data: {
    template_type: string
    category?: string | null
    name: string
    body: string
    is_active?: boolean
    sort_order?: number
  }) => apiClient.post<import('./types').InquiryTemplate>('/admin/inquiries/manage/templates', data),
  updateTemplate: (
    id: number,
    data: {
      category?: string | null
      name?: string
      body?: string
      is_active?: boolean
      sort_order?: number
    }
  ) => apiClient.put<import('./types').InquiryTemplate>(`/admin/inquiries/manage/templates/${id}`, data),
  deleteTemplate: (id: number) => apiClient.delete(`/admin/inquiries/manage/templates/${id}`),
  getSettings: () => apiClient.get<import('./types').InquirySettings>('/admin/inquiries/manage/settings'),
  updateSettings: (data: Partial<import('./types').InquirySettings & { auto_reply_body?: string }>) =>
    apiClient.put<import('./types').InquirySettings>('/admin/inquiries/manage/settings', data),
  uploadAttachments: (inquiryId: number, files: File[], messageId?: number) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    return apiClient.post<import('./types').InquiryAttachment[]>(
      `/admin/inquiries/${inquiryId}/attachments`,
      form,
      { params: messageId ? { message_id: messageId } : undefined }
    )
  },
  getEmailTemplates: () =>
    apiClient.get<import('./types').InquiryEmailTemplateOption[]>('/admin/inquiries/email/templates'),
  previewEmail: (inquiryId: number, data: { email_template_key: string; reply_text: string; include_reply_content?: boolean; force_dark?: boolean }) =>
    apiClient.post<import('./types').InquiryEmailPreview>(`/admin/inquiries/${inquiryId}/email/preview`, data),
  getEmailLogs: (inquiryId: number, limit?: number) =>
    apiClient.get<import('./types').InquiryEmailLog[]>(`/admin/inquiries/${inquiryId}/email/logs`, {
      params: limit ? { limit } : undefined,
    }),
  resendEmail: (inquiryId: number, data: { event_key: string; reply_text?: string }) =>
    apiClient.post(`/admin/inquiries/${inquiryId}/email/resend`, data),
  getDraft: (inquiryId: number) =>
    apiClient.get<import('./types').InquiryReplyDraft | null>(`/admin/inquiries/${inquiryId}/draft`),
  deleteDraft: (inquiryId: number) => apiClient.delete(`/admin/inquiries/${inquiryId}/draft`),
}

export const adminBuybackApi = {
  getStats: () => apiClient.get<import('./types').AdminBuybackStats>('/admin/buyback/stats'),
  listIdentity: (params?: { status?: string; q?: string }) =>
    apiClient.get<import('./types').AdminIdentityListItem[]>('/admin/buyback/identity', { params }),
  getIdentity: (id: number) =>
    apiClient.get<import('./types').AdminIdentityDetail>(`/admin/buyback/identity/${id}`),
  getIdentityDocument: (id: number, side: 'front' | 'back') =>
    apiClient.get<Blob>(`/admin/buyback/identity/${id}/documents/${side}`, { responseType: 'blob' }),
  approveIdentity: (id: number) =>
    apiClient.post<import('./types').AdminIdentityDetail>(`/admin/buyback/identity/${id}/approve`),
  rejectIdentity: (id: number, rejection_reason: string) =>
    apiClient.post<import('./types').AdminIdentityDetail>(`/admin/buyback/identity/${id}/reject`, {
      rejection_reason,
    }),
  requestResubmitIdentity: (id: number, reason: string, admin_memo?: string) =>
    apiClient.post<import('./types').AdminIdentityDetail>(
      `/admin/buyback/identity/${id}/request-resubmit`,
      { reason, admin_memo }
    ),
  updateIdentityMemo: (id: number, admin_memo: string) =>
    apiClient.patch<import('./types').AdminIdentityDetail>(`/admin/buyback/identity/${id}/memo`, {
      admin_memo,
    }),
  listRequests: (params?: {
    status?: string
    q?: string
    buyback_method?: string
    payout_transfer_status?: string
    identity_not_approved?: boolean
    date_from?: string
    date_to?: string
  }) =>
    apiClient.get<import('./types').AdminBuybackRequestListItem[]>('/admin/buyback/requests', {
      params,
    }),
  exportRequestsCsv: (params?: {
    status?: string
    q?: string
    buyback_method?: string
    payout_transfer_status?: string
    identity_not_approved?: boolean
    date_from?: string
    date_to?: string
  }) =>
    apiClient.get('/admin/buyback/requests/export.csv', {
      params,
      responseType: 'blob',
    }),
  getRequest: (id: number) =>
    apiClient.get<import('./types').AdminBuybackRequestDetail>(`/admin/buyback/requests/${id}`),
  getAssessmentLogs: (id: number) =>
    apiClient.get<import('./types').AdminBuybackAssessmentLog[]>(
      `/admin/buyback/requests/${id}/assessment-logs`
    ),
  presentAssessment: (id: number, data: { customer_status_note?: string }) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/present-assessment`,
      data
    ),
  storeCheckIn: (id: number) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/store/check-in`
    ),
  storeStartAssessment: (id: number) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/store/start-assessment`
    ),
  storeAppraisalEstimate: (
    id: number,
    data: { estimated_minutes: number; message?: string }
  ) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/store/appraisal-estimate`,
      data
    ),
  storeCompletePayment: (
    id: number,
    data: { payment_method: string; payment_amount?: number; payment_note?: string }
  ) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/store/complete-payment`,
      data
    ),
  storeCompleteTransaction: (id: number) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/store/complete-transaction`
    ),
  updateRequest: (
    id: number,
    data: {
      status: string
      admin_note?: string
      tracking_number?: string
      assessed_total?: number
      payout_total?: number
      send_email?: boolean
      force_email?: boolean
    }
  ) => apiClient.patch<import('./types').AdminBuybackRequestDetail>(`/admin/buyback/requests/${id}`, data),
  resendRequestEmail: (id: number, event_key: string, force = true) =>
    apiClient.post(`/admin/buyback/requests/${id}/resend-email`, { event_key, force }),
  updateRequestItems: (
    id: number,
    data: {
      items: Array<{
        id: number
        line_status?: string
        condition_code?: string
        assessed_unit_price?: number | null
        accepted_unit_price?: number | null
        rejection_reason_code?: string | null
        rejection_reason_text?: string | null
        assessment_comment?: string | null
        is_return_target?: boolean
        is_disposal_target?: boolean
        return_status?: string
        return_tracking_number?: string | null
        return_shipping_cost?: number | null
      }>
      recalculate_assessed_total?: boolean
      apply_handling_policy?: boolean
    }
  ) =>
    apiClient.patch<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/items`,
      data
    ),
  completePayout: (
    id: number,
    data: {
      payout_total?: number
      admin_note?: string
      send_email?: boolean
      force_email?: boolean
    }
  ) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/complete-payout`,
      data
    ),
  schedulePayout: (
    id: number,
    data: { payout_scheduled_at: string; admin_note?: string }
  ) =>
    apiClient.post<import('./types').AdminBuybackRequestDetail>(
      `/admin/buyback/requests/${id}/schedule-payout`,
      data
    ),
  listCatalogProducts: (params?: { include_inactive?: boolean }) =>
    apiClient.get<import('./types').AdminBuybackCatalogProduct[]>(
      '/admin/buyback/catalog/products',
      { params }
    ),
  createCatalogProduct: (data: import('./types').AdminBuybackCatalogProductInput) =>
    apiClient.post<import('./types').AdminBuybackCatalogProduct>(
      '/admin/buyback/catalog/products',
      data
    ),
  updateCatalogProduct: (
    id: number,
    data: import('./types').AdminBuybackCatalogProductInput
  ) =>
    apiClient.put<import('./types').AdminBuybackCatalogProduct>(
      `/admin/buyback/catalog/products/${id}`,
      data
    ),
  deleteCatalogProduct: (id: number) =>
    apiClient.delete(`/admin/buyback/catalog/products/${id}`),
  getChannelSettings: () =>
    apiClient.get<import('./types').BuybackChannelSettings>('/admin/buyback/channel/settings'),
  updateChannelSettings: (data: Partial<{
    store_enabled: boolean
    mail_enabled: boolean
    slot_interval_minutes: number
    business_hours: Record<string, import('./types').BuybackBusinessDayHours>
    closed_dates: string[]
  }>) =>
    apiClient.put<import('./types').BuybackChannelSettings>('/admin/buyback/channel/settings', data),
  listBanners: () =>
    apiClient.get<import('./types').BuybackPromoBanner[]>('/admin/buyback/banners'),
  createBanner: (data: Omit<import('./types').BuybackPromoBanner, 'id' | 'is_active' | 'created_at' | 'updated_at'>) =>
    apiClient.post<import('./types').BuybackPromoBanner>('/admin/buyback/banners', data),
  updateBanner: (id: number, data: Partial<Omit<import('./types').BuybackPromoBanner, 'id' | 'is_active' | 'created_at' | 'updated_at'>>) =>
    apiClient.put<import('./types').BuybackPromoBanner>(`/admin/buyback/banners/${id}`, data),
  deleteBanner: (id: number) => apiClient.delete(`/admin/buyback/banners/${id}`),
  listReservations: (params?: { from_date?: string; to_date?: string }) =>
    apiClient.get<import('./types').BuybackStoreReservation[]>('/admin/buyback/reservations', { params }),
}

export const adminBuybackLogisticsApi = {
  scan: (data: { code: string; device_info?: string }) =>
    apiClient.post<import('./types').AdminBuybackScanResult>('/admin/buyback/scan', data),
  receive: (data: {
    inbound_shipment_id: number
    scanned_code?: string
    box_count?: number
    actual_item_count?: number
    condition_note?: string
    admin_note?: string
    device_info?: string
  }) =>
    apiClient.post<import('./types').AdminBuybackScanResult>('/admin/buyback/inbound/receive', data),
  listPackages: (requestId: number) =>
    apiClient.get<import('./types').AdminBuybackPackage[]>(
      `/admin/buyback/requests/${requestId}/packages`
    ),
  issuePackages: (
    requestId: number,
    data: {
      total_boxes?: number
      package_kind?: string
      shipping_method?: string
      preferred_ship_date?: string
      preferred_time_slot?: string
      return_reference?: string
      admin_note?: string
      request_item_ids?: number[]
      replace_existing?: boolean
    }
  ) =>
    apiClient.post<import('./types').AdminBuybackPackage[]>(
      `/admin/buyback/requests/${requestId}/packages`,
      data
    ),
  completePackage: (
    packageId: number,
    data?: { tracking_number?: string; admin_note?: string }
  ) =>
    apiClient.post<import('./types').AdminBuybackPackage>(
      `/admin/buyback/packages/${packageId}/complete`,
      data || {}
    ),
  getPackageLabel: (packageId: number) =>
    apiClient.get<import('./types').AdminBuybackPackageLabel>(
      `/admin/buyback/packages/${packageId}/label`
    ),
  printPackageLabel: (
    packageId: number,
    data?: { is_reprint?: boolean; device_info?: string }
  ) =>
    apiClient.post<import('./types').AdminBuybackPackageLabel>(
      `/admin/buyback/packages/${packageId}/label/print`,
      data || {}
    ),
  shipScan: (data: { code: string; device_info?: string }) =>
    apiClient.post<import('./types').AdminBuybackShipVerifyResult>(
      '/admin/buyback/ship/scan',
      data
    ),
  shipConfirm: (data: {
    package_id: number
    checklist: Record<string, boolean>
    scanned_code?: string
    tracking_number?: string
    shipping_method?: string
    device_info?: string
  }) =>
    apiClient.post<import('./types').AdminBuybackShipVerifyResult>(
      '/admin/buyback/ship/confirm',
      data
    ),
  getLabelLayout: () =>
    apiClient.get<import('./types').AdminBuybackLabelLayout>('/admin/buyback/labels/layout'),
  getLabelSheet: (data: {
    package_ids: number[]
    start_position?: number
    copies?: number
    include_applicant_name?: boolean
  }) =>
    apiClient.post<import('./types').AdminBuybackLabelSheet>('/admin/buyback/labels/sheet', data),
  listLogisticsLogs: (params?: {
    log_type?: string
    request_id?: number
    package_id?: number
    page?: number
    per_page?: number
  }) =>
    apiClient.get<import('./types').AdminBuybackLogisticsLogs>('/admin/buyback/logs', { params }),
}

export const adminSecurityApi = {
  getSession: () => apiClient.get<import('./types').AdminSession>('/admin/security/me'),
  sessionLogin: () => apiClient.post<import('./types').AdminSession>('/admin/security/session/login'),
  sessionLogout: () => apiClient.post('/admin/security/session/logout'),
  reportLoginFailed: (reason?: string) =>
    apiClient.post('/admin/security/session/login-failed', { success: false, reason }),
  reauth: () => apiClient.post<import('./types').AdminSession>('/admin/security/reauth', { confirmed: true }),
  listAdmins: (params?: { page?: number; per_page?: number; q?: string }) =>
    apiClient.get<import('./types').PaginatedAdminUsers>('/admin/security/admins', { params }),
  getAdmin: (id: number) =>
    apiClient.get<import('./types').AdminUserDetail>(`/admin/security/admins/${id}`),
  createAdmin: (data: {
    email: string
    name: string
    role_code: string
    display_name?: string
  }) => apiClient.post<import('./types').AdminUserDetail>('/admin/security/admins', data),
  updateAdmin: (
    id: number,
    data: { role_code?: string; display_name?: string; is_active?: boolean; reason?: string }
  ) => apiClient.patch<import('./types').AdminUserDetail>(`/admin/security/admins/${id}`, data),
  listRoles: () => apiClient.get<import('./types').AdminRole[]>('/admin/security/roles'),
  getPermissionsMatrix: () =>
    apiClient.get<import('./types').AdminPermissionsMatrix>('/admin/security/permissions/matrix'),
  listAuditLogs: (params?: { page?: number; per_page?: number; action?: string }) =>
    apiClient.get<import('./types').PaginatedAuditLogs>('/admin/security/audit-logs', { params }),
  getAuditLog: (id: number) =>
    apiClient.get<import('./types').AdminAuditLog>(`/admin/security/audit-logs/${id}`),
}

export const adminEmailApi = {
  getBrand: () => apiClient.get('/admin/email/brand'),
  updateBrand: (data: Record<string, unknown>) => apiClient.put('/admin/email/brand', data),
  listTemplates: (category?: string) =>
    apiClient.get('/admin/email/templates', { params: category ? { category } : {} }),
  createTemplate: (data: Record<string, unknown>) => apiClient.post('/admin/email/templates', data),
  getBuybackAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/buyback/auto-send'),
  updateBuybackAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/buyback/auto-send', { settings }),
  getKycAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/kyc/auto-send'),
  updateKycAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/kyc/auto-send', { settings }),
  getMemberAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/member/auto-send'),
  updateMemberAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/member/auto-send', { settings }),
  resendMemberEmail: (userId: number, data: { event_key: string; verify_url?: string; reset_url?: string }) =>
    apiClient.post(`/admin/email/member/users/${userId}/resend`, data),
  getLoyaltyAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/loyalty/auto-send'),
  updateLoyaltyAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/loyalty/auto-send', { settings }),
  resendLoyaltyEmail: (userId: number, data: { event_key: string }) =>
    apiClient.post(`/admin/email/loyalty/users/${userId}/resend`, data),
  getInquiryAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/inquiry/auto-send'),
  updateInquiryAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/inquiry/auto-send', { settings }),
  resendInquiryEmail: (inquiryId: number, data: { event_key: string; reply_text?: string }) =>
    apiClient.post(`/admin/email/inquiry/inquiries/${inquiryId}/resend`, data),
  getAdminNotifyEvents: () =>
    apiClient.get<Array<{ event_key: string; template_key: string; label: string; category: string; channel_default: string }>>(
      '/admin/email/admin-notify/events'
    ),
  getAdminNotifyAutoSend: () =>
    apiClient.get<{ settings: Record<string, boolean> }>('/admin/email/admin-notify/auto-send'),
  updateAdminNotifyAutoSend: (settings: Record<string, boolean>) =>
    apiClient.put('/admin/email/admin-notify/auto-send', { settings }),
  getAdminNotifyChannels: () =>
    apiClient.get<{ settings: Record<string, string> }>('/admin/email/admin-notify/channels'),
  updateAdminNotifyChannels: (settings: Record<string, string>) =>
    apiClient.put('/admin/email/admin-notify/channels', { settings }),
  getAdminNotifyRecipients: () =>
    apiClient.get<{ settings: Record<string, { mode: string; permission_codes: string[]; custom_emails: string[] }> }>(
      '/admin/email/admin-notify/recipients'
    ),
  updateAdminNotifyRecipients: (
    settings: Record<string, { mode: string; permission_codes: string[]; custom_emails: string[] }>
  ) => apiClient.put('/admin/email/admin-notify/recipients', { settings }),
  duplicateTemplate: (key: string, data: { new_template_key: string; name?: string; category?: string }) =>
    apiClient.post(`/admin/email/templates/${encodeURIComponent(key)}/duplicate`, data),
  getBroadcastAudiences: () =>
    apiClient.get<{ segments: Array<{ segment_key: string; label: string; description: string; requires_params: boolean }> }>(
      '/admin/email/broadcast/audiences'
    ),
  getTemplate: (key: string) => apiClient.get(`/admin/email/templates/${encodeURIComponent(key)}`),
  getTemplateVariables: (key: string) =>
    apiClient.get<{ variables: string[]; aliases: Record<string, string>; sample: Record<string, string> }>(
      `/admin/email/templates/${encodeURIComponent(key)}/variables`
    ),
  updateTemplate: (key: string, data: Record<string, unknown>) =>
    apiClient.put(`/admin/email/templates/${encodeURIComponent(key)}`, data),
  previewTemplate: (
    key: string,
    payload: {
      variables?: Record<string, string>
      subject?: string
      preheader?: string
      html_body?: string
      text_body?: string
      force_dark?: boolean
    }
  ) =>
    apiClient.post(`/admin/email/templates/${encodeURIComponent(key)}/preview`, payload),
  testSend: (key: string, to_email: string, variables: Record<string, string>) =>
    apiClient.post(`/admin/email/templates/${encodeURIComponent(key)}/test-send`, { to_email, variables }),
  toggleActive: (key: string, is_active: boolean) =>
    apiClient.patch(`/admin/email/templates/${encodeURIComponent(key)}/active?is_active=${is_active}`),
  getSendLogs: (params?: { status?: string; template_key?: string; campaign_id?: number; limit?: number }) =>
    apiClient.get('/admin/email/send-logs', { params }),
  listCampaigns: (limit?: number) =>
    apiClient.get('/admin/email/campaigns', { params: limit ? { limit } : {} }),
  getCampaign: (id: number) => apiClient.get(`/admin/email/campaigns/${id}`),
  retryCampaignFailed: (id: number) => apiClient.post(`/admin/email/campaigns/${id}/retry-failed`),
  retryAllFailed: () => apiClient.post('/admin/email/retry-failed'),
}

export const adminNotificationsApi = {
  getUnreadCount: () =>
    apiClient.get<{ count: number }>('/admin/notifications/unread-count'),
  list: (params?: { unread_only?: boolean; limit?: number }) =>
    apiClient.get<import('./types').AdminInAppNotification[]>('/admin/notifications', { params }),
  markRead: (id: number) => apiClient.patch(`/admin/notifications/${id}/read`),
}

export const adminOrderLogisticsApi = {
  getShipmentLogs: (orderId: number) =>
    apiClient.get<import('./types').OrderShipmentLog[]>(`/admin/orders/${orderId}/shipment-logs`),
  scanOrder: (code: string, deviceInfo?: string) =>
    apiClient.post<import('./types').OrderScanResult>('/admin/orders/scan', {
      code,
      device_info: deviceInfo,
    }),
}

export const adminLiveApi = {
  listStreams: (params?: { status?: string; visibility?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveStreamList>('/admin/live/streams', { params }),
  createStream: (data: {
    title: string
    description?: string
    thumbnail_url?: string
    embed_url?: string
    visibility?: 'public' | 'unlisted'
    scheduled_at?: string
  }) => apiClient.post<import('./types').LiveStream>('/admin/live/streams', data),
  getStream: (id: number) => apiClient.get<import('./types').LiveStream>(`/admin/live/streams/${id}`),
  updateStream: (id: number, data: Record<string, unknown>) =>
    apiClient.patch<import('./types').LiveStream>(`/admin/live/streams/${id}`, data),
  startStream: (id: number) => apiClient.post<import('./types').LiveStream>(`/admin/live/streams/${id}/start`),
  pauseStream: (id: number) => apiClient.post<import('./types').LiveStream>(`/admin/live/streams/${id}/pause`),
  resumeStream: (id: number) => apiClient.post<import('./types').LiveStream>(`/admin/live/streams/${id}/resume`),
  endStream: (id: number) => apiClient.post<import('./types').LiveStream>(`/admin/live/streams/${id}/end`),
  listProducts: (streamId: number) =>
    apiClient.get<import('./types').LiveProduct[]>(`/admin/live/streams/${streamId}/products`),
  addProduct: (streamId: number, data: { card_id: number; display_price?: number; sort_order?: number }) =>
    apiClient.post<import('./types').LiveProduct>(`/admin/live/streams/${streamId}/products`, data),
  activateProduct: (streamId: number, productId: number) =>
    apiClient.post<import('./types').LiveProduct>(
      `/admin/live/streams/${streamId}/products/${productId}/activate`
    ),
  pinProduct: (streamId: number, productId: number) =>
    apiClient.post<import('./types').LiveProduct>(`/admin/live/streams/${streamId}/products/${productId}/pin`),
  listComments: (streamId: number, params?: { q?: string; sender_type?: string; pinned_only?: boolean; cursor?: number; limit?: number }) =>
    apiClient.get<import('./types').LiveCommentList>(`/admin/live/streams/${streamId}/comments`, { params }),
  postStaffComment: (streamId: number, data: { message: string; sender_type?: 'staff' | 'admin' }) =>
    apiClient.post<import('./types').LiveComment>(`/admin/live/streams/${streamId}/comments`, data),
  pinComment: (streamId: number, commentId: number, pinned = true) =>
    apiClient.post<import('./types').LiveComment>(
      `/admin/live/streams/${streamId}/comments/${commentId}/pin`,
      null,
      { params: { pinned } }
    ),
  deleteComment: (streamId: number, commentId: number) =>
    apiClient.delete<import('./types').LiveComment>(`/admin/live/streams/${streamId}/comments/${commentId}`),
  listNgWords: () => apiClient.get<{ id: number; word: string; is_active: boolean; created_at: string }[]>('/admin/live/ng-words'),
  createNgWord: (word: string) => apiClient.post('/admin/live/ng-words', { word }),
  deleteNgWord: (id: number) => apiClient.delete(`/admin/live/ng-words/${id}`),
}

export const liveApi = {
  listStreams: (params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveStreamList>('/live/streams', { params }),
  getStream: (id: number) => apiClient.get<import('./types').LiveStream>(`/live/streams/${id}`),
  listComments: (streamId: number, params?: { q?: string; cursor?: number; limit?: number }) =>
    apiClient.get<import('./types').LiveCommentList>(`/live/streams/${streamId}/comments`, { params }),
  postComment: (streamId: number, message: string) =>
    apiClient.post<import('./types').LiveComment>(`/live/streams/${streamId}/comments`, { message }),
  reportComment: (streamId: number, commentId: number, reason?: string) =>
    apiClient.post(`/live/streams/${streamId}/comments/${commentId}/report`, { reason }),
}

export const adminLiveAuctionApi = {
  list: (streamId: number, params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveAuctionList>(`/admin/live/streams/${streamId}/auctions`, { params }),
  create: (
    streamId: number,
    data: {
      live_product_id: number
      start_price: number
      min_bid_increment?: number
      buy_now_price?: number
      duration_seconds?: number
      extension_seconds?: number
      auto_extend_enabled?: boolean
      max_extensions?: number
      trigger_remaining_seconds?: number
    },
  ) => apiClient.post<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions`, data),
  get: (streamId: number, auctionId: number) =>
    apiClient.get<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}`),
  update: (streamId: number, auctionId: number, data: Record<string, unknown>) =>
    apiClient.patch<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}`, data),
  start: (streamId: number, auctionId: number, data?: { duration_seconds?: number }) =>
    apiClient.post<import('./types').LiveAuction>(
      `/admin/live/streams/${streamId}/auctions/${auctionId}/start`,
      data ?? {},
    ),
  pause: (streamId: number, auctionId: number) =>
    apiClient.post<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}/pause`),
  resume: (streamId: number, auctionId: number) =>
    apiClient.post<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}/resume`),
  finish: (streamId: number, auctionId: number) =>
    apiClient.post<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}/finish`),
  cancel: (streamId: number, auctionId: number) =>
    apiClient.post<import('./types').LiveAuction>(`/admin/live/streams/${streamId}/auctions/${auctionId}/cancel`),
  forceEnd: (streamId: number, auctionId: number) =>
    apiClient.post<import('./types').LiveAuction>(
      `/admin/live/streams/${streamId}/auctions/${auctionId}/force-end`,
    ),
  listBids: (streamId: number, auctionId: number, params?: { limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveBidList>(
      `/admin/live/streams/${streamId}/auctions/${auctionId}/bids`,
      { params },
    ),
}

export const liveAuctionApi = {
  list: (streamId: number, params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveAuctionList>(`/live/streams/${streamId}/auctions`, { params }),
  get: (auctionId: number) => apiClient.get<import('./types').LiveAuction>(`/live/auctions/${auctionId}`),
  listBids: (auctionId: number, params?: { limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveBidList>(`/live/auctions/${auctionId}/bids`, { params }),
  placeBid: (auctionId: number, amount: number, idempotencyKey?: string) =>
    apiClient.post<import('./types').LiveBidPlaceResult>(`/live/auctions/${auctionId}/bids`, {
      amount,
      idempotency_key: idempotencyKey,
    }),
  getPurchaseRight: (auctionId: number) =>
    apiClient.get<import('./types').LiveAuctionPurchaseRight>(`/live/auctions/${auctionId}/purchase-right`),
  purchase: (auctionId: number, data?: Record<string, unknown>) =>
    apiClient.post<import('./types').LiveAuctionPurchaseResult>(`/live/auctions/${auctionId}/purchase`, data ?? {}),
}

export const adminLiveOfferApi = {
  getSettings: (streamId: number) =>
    apiClient.get<import('./types').LiveOfferSettings>(`/admin/live/streams/${streamId}/offers/settings`),
  patchSettings: (streamId: number, data: Partial<import('./types').LiveOfferSettings>) =>
    apiClient.patch<import('./types').LiveOfferSettings>(`/admin/live/streams/${streamId}/offers/settings`, data),
  patchProductOffersEnabled: (streamId: number, productId: number, offers_enabled: boolean) =>
    apiClient.patch<{ id: number; offers_enabled: boolean }>(
      `/admin/live/streams/${streamId}/products/${productId}/offers`,
      { offers_enabled },
    ),
  listOffers: (
    streamId: number,
    params?: { status?: string; sort?: string; order?: string; limit?: number; offset?: number },
  ) => apiClient.get<import('./types').LiveOfferList>(`/admin/live/streams/${streamId}/offers`, { params }),
  getOffer: (streamId: number, offerId: number) =>
    apiClient.get<import('./types').LiveOffer>(`/admin/live/streams/${streamId}/offers/${offerId}`),
  accept: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/accept`,
      review_note ? { review_note } : {},
    ),
  reject: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/reject`,
      review_note ? { review_note } : {},
    ),
  hold: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/hold`,
      review_note ? { review_note } : {},
    ),
}

export const liveOfferApi = {
  listPublic: (streamId: number, params?: { limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveOfferPublicList>(`/live/streams/${streamId}/offers`, { params }),
  listMine: (streamId: number, params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveOfferList>(`/live/streams/${streamId}/offers/mine`, { params }),
  create: (
    streamId: number,
    data: { live_product_id: number; amount: number; idempotency_key?: string },
  ) => apiClient.post<import('./types').LiveOffer>(`/live/streams/${streamId}/offers`, data),
  getPurchaseRight: (offerId: number) =>
    apiClient.get<import('./types').LiveOfferPurchaseRight>(`/live/offers/${offerId}/purchase-right`),
  purchase: (offerId: number, data?: Record<string, unknown>) =>
    apiClient.post<import('./types').LiveOfferPurchaseResult>(`/live/offers/${offerId}/purchase`, data ?? {}),
}

