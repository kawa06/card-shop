export interface Card {
  id: number
  name: string
  name_en: string | null
  description: string
  price: number
  price_usd: number | null
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
  name_en?: string | null
  slug?: string
  description?: string | null
}

export interface Pack {
  id: number
  name: string
  name_en?: string | null
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
  payment_deadline: string | null
  stock_reserved: boolean
  paid_at: string | null
  order_number: string | null
  stripe_payment_intent_id: string | null
  shipping_status: string | null
  shipping_carrier: string | null
  tracking_number: string | null
  shipped_at: string | null
  purchase_email_sent_at: string | null
  shipping_email_sent_at: string | null
  email_send_status: string | null
  admin_note: string | null
  discount_amount?: number
  coupon_code?: string | null
  coupon_name?: string | null
  payment_fee?: number
  packaging_fee?: number
  buyer_note?: string | null
  buyer_phone?: string | null
  click_post_csv_exported_at: string | null
  created_at: string
  updated_at?: string | null
  items: OrderItem[]
  /** Admin list only */
  buyer_name?: string | null
  buyer_email?: string | null
}

export interface AdminOrderDetail extends Order {
  stripe_checkout_session_id?: string | null
}

export interface InvoiceConfigApi {
  invoice_enabled: boolean
  invoice_registration_number: string | null
  invoice_issuer_name: string | null
  default_tax_rate: number
  qualified_invoice_enabled: boolean
}

export interface AdminClickPostOrder {
  id: number
  buyer_name: string
  postal_code: string | null
  region: string | null
  city: string | null
  address_line1: string | null
  address_line2: string | null
  product_names: string
  created_at: string
  payment_status: string | null
  click_post_csv_exported_at: string | null
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

export interface ShippingQuote {
  method_code: string
  fee_jpy: number
  base_shipping_fee_jpy?: number | null
  packaging_fee_jpy?: number | null
  ems_zone?: number | null
  zone_label_ja?: string | null
  zone_label_en?: string | null
  estimated_delivery_min_days?: number | null
  estimated_delivery_max_days?: number | null
  has_insurance?: boolean
  has_tracking?: boolean
  insurance_max_amount?: number | null
  insurance_detail_ja?: string | null
  insurance_detail_en?: string | null
  insurance_note_ja?: string | null
  insurance_note_en?: string | null
  extra_note_ja?: string | null
  extra_note_en?: string | null
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

export interface InquiryMessage {
  id: number
  sender_type: 'customer' | 'admin' | 'system'
  message: string
  is_internal_note: boolean
  template_id: number | null
  created_at: string
  sender_name: string | null
}

export interface InquiryAttachment {
  id: number
  message_id: number | null
  original_filename: string
  mime_type: string
  file_size: number
  created_at: string
  download_url: string | null
}

export interface InquiryListItem {
  id: number
  inquiry_number: string
  category: string
  subject: string
  related_order_number: string | null
  status: string
  priority: string
  last_message_at: string | null
  customer_unread_count: number
  created_at: string
  updated_at: string | null
}

export interface InquiryDetail extends InquiryListItem {
  reply_email: string
  related_order_id: number | null
  related_product_id: number | null
  related_product_name: string | null
  messages: InquiryMessage[]
  attachments: InquiryAttachment[]
}

export interface InquiryTemplate {
  id: number
  template_type: 'customer' | 'admin'
  category: string | null
  name: string
  body: string
  is_active: boolean
  sort_order: number
}

export interface InquiryCreatePayload {
  category: string
  subject: string
  message: string
  reply_email?: string
  related_order_id?: number | null
  related_product_id?: number | null
  template_id?: number | null
}

export interface AdminInquiryListItem extends InquiryListItem {
  buyer_name: string | null
  buyer_email: string | null
  assigned_admin_name: string | null
  admin_unread_count: number
}

export interface AdminInquiryDetail extends AdminInquiryListItem {
  reply_email: string
  related_order_id: number | null
  related_product_id: number | null
  related_product_name: string | null
  messages: InquiryMessage[]
  attachments: InquiryAttachment[]
}

export interface InquiryStats {
  unreplied_count: number
  today_count: number
  in_progress_count: number
  waiting_customer_count: number
  resolved_count: number
  high_priority_count: number
}

export interface InquirySettings {
  enabled: boolean
  attachments_enabled: boolean
  max_attachments: number
  max_attachment_bytes: number
  auto_reply_enabled: boolean
  allow_reopen_resolved: boolean
  auto_close_days: number
}

export interface AdminInquiryReplyPayload {
  message: string
  is_internal_note?: boolean
  template_id?: number | null
  status?: string | null
  assigned_admin_id?: number | null
  reason?: string | null
}

export interface AdminBuybackStats {
  pending_kyc_count: number
  submitted_request_count: number
  in_progress_request_count: number
  payout_pending_count: number
}

export interface AdminBuybackCatalogPrice {
  id?: number
  condition_code: string
  price_normal: number
  price_high?: number | null
  purchase_limit?: number | null
  tier_overflow_price?: number | null
  effective_from?: string | null
}

export interface AdminBuybackCatalogProduct {
  id: number
  name: string
  category: string
  card_number?: string | null
  rarity?: string | null
  pack_name?: string | null
  image_url?: string | null
  notes?: string | null
  is_active: boolean
  sort_order: number
  prices: AdminBuybackCatalogPrice[]
  created_at?: string | null
  updated_at?: string | null
}

export interface AdminBuybackCatalogProductInput {
  name: string
  category: string
  card_number?: string | null
  rarity?: string | null
  pack_name?: string | null
  image_url?: string | null
  notes?: string | null
  is_active: boolean
  sort_order: number
  prices: Array<{
    condition_code: string
    price_normal: number
    price_high?: number | null
    purchase_limit?: number | null
    tier_overflow_price?: number | null
  }>
}

export interface AdminIdentityListItem {
  id: number
  user_id: number
  user_email: string
  user_name: string
  status: string
  status_label: string
  document_type: string | null
  document_type_label: string | null
  has_front: boolean
  has_back: boolean
  submitted_at: string | null
  updated_at: string | null
}

export interface AdminIdentityDetail extends AdminIdentityListItem {
  rejection_reason: string | null
  reviewed_at: string | null
  reviewer_name: string | null
}

export interface AdminBuybackRequestListItem {
  id: number
  request_number: string | null
  status: string
  status_label: string
  user_id: number
  user_email: string
  user_name: string
  item_count: number
  estimated_total: number | null
  payout_total: number | null
  submitted_at: string | null
  created_at: string
}

export interface AdminPayoutAccount {
  id: number
  bank_name: string
  branch_name: string | null
  account_type: string
  account_type_label: string
  account_holder: string
  account_number: string
  account_number_masked: string
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface AdminBuybackStatusHistoryItem {
  id: number
  from_status: string | null
  from_status_label: string | null
  to_status: string
  to_status_label: string
  note: string | null
  created_at: string
}

export interface AdminBuybackRequestItem {
  id: number
  product_id?: number | null
  product_name_snapshot: string
  condition_code: string
  quantity: number
  listed_unit_price: number
  assessed_unit_price?: number | null
  accepted_unit_price?: number | null
  line_status: string | null
  line_status_label?: string | null
  rejection_reason_code?: string | null
  rejection_reason_text?: string | null
  rejection_reason_label?: string | null
  is_return_target?: boolean
  is_disposal_target?: boolean
  return_status?: string | null
  return_status_label?: string | null
  return_tracking_number?: string | null
  return_shipping_cost?: number | null
}

export interface AdminBuybackRejectionReasonOption {
  code: string
  label: string
}

export interface AdminBuybackRequestDetail extends AdminBuybackRequestListItem {
  shipping_method: string | null
  tracking_number: string | null
  customer_note: string | null
  admin_note: string | null
  assessed_total: number | null
  payout_total: number | null
  rejected_item_handling?: string | null
  rejected_item_handling_label?: string | null
  agreed_prepaid_shipping?: boolean
  agreed_cod_consequence?: boolean
  agreed_condition_rejection?: boolean
  items: AdminBuybackRequestItem[]
  status_history: AdminBuybackStatusHistoryItem[]
  allowed_next_statuses: string[]
  payout_account: AdminPayoutAccount | null
  ready_for_payout: boolean
  payout_email_sent: boolean
  paid_at: string | null
  rejection_reason_options?: AdminBuybackRejectionReasonOption[]
}

export interface AdminRole {
  id: number
  code: string
  name: string
  description?: string | null
  is_system: boolean
}

export interface AdminPermission {
  id: number
  code: string
  name: string
  description?: string | null
  category?: string | null
}

export interface AdminUserSummary {
  id: number
  user_id: number
  email: string
  name: string
  display_name?: string | null
  role: AdminRole
  is_active: boolean
  failed_login_count: number
  locked_until?: string | null
  last_login_at?: string | null
  created_at: string
  deactivated_at?: string | null
}

export interface AdminUserDetail extends AdminUserSummary {
  permissions: string[]
  last_login_ip?: string | null
}

export interface AdminAuditLog {
  id: number
  admin_user_id?: number | null
  actor_email?: string | null
  action: string
  resource_type?: string | null
  resource_id?: string | null
  before_data?: string | null
  after_data?: string | null
  reason?: string | null
  result: string
  ip_address?: string | null
  user_agent?: string | null
  created_at: string
}

export interface AdminSession {
  is_admin: boolean
  admin_user_id?: number | null
  role_code?: string | null
  permissions: string[]
  email?: string | null
  reauth_valid: boolean
}

export interface PaginatedAdminUsers {
  items: AdminUserSummary[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface PaginatedAuditLogs {
  items: AdminAuditLog[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface AdminPermissionsMatrix {
  roles: AdminRole[]
  permissions: AdminPermission[]
  role_permissions: Record<string, string[]>
}

export interface AdminBuybackScanItem {
  id: number
  product_name: string
  condition_code: string
  quantity: number
}

export interface AdminBuybackScanHistory {
  id: number
  from_status: string | null
  from_status_label: string | null
  to_status: string
  to_status_label: string
  note: string | null
  created_at: string | null
}

export interface AdminBuybackReceipt {
  id: number
  received_at: string
  received_by_name: string | null
  box_count: number | null
  actual_item_count: number | null
  condition_note: string | null
  admin_note: string | null
  device_info: string | null
}

export interface AdminBuybackScanResult {
  found: boolean
  message?: string | null
  request_id?: number | null
  inbound_shipment_id?: number | null
  barcode_id?: number | null
  request_number?: string | null
  public_buyback_code?: string | null
  inbound_mgmt_id?: string | null
  applicant_name?: string | null
  public_member_id?: string | null
  submitted_at?: string | null
  request_status?: string | null
  request_status_label?: string | null
  inbound_status?: string | null
  inbound_status_label?: string | null
  shipping_method?: string | null
  declared_item_count?: number | null
  actual_item_count?: number | null
  expected_box_count?: number | null
  items?: AdminBuybackScanItem[]
  identity_status?: string | null
  identity_status_label?: string | null
  guardian_status?: string | null
  guardian_status_label?: string | null
  admin_note?: string | null
  logistics_note?: string | null
  already_received?: boolean
  is_cancelled?: boolean
  can_receive?: boolean
  status_history?: AdminBuybackScanHistory[]
  receipts?: AdminBuybackReceipt[]
  notices?: string[]
  user_email?: string | null
  phone_number?: string | null
  address?: {
    postal_code?: string | null
    region?: string | null
    city?: string | null
    address_line1?: string | null
    address_line2?: string | null
  } | null
}

export interface AdminBuybackPackageItem {
  request_item_id: number
  quantity: number
  product_name?: string | null
  condition_code?: string | null
}

export interface AdminBuybackPackage {
  id: number
  request_id: number
  package_code: string
  package_kind: string
  package_kind_label?: string | null
  box_index: number
  total_boxes: number
  return_reference?: string | null
  shipping_method?: string | null
  preferred_ship_date?: string | null
  preferred_time_slot?: string | null
  tracking_number?: string | null
  status: string
  status_label?: string | null
  packed_by_name?: string | null
  packed_at?: string | null
  shipped_at?: string | null
  admin_note?: string | null
  barcode_human_readable?: string | null
  items?: AdminBuybackPackageItem[]
  created_at?: string | null
}

export interface AdminBuybackPackageLabel extends AdminBuybackPackage {
  shop_name: string
  public_buyback_code?: string | null
  request_number?: string | null
  inbound_mgmt_id?: string | null
  applicant_name?: string | null
  destination_name?: string | null
  destination_phone?: string | null
  destination_address?: {
    postal_code?: string | null
    region?: string | null
    city?: string | null
    address_line1?: string | null
    address_line2?: string | null
  } | null
  request_status?: string | null
  request_status_label?: string | null
  item_count: number
  handling_note: string
  is_reprint: boolean
}

export interface AdminBuybackShipCheckItem {
  code: string
  label: string
}

export interface AdminBuybackShipVerifyResult {
  found: boolean
  message?: string | null
  package_id?: number | null
  barcode_id?: number | null
  package_code?: string | null
  package_kind?: string | null
  package_kind_label?: string | null
  box_index?: number | null
  total_boxes?: number | null
  request_id?: number | null
  request_number?: string | null
  public_buyback_code?: string | null
  return_reference?: string | null
  request_status?: string | null
  request_status_label?: string | null
  package_status?: string | null
  package_status_label?: string | null
  shipping_method?: string | null
  preferred_ship_date?: string | null
  preferred_time_slot?: string | null
  tracking_number?: string | null
  applicant_name?: string | null
  destination_name?: string | null
  destination_phone?: string | null
  destination_address?: {
    postal_code?: string | null
    region?: string | null
    city?: string | null
    address_line1?: string | null
    address_line2?: string | null
  } | null
  items?: AdminBuybackPackageItem[]
  checklist_items?: AdminBuybackShipCheckItem[]
  warnings?: string[]
  notices?: string[]
  already_shipped?: boolean
  is_cancelled?: boolean
  address_complete?: boolean
  can_confirm?: boolean
}

export interface AdminBuybackLabelLayout {
  product_code: string
  format_code: string
  sheet_width_mm: number
  sheet_height_mm: number
  label_width_mm: number
  label_height_mm: number
  columns: number
  rows: number
  faces: number
  gap_h_mm: number
  gap_v_mm: number
  margin_left_mm: number
  margin_top_mm: number
  margin_right_mm: number
  margin_bottom_mm: number
  margins_confirmed: boolean
  margins_note: string
  source_url: string
  shop_name: string
}

export interface AdminBuybackLabelSheetCell {
  package_id: number
  package_code: string
  barcode_human_readable?: string | null
  public_buyback_code?: string | null
  request_number?: string | null
  inbound_mgmt_id?: string | null
  box_index?: number | null
  total_boxes?: number | null
  package_kind?: string | null
  package_kind_label?: string | null
  applicant_name?: string | null
  handling_note?: string
  shop_name?: string
  title?: string | null
}

export interface AdminBuybackLabelSheet {
  layout: AdminBuybackLabelLayout
  start_position: number
  copies: number
  labels: AdminBuybackLabelSheetCell[]
}

export interface AdminBuybackLogisticsLog {
  id: string
  log_type: string
  action: string
  result?: string | null
  actor_user_id?: number | null
  actor_name?: string | null
  request_id?: number | null
  package_id?: number | null
  entity_type?: string | null
  entity_id?: string | null
  includes_pii?: boolean | null
  is_reprint?: boolean | null
  details?: Record<string, unknown> | null
  device_info?: string | null
  ip_address?: string | null
  created_at?: string | null
}

export interface AdminBuybackLogisticsLogs {
  items: AdminBuybackLogisticsLog[]
  total: number
  page: number
  per_page: number
  pages: number
}
