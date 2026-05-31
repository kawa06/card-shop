export interface Card {
  id: number
  name: string
  description: string
  price: number
  stock: number
  image_url: string | null
  rarity: string
  category_id: number | null
  category?: Category
  created_at: string
}

export interface Category {
  id: number
  name: string
  description: string | null
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
  created_at: string
}

export interface CartItem {
  id: number
  card_id: number
  quantity: number
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
  price: number
  card: Card
}

export interface Order {
  id: number
  user_id: number
  status: string
  total: number
  shipping_address: string | null
  created_at: string
  items: OrderItem[]
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
