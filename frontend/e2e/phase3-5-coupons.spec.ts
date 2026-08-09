import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-5-coupons')
const TEST_EMAIL = 'rikukai0609@icloud.com'

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function ensureAdminSession(page: import('@playwright/test').Page) {
  if (!page.url().includes('/admin')) {
    await page.goto('/admin/coupons', { waitUntil: 'domcontentloaded' })
  }
}

async function resolveTestUser(page: import('@playwright/test').Page) {
  await ensureAdminSession(page)
  const usersRes = await page.request.get('/api/admin/users', { params: { q: TEST_EMAIL } })
  expect(usersRes.ok(), await usersRes.text()).toBeTruthy()
  const users = (await usersRes.json()) as Array<{ id: number; email: string }>
  const user = users.find((u) => u.email.toLowerCase() === TEST_EMAIL.toLowerCase()) ?? users[0]
  expect(user?.id).toBeTruthy()
  return user
}

async function waitForBackendAuth(page: import('@playwright/test').Page) {
  await page.goto('/mypage/coupons', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-coupons-heading')).toBeVisible({ timeout: 60_000 })
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('auth_token')), {
      timeout: 60_000,
      message: 'backend JWT missing after mypage auth sync',
    })
    .toBeTruthy()
}

async function getUserAuthHeaders(page: import('@playwright/test').Page) {
  await waitForBackendAuth(page)
  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(token).toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

async function findOrCreateSellableCard(page: import('@playwright/test').Page) {
  const cardsRes = await page.request.get('/api/cards', { params: { per_page: 50, page: 1 } })
  expect(cardsRes.ok(), await cardsRes.text()).toBeTruthy()
  const payload = (await cardsRes.json()) as {
    items?: Array<{ id: number; price?: number; stock?: number; is_active?: boolean }>
  }
  let card =
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) >= 3 && (c.price ?? 0) >= 500) ??
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) > 0)

  if (!card?.id) {
    await ensureAdminSession(page)
    const createRes = await page.request.post('/api/admin/cards', {
      data: {
        name: `E2E Coupon Card ${Date.now()}`,
        price: 1500,
        stock: 20,
        condition: 'a',
        is_active: true,
        allowed_shipping_methods: JSON.stringify(['takkyubin_compact']),
      },
    })
    expect(createRes.ok(), await createRes.text()).toBeTruthy()
    card = (await createRes.json()) as { id: number; price?: number; stock?: number }
  }
  expect(card?.id).toBeTruthy()
  return card!
}

async function clearUserCart(page: import('@playwright/test').Page, authHeaders: Record<string, string>) {
  const cartRes = await page.request.get('/api/cart', { headers: authHeaders })
  if (!cartRes.ok()) return
  const items = (await cartRes.json()) as Array<{ id: number }>
  for (const item of items) {
    await page.request.delete(`/api/cart/${item.id}`, { headers: authHeaders })
  }
}

async function addCardToCart(
  page: import('@playwright/test').Page,
  authHeaders: Record<string, string>,
  cardId: number,
  quantity = 1,
) {
  const res = await page.request.post('/api/cart', {
    headers: authHeaders,
    data: { card_id: cardId, quantity },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
}

function defaultCheckoutPayload() {
  return {
    postal_code: '6500001',
    country: 'Japan',
    region: '\u5175\u5eab\u770c',
    city: '\u795e\u6238\u5e02\u4e2d\u592e\u533a',
    address_line1: 'E2E\u30c6\u30b9\u30c81-1',
    address_line2: '',
    shipping_address: '\u5175\u5eab\u770c\u795e\u6238\u5e02\u4e2d\u592e\u533aE2E\u30c6\u30b9\u30c81-1',
    shipping_method: 'takkyubin_compact',
    locale: 'ja',
    checkout_type: 'card',
  }
}

async function createCoupon(
  page: import('@playwright/test').Page,
  data: Record<string, unknown>,
) {
  await ensureAdminSession(page)
  const res = await page.request.post('/api/admin/coupons', { data })
  expect(res.ok() || res.status() === 201, await res.text()).toBeTruthy()
  return (await res.json()) as { id: number; code: string; name: string; coupon_type: string }
}

test('Scenario 1: admin create fixed/percent/free_shipping + CSV', async ({ page }) => {
  await page.goto('/admin/coupons', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('admin-coupons-heading')).toBeVisible({ timeout: 60_000 })
  await shot(page, '01-admin-coupons')

  const stamp = Date.now()
  const fixed = await createCoupon(page, {
    code: `FIX${stamp}`,
    name: 'E2E Fixed',
    coupon_type: 'fixed_amount',
    amount_yen: 500,
    audience: 'public',
    max_uses_per_user: 5,
  })
  const percent = await createCoupon(page, {
    code: `PCT${stamp}`,
    name: 'E2E Percent',
    coupon_type: 'percent',
    percent_off: 10,
    audience: 'public',
    max_uses_per_user: 5,
  })
  const ship = await createCoupon(page, {
    code: `SHIP${stamp}`,
    name: 'E2E Free Ship',
    coupon_type: 'free_shipping',
    audience: 'public',
    max_uses_per_user: 5,
  })
  expect(fixed.code).toBeTruthy()
  expect(percent.code).toBeTruthy()
  expect(ship.code).toBeTruthy()

  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByText(fixed.code)).toBeVisible({ timeout: 30_000 })
  await shot(page, '02-admin-coupons-created')

  const csv = await page.request.get('/api/admin/coupons/export.csv')
  expect(csv.ok(), await csv.text()).toBeTruthy()
  const csvText = await csv.text()
  expect(csvText).toContain(fixed.code)
  await shot(page, '03-admin-csv-smoke')
})

test('Scenario 2: checkout preview apply with points + unpaid cancel restore', async ({ page }) => {
  const stamp = Date.now()
  const coupon = await createCoupon(page, {
    code: `CHK${stamp}`,
    name: 'E2E Checkout',
    coupon_type: 'fixed_amount',
    amount_yen: 300,
    audience: 'public',
    max_uses_per_user: 10,
  })

  const user = await resolveTestUser(page)
  await ensureAdminSession(page)
  await page.request.post('/api/admin/points/grant', {
    data: {
      user_id: user.id,
      amount: 5000,
      reason: 'E2E coupon stack',
      idempotency_key: `e2e-cpn-pts-${stamp}`,
    },
  })

  const authHeaders = await getUserAuthHeaders(page)
  const card = await findOrCreateSellableCard(page)
  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)

  const unitPrice = Math.round(card.price ?? 1000)
  const preview = await page.request.post('/api/coupons/checkout-preview', {
    headers: authHeaders,
    data: {
      coupon_code: coupon.code,
      items_subtotal: unitPrice,
      shipping_fee: 650,
      cart_items: [{ card_id: card.id, quantity: 1, unit_price: unitPrice }],
      requested_points: 100,
    },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const previewBody = (await preview.json()) as { valid: boolean; discount_amount: number }
  expect(previewBody.valid).toBeTruthy()
  expect(previewBody.discount_amount).toBe(300)

  await page.goto('/cart', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /\u8cfc\u5165\u624b\u7d9a\u304d\u3078|Proceed to checkout/i }).click()
  await expect(page.getByRole('heading', { name: /\u6ce8\u6587\u78ba\u8a8d|Checkout/i })).toBeVisible({
    timeout: 60_000,
  })
  await page.getByTestId('checkout-coupon-input').fill(coupon.code)
  await expect(page.getByTestId('checkout-coupon-applied')).toBeVisible({ timeout: 60_000 })
  await shot(page, '04-checkout-coupon-apply')

  const checkoutRes = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: {
      ...defaultCheckoutPayload(),
      coupon_code: coupon.code,
      points_to_use: 100,
    },
  })
  expect(checkoutRes.ok(), await checkoutRes.text()).toBeTruthy()
  const checkout = (await checkoutRes.json()) as { order_id: number; session_id: string }
  expect(checkout.order_id).toBeTruthy()

  const orderRes = await page.request.get(`/api/orders/${checkout.order_id}`, { headers: authHeaders })
  expect(orderRes.ok(), await orderRes.text()).toBeTruthy()
  const order = (await orderRes.json()) as {
    discount_amount?: number
    coupon_code?: string
    points_used?: number
  }
  expect(order.coupon_code).toBe(coupon.code)
  expect(order.discount_amount).toBe(300)
  expect(order.points_used).toBe(100)

  await page.goto('/orders', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: /\u6ce8\u6587\u5c65\u6b74/i })).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-order-breakdown')

  await ensureAdminSession(page)
  const cancelRes = await page.request.post(`/api/admin/orders/${checkout.order_id}/cancel`)
  expect(cancelRes.ok(), await cancelRes.text()).toBeTruthy()

  const reusePreview = await page.request.post('/api/coupons/checkout-preview', {
    headers: authHeaders,
    data: {
      coupon_code: coupon.code,
      items_subtotal: unitPrice,
      shipping_fee: 650,
      cart_items: [{ card_id: card.id, quantity: 1, unit_price: unitPrice }],
    },
  })
  expect(reusePreview.ok(), await reusePreview.text()).toBeTruthy()
  expect(((await reusePreview.json()) as { valid: boolean }).valid).toBeTruthy()
})

test('Scenario 3: mypage assigned list + reject expired/min/over-limit', async ({ page }) => {
  const stamp = Date.now()
  const user = await resolveTestUser(page)
  const assigned = await createCoupon(page, {
    code: `ASN${stamp}`,
    name: 'E2E Assigned',
    coupon_type: 'fixed_amount',
    amount_yen: 200,
    audience: 'assigned',
    max_uses_per_user: 1,
  })
  await ensureAdminSession(page)
  const assignRes = await page.request.post(`/api/admin/coupons/${assigned.id}/assign`, {
    data: { user_id: user.id },
  })
  expect(assignRes.ok(), await assignRes.text()).toBeTruthy()

  const expired = await createCoupon(page, {
    code: `EXP${stamp}`,
    name: 'E2E Expired',
    coupon_type: 'fixed_amount',
    amount_yen: 100,
    audience: 'public',
    ends_at: new Date(Date.now() - 86400000).toISOString(),
  })
  const minOnly = await createCoupon(page, {
    code: `MIN${stamp}`,
    name: 'E2E Min',
    coupon_type: 'fixed_amount',
    amount_yen: 100,
    audience: 'public',
    min_subtotal_yen: 999999,
  })
  const once = await createCoupon(page, {
    code: `ONCE${stamp}`,
    name: 'E2E Once',
    coupon_type: 'fixed_amount',
    amount_yen: 100,
    audience: 'public',
    max_uses_total: 1,
    max_uses_per_user: 1,
  })

  const authHeaders = await getUserAuthHeaders(page)
  await page.goto('/mypage/coupons', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-coupons-heading')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(assigned.code)).toBeVisible({ timeout: 30_000 })
  await shot(page, '06-mypage-coupons')
  await page.setViewportSize({ width: 390, height: 844 })
  await shot(page, '07-mypage-coupons-mobile')
  await page.setViewportSize({ width: 1280, height: 720 })

  const card = await findOrCreateSellableCard(page)
  const unitPrice = Math.round(card.price ?? 1000)

  const expiredPreview = await page.request.post('/api/coupons/checkout-preview', {
    headers: authHeaders,
    data: {
      coupon_code: expired.code,
      items_subtotal: unitPrice,
      shipping_fee: 650,
      cart_items: [{ card_id: card.id, quantity: 1, unit_price: unitPrice }],
    },
  })
  expect(expiredPreview.ok()).toBeTruthy()
  expect(((await expiredPreview.json()) as { valid: boolean }).valid).toBeFalsy()

  const minPreview = await page.request.post('/api/coupons/checkout-preview', {
    headers: authHeaders,
    data: {
      coupon_code: minOnly.code,
      items_subtotal: unitPrice,
      shipping_fee: 650,
      cart_items: [{ card_id: card.id, quantity: 1, unit_price: unitPrice }],
    },
  })
  expect(minPreview.ok()).toBeTruthy()
  expect(((await minPreview.json()) as { valid: boolean }).valid).toBeFalsy()

  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)
  const firstUse = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: { ...defaultCheckoutPayload(), coupon_code: once.code },
  })
  expect(firstUse.ok(), await firstUse.text()).toBeTruthy()
  const firstOrder = (await firstUse.json()) as { order_id: number }

  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)
  const secondUse = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: { ...defaultCheckoutPayload(), coupon_code: once.code },
  })
  expect(secondUse.ok()).toBeFalsy()

  await ensureAdminSession(page)
  await page.request.post(`/api/admin/orders/${firstOrder.order_id}/cancel`)
})
