export interface Card {
  id: number
  name: string
  name_en: string | null
  description: string
  price: number
  stock: number
  image_url: string | null
  image_urls: string | null  // JSON array string e.g. '["url1","url2"]'
  rarity: string
  condition: string | null   // a/b/c/d/e
  allowed_shipping_methods: string | null // JSON array string e.g. '["takkyubin_compact"]'
  category_id: number | null
  category?: Category
  pack_id: number | null
  pack?: Pack
  is_active: boolean
  created_at: string
}

export interface Category {
  id: number
  name: string
  description: string | null
}

export interface Pack {
  id: number
  name: string
  slug: string
  sort_order: number
}

export interface Announcement {
  id: number
  title: string
  content: string
  is_active: boolean
  created_at: string
}

export interface User {
  id: number
  email: string
  name: string
  is_admin: boolean
  is_verified: boolean
  postal_code: string | null
  country: string | null
  region: string | null
  city: string | null
  address_line1: string | null
  address_line2: string | null
  address: string | null
  phone_number: string | null
  phone_verified: boolean
  created_at: string
}

export interface CartItem {
  id: number
  card_id: number
  quantity: number
  card: Card
}

export interface Favorite {
  id: number
  card_id: number
  created_at: string
  card: Card
}

export interface Cart {
  items: CartItem[]
  total: number
}

export interface OrderItem {
  id: number
  card_id: number
  quantity: number
  unit_price: number
  card: Card
}

export interface Order {
  id: number
  user_id: number
  status: string
  total_amount: number
  postal_code: string | null
  country: string | null
  region: string | null
  city: string | null
  address_line1: string | null
  address_line2: string | null
  shipping_address: string | null
  shipping_method: string | null
  shipping_fee: number
  payment_method: string | null
  payment_status: string | null
  created_at: string
  items: OrderItem[]
}

export interface ShippingRate {
  method_code: string
  carrier?: string
  name_ja: string
  name_en: string
  fee_jpy: number
  has_tracking: boolean
  has_insurance: boolean
  is_individual_available: boolean
  is_international_available: boolean
  international_zones?: string // JSON string
  max_weight_international?: number
  insurance_max_amount?: number
  insurance_url?: string
  estimated_delivery_min_days?: number
  estimated_delivery_max_days?: number
  is_recommended: boolean
  regional_rates?: string // JSON string
  max_size: string | null
  max_weight: string | null
  source_url: string | null
  updated_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface PasswordChangeRequest {
  old_password: string
  new_password: string
}
