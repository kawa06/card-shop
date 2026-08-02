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
]

const PUBLIC_API_PATHS = ['/payments/stripe/config', '/inquiries/meta/categories']

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
  listRequests: (params?: { status?: string; q?: string }) =>
    apiClient.get<import('./types').AdminBuybackRequestListItem[]>('/admin/buyback/requests', {
      params,
    }),
  getRequest: (id: number) =>
    apiClient.get<import('./types').AdminBuybackRequestDetail>(`/admin/buyback/requests/${id}`),
  updateRequest: (
    id: number,
    data: {
      status: string
      admin_note?: string
      tracking_number?: string
      assessed_total?: number
      payout_total?: number
    }
  ) => apiClient.patch<import('./types').AdminBuybackRequestDetail>(`/admin/buyback/requests/${id}`, data),
  updateRequestItems: (
    id: number,
    data: {
      items: Array<{
        id: number
        line_status?: string
        assessed_unit_price?: number | null
        accepted_unit_price?: number | null
        rejection_reason_code?: string | null
        rejection_reason_text?: string | null
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
