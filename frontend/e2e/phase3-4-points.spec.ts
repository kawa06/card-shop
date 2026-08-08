import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-4-points')
const TEST_EMAIL = 'rikukai0609@icloud.com'

/** Serial flow: grant balance is reused in later scenarios. */
let expectedAvailablePoints: number | null = null

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

function formatMypageBalance(points: number): string {
  return `${points.toLocaleString('ja-JP')}pt`
}

async function ensureAdminSession(page: import('@playwright/test').Page) {
  if (!page.url().includes('/admin')) {
    await page.goto('/admin/points', { waitUntil: 'domcontentloaded' })
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

async function getAdminUserPoints(page: import('@playwright/test').Page, userId: number) {
  await ensureAdminSession(page)
  const res = await page.request.get(`/api/admin/points/users/${userId}`)
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as { available_points: number; reserved_points: number }
}

async function grantPoints(
  page: import('@playwright/test').Page,
  userId: number,
  amount: number,
  reason: string,
  idempotencyKey: string,
) {
  const grant = await page.request.post('/api/admin/points/grant', {
    data: { user_id: userId, amount, reason, idempotency_key: idempotencyKey },
  })
  expect(grant.ok(), await grant.text()).toBeTruthy()
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
        name: `E2E Points Card ${Date.now()}`,
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

  expect(card?.id, 'No sellable card for checkout E2E').toBeTruthy()
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
    region: '兵庫県',
    city: '神戸市中央区',
    address_line1: 'E2Eテスト1-1',
    address_line2: '',
    shipping_address: '兵庫県神戸市中央区E2Eテスト1-1',
    shipping_method: 'takkyubin_compact',
    locale: 'ja',
    checkout_type: 'card',
  }
}

async function fetchShippingQuote(page: import('@playwright/test').Page, authHeaders: Record<string, string>) {
  const res = await page.request.get('/api/shipping-rates/calculate', {
    headers: authHeaders,
    params: { method_code: 'takkyubin_compact', region: '兵庫県', country: 'Japan' },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as {
    fee_jpy?: number
    base_shipping_fee_jpy?: number
    packaging_fee_jpy?: number
  }
}

async function openCheckoutFromCart(page: import('@playwright/test').Page) {
  await page.goto('/cart', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: /ショッピングカート|Shopping Cart/i })).toBeVisible({
    timeout: 60_000,
  })
  await page.getByRole('button', { name: /購入手続きへ|Proceed to checkout/i }).click()
  await expect(page.getByRole('heading', { name: /注文確認|Checkout/i })).toBeVisible({ timeout: 60_000 })
}

async function fillCheckoutAddress(page: import('@playwright/test').Page) {
  await openCheckoutFromCart(page)
  const postal = page.locator('#postalCode').first()
  if (await postal.isVisible().catch(() => false)) await postal.fill('6500001')
  const region = page.locator('select').filter({ has: page.locator('option', { hasText: '兵庫県' }) }).first()
  if (await region.isVisible().catch(() => false)) await region.selectOption({ label: '兵庫県' })
  const city = page.locator('#city').first()
  if (await city.isVisible().catch(() => false)) await city.fill('神戸市中央区')
  const line1 = page.locator('#addressLine1').first()
  if (await line1.isVisible().catch(() => false)) await line1.fill('E2Eテスト1-1')
  const fullName = page.locator('#fullName').first()
  if (await fullName.isVisible().catch(() => false)) await fullName.fill('E2E Test User')
}

async function ensureFullPointsCheckoutSettings(page: import('@playwright/test').Page) {
  await ensureAdminSession(page)
  const patch = await page.request.patch('/api/admin/points/settings', {
    data: { max_usage_percent: 100, points_apply_to_shipping: true },
  })
  expect(patch.ok(), await patch.text()).toBeTruthy()
}

async function getUserPointHistory(page: import('@playwright/test').Page, authHeaders: Record<string, string>) {
  const res = await page.request.get('/api/points/history', { headers: authHeaders, params: { limit: 20 } })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as { items: Array<{ type: string; amount: number; order_id?: number | null }> }
}

async function waitForMypagePointsReady(page: import('@playwright/test').Page) {
  const loading = page.getByText('読み込み中...')
  const heading = page.getByRole('heading', { name: 'ポイント', exact: true })
  const balanceEl = page.locator('p.text-4xl')

  const attemptLoad = async (clearToken: boolean) => {
    if (clearToken) {
      await page.evaluate(() => localStorage.removeItem('auth_token'))
      await page.reload({ waitUntil: 'domcontentloaded' })
    } else {
      await page.goto('/mypage/points', { waitUntil: 'domcontentloaded' })
    }

    await expect(heading).toBeVisible({ timeout: 60_000 })

    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('auth_token')), {
        timeout: 60_000,
        message: 'backend JWT missing after mypage auth sync',
      })
      .toBeTruthy()

    const token = await page.evaluate(() => localStorage.getItem('auth_token'))
    const authHeaders = { Authorization: `Bearer ${token}` }
    const balanceApi = await page.request.get('/api/points/balance', { headers: authHeaders })
    expect(balanceApi.ok(), await balanceApi.text()).toBeTruthy()
    const historyApi = await page.request.get('/api/points/history', {
      headers: authHeaders,
      params: { limit: 20 },
    })
    expect(historyApi.ok(), await historyApi.text()).toBeTruthy()

    await expect(loading).toBeHidden({ timeout: 90_000 })
    await expect(balanceEl).toBeVisible({ timeout: 30_000 })
  }

  try {
    await attemptLoad(false)
  } catch {
    await attemptLoad(true)
  }
}

async function waitForPointLedgerType(
  page: import('@playwright/test').Page,
  authHeaders: Record<string, string>,
  type: string,
) {
  await expect
    .poll(
      async () => {
        const history = await getUserPointHistory(page, authHeaders)
        return history.items.some((tx) => tx.type === type)
      },
      { timeout: 60_000, message: `expected ${type} ledger row` },
    )
    .toBe(true)
}

async function getUserAuthHeaders(page: import('@playwright/test').Page) {
  await waitForMypagePointsReady(page)

  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(token, 'backend JWT missing after mypage auth sync').toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

test('Scenario 1: admin grant and mypage balance', async ({ page }) => {
  await page.goto('/admin/points', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'ポイント管理' })).toBeVisible({ timeout: 60_000 })
  await shot(page, '01-admin-points')

  const user = await resolveTestUser(page)
  const grantKey = `e2e-grant-${Date.now()}`
  const grant = await page.request.post('/api/admin/points/grant', {
    data: { user_id: user.id, amount: 1000, reason: 'E2E grant', idempotency_key: grantKey },
  })
  expect(grant.ok(), await grant.text()).toBeTruthy()

  const history = await page.request.get(`/api/admin/points/users/${user.id}/history`, { params: { limit: 10 } })
  expect(history.ok(), await history.text()).toBeTruthy()
  const historyBody = (await history.json()) as { items: Array<{ type: string }> }
  expect(historyBody.items.some((tx) => tx.type === 'admin_grant')).toBeTruthy()

  expectedAvailablePoints = (await getAdminUserPoints(page, user.id)).available_points

  await waitForMypagePointsReady(page)
  await expect(
    page.locator('p.text-4xl').filter({ hasText: formatMypageBalance(expectedAvailablePoints) }),
  ).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('付与').first()).toBeVisible()
  await shot(page, '02-mypage-balance')
})

test('Scenario 2: partial points full checkout flow', async ({ page }) => {
  const user = await resolveTestUser(page)
  const authHeaders = await getUserAuthHeaders(page)
  const card = await findOrCreateSellableCard(page)

  await grantPoints(page, user.id, 20000, 'E2E partial checkout', `e2e-partial-grant-${Date.now()}`)
  const beforePoints = await getAdminUserPoints(page, user.id)

  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)

  const unitPrice = Math.round(card.price ?? 1000)
  const quote = await fetchShippingQuote(page, authHeaders)
  const shippingFee = Math.round(quote.fee_jpy ?? quote.base_shipping_fee_jpy ?? 650)
  const requestedPoints = Math.min(500, Math.max(100, Math.floor(unitPrice * 0.2)))

  const preview = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: { items_subtotal: unitPrice, shipping_fee: shippingFee, requested_points: requestedPoints },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const previewBody = (await preview.json()) as {
    applied_points: number
    total_yen: number
    max_usable_points: number
  }
  expect(previewBody.applied_points).toBeGreaterThan(0)
  expect(previewBody.total_yen).toBeLessThan(unitPrice + shippingFee)

  const checkoutRes = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: { ...defaultCheckoutPayload(), points_to_use: previewBody.applied_points },
  })
  const checkoutRaw = await checkoutRes.text()
  expect(checkoutRes.ok(), checkoutRaw).toBeTruthy()
  const checkout = JSON.parse(checkoutRaw) as {
    checkout_url: string
    session_id: string
    order_id: number
  }
  expect(checkout.session_id).not.toMatch(/^points-only-/)
  expect(checkout.checkout_url).toMatch(/stripe\.com|checkout\.stripe\.com/)

  const orderRes = await page.request.get(`/api/orders/${checkout.order_id}`, { headers: authHeaders })
  expect(orderRes.ok(), await orderRes.text()).toBeTruthy()
  const order = (await orderRes.json()) as { points_used?: number }
  expect(order.points_used).toBe(previewBody.applied_points)

  const afterReserve = await getAdminUserPoints(page, user.id)
  expect(afterReserve.available_points).toBeLessThan(beforePoints.available_points)
  expect(afterReserve.reserved_points).toBeGreaterThanOrEqual(
    beforePoints.reserved_points + previewBody.applied_points,
  )

  const history = await getUserPointHistory(page, authHeaders)
  expect(history.items.some((tx) => tx.type === 'reserve')).toBeTruthy()

  await fillCheckoutAddress(page)
  const pointsInput = page.locator('#points')
  await pointsInput.fill('')
  await pointsInput.pressSequentially(String(requestedPoints), { delay: 20 })
  await pointsInput.blur()
  await expect(page.getByText(/pt 適用|pt applied/i).first()).toBeVisible({ timeout: 60_000 })
  await shot(page, '03-checkout-preview-partial')

  await page.goto('/orders', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: /注文履歴/i })).toBeVisible({ timeout: 30_000 })
  await shot(page, '04-orders-partial-points')

  await ensureAdminSession(page)
  const cancelRes = await page.request.post(`/api/admin/orders/${checkout.order_id}/cancel`)
  expect(cancelRes.ok(), await cancelRes.text()).toBeTruthy()
  await expect
    .poll(async () => (await getAdminUserPoints(page, user.id)).reserved_points, {
      timeout: 30_000,
      message: 'Scenario 2 cancel should release this order reservation',
    })
    .toBe(beforePoints.reserved_points)
})

test('Scenario 3: zero-yen full points checkout skips Stripe', async ({ page }) => {
  await ensureFullPointsCheckoutSettings(page)
  const user = await resolveTestUser(page)
  const authHeaders = await getUserAuthHeaders(page)
  const card = await findOrCreateSellableCard(page)

  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)

  const unitPrice = Math.round(card.price ?? 1000)
  const quote = await fetchShippingQuote(page, authHeaders)
  const baseShipping = Math.round(quote.base_shipping_fee_jpy ?? quote.fee_jpy ?? 650)
  const packagingFee = Math.round(quote.packaging_fee_jpy ?? 0)
  const totalBeforePoints = unitPrice + baseShipping + packagingFee

  await grantPoints(page, user.id, 50000, 'E2E zero checkout', `e2e-zero-grant-${Date.now()}`)
  const acct = await getAdminUserPoints(page, user.id)
  expect(acct.available_points).toBeGreaterThanOrEqual(totalBeforePoints)

  const capPreview = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: {
      items_subtotal: unitPrice,
      shipping_fee: baseShipping,
      packaging_fee: packagingFee,
      requested_points: 1,
    },
  })
  expect(capPreview.ok(), await capPreview.text()).toBeTruthy()
  const capBody = (await capPreview.json()) as { max_usable_points: number }
  expect(capBody.max_usable_points).toBeGreaterThan(0)

  const preview = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: {
      items_subtotal: unitPrice,
      shipping_fee: baseShipping,
      packaging_fee: packagingFee,
      requested_points: capBody.max_usable_points,
    },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const previewBody = (await preview.json()) as {
    applied_points: number
    total_yen: number
    max_usable_points: number
  }
  expect(previewBody.max_usable_points).toBeGreaterThan(0)
  expect(previewBody.applied_points).toBeGreaterThan(0)
  expect(previewBody.total_yen).toBe(0)

  await fillCheckoutAddress(page)
  await page.locator('#points').fill(String(previewBody.applied_points))
  await shot(page, '05-checkout-preview-zero')

  const checkoutRes = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: { ...defaultCheckoutPayload(), points_to_use: previewBody.applied_points },
  })
  expect(checkoutRes.ok(), await checkoutRes.text()).toBeTruthy()
  const checkout = (await checkoutRes.json()) as {
    checkout_url: string
    session_id: string
    order_id: number
  }
  expect(checkout.session_id).toMatch(/^points-only-/)
  expect(checkout.checkout_url).not.toMatch(/stripe\.com/)
  expect(checkout.checkout_url).toMatch(/checkout\/success/)

  const confirmRes = await page.request.get('/api/payments/stripe/confirm', {
    headers: authHeaders,
    params: { session_id: checkout.session_id },
  })
  expect(confirmRes.ok(), await confirmRes.text()).toBeTruthy()

  const successPath = checkout.checkout_url.replace(/^https?:\/\/[^/]+/, '')
  await page.goto(successPath, { waitUntil: 'domcontentloaded' })
  await expect(page.getByText(/決済が完了しました|ご注文ありがとう|購入完了|注文が完了/i).first()).toBeVisible({ timeout: 60_000 })
  await shot(page, '06-checkout-success-zero')

  const orderRes = await page.request.get(`/api/orders/${checkout.order_id}`, { headers: authHeaders })
  expect(orderRes.ok()).toBeTruthy()
  const order = (await orderRes.json()) as { points_used?: number; payment_status?: string }
  expect(order.points_used).toBe(previewBody.applied_points)
  expect(order.payment_status).toBe('paid')

  await waitForPointLedgerType(page, authHeaders, 'use')
})

test('Scenario 4: cancel restores reserved points idempotently', async ({ page }) => {
  const user = await resolveTestUser(page)
  const authHeaders = await getUserAuthHeaders(page)
  const card = await findOrCreateSellableCard(page)

  await grantPoints(page, user.id, 15000, 'E2E cancel restore', `e2e-cancel-grant-${Date.now()}`)
  const beforeCancel = await getAdminUserPoints(page, user.id)

  await clearUserCart(page, authHeaders)
  await addCardToCart(page, authHeaders, card.id, 1)

  const unitPrice = Math.round(card.price ?? 1000)
  const pointsToUse = Math.min(800, unitPrice)

  const checkoutRes = await page.request.post('/api/payments/stripe/create-checkout-session', {
    headers: authHeaders,
    data: { ...defaultCheckoutPayload(), points_to_use: pointsToUse },
  })
  expect(checkoutRes.ok(), await checkoutRes.text()).toBeTruthy()
  const checkout = (await checkoutRes.json()) as { order_id: number; session_id: string }
  expect(checkout.session_id).not.toMatch(/^points-only-/)

  const afterOrder = await getAdminUserPoints(page, user.id)
  expect(afterOrder.available_points).toBeLessThan(beforeCancel.available_points)
  expect(afterOrder.reserved_points).toBeGreaterThanOrEqual(
    beforeCancel.reserved_points + pointsToUse,
  )

  await ensureAdminSession(page)
  const cancel1 = await page.request.post(`/api/admin/orders/${checkout.order_id}/cancel`)
  expect(cancel1.ok(), await cancel1.text()).toBeTruthy()

  await expect
    .poll(async () => (await getAdminUserPoints(page, user.id)).reserved_points, {
      timeout: 30_000,
      message: 'reserved points for this order should clear after first cancel',
    })
    .toBe(beforeCancel.reserved_points)
  const afterFirstCancel = await getAdminUserPoints(page, user.id)
  expect(afterFirstCancel.available_points).toBeGreaterThanOrEqual(afterOrder.available_points)

  const adminHistory = await page.request.get(`/api/admin/points/users/${user.id}/history`, { params: { limit: 30 } })
  expect(adminHistory.ok()).toBeTruthy()
  const adminHistoryBody = (await adminHistory.json()) as {
    items: Array<{ type: string; source_id?: number | null; order_id?: number | null }>
  }
  expect(
    adminHistoryBody.items.some((tx) => {
      const linkedOrderId = tx.order_id ?? tx.source_id
      return (tx.type === 'release' || tx.type === 'cancel_restore') && linkedOrderId === checkout.order_id
    }),
  ).toBeTruthy()

  const cancel2 = await page.request.post(`/api/admin/orders/${checkout.order_id}/cancel`)
  expect(cancel2.ok(), await cancel2.text()).toBeTruthy()
  const afterSecondCancel = await getAdminUserPoints(page, user.id)
  expect(afterSecondCancel.available_points).toBe(afterFirstCancel.available_points)

  await waitForMypagePointsReady(page)
  await shot(page, '07-mypage-after-cancel')
})

test('Scenario 5: mypage points history visible', async ({ page }) => {
  await waitForMypagePointsReady(page)
  await expect(page.getByText('付与').first()).toBeVisible({ timeout: 30_000 })
  await shot(page, '08-mypage-history')
})

test('Scenario 6: admin deduct reflects on mypage', async ({ page }) => {
  const user = await resolveTestUser(page)
  const beforeDeduct = (await getAdminUserPoints(page, user.id)).available_points
  const deductAmount = 200

  const deduct = await page.request.post('/api/admin/points/deduct', {
    data: {
      user_id: user.id,
      amount: deductAmount,
      reason: 'E2E deduct',
      idempotency_key: `e2e-deduct-${Date.now()}`,
    },
  })
  expect(deduct.ok(), await deduct.text()).toBeTruthy()

  const afterDeduct = (await getAdminUserPoints(page, user.id)).available_points
  expect(afterDeduct).toBe(beforeDeduct - deductAmount)
  expectedAvailablePoints = afterDeduct

  await waitForMypagePointsReady(page)
  await expect(
    page.locator('p.text-4xl').filter({ hasText: formatMypageBalance(afterDeduct) }),
  ).toBeVisible({ timeout: 30_000 })
  await shot(page, '09-after-deduct')
})

test('Scenario 7: over-balance checkout preview rejected', async ({ page }) => {
  const authHeaders = await getUserAuthHeaders(page)
  const balanceRes = await page.request.get('/api/points/balance', { headers: authHeaders })
  expect(balanceRes.ok(), await balanceRes.text()).toBeTruthy()
  const { available_points } = (await balanceRes.json()) as { available_points: number }

  const extreme = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: { items_subtotal: 1000, shipping_fee: 0, requested_points: 999999 },
  })
  // Backend preview_checkout_points swallows validation errors and returns applied=0 (not HTTP 400).
  expect(extreme.ok(), await extreme.text()).toBeTruthy()
  const extremeBody = (await extreme.json()) as {
    applied_points: number
    max_usable_points: number
    requested_points: number
  }
  expect(extremeBody.applied_points).toBe(0)
  expect(extremeBody.max_usable_points).toBeLessThanOrEqual(available_points)
  expect(extremeBody.max_usable_points).toBeLessThan(999999)

  const overRequest = available_points + 2000
  const capped = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: { items_subtotal: 50000, shipping_fee: 0, requested_points: overRequest },
  })
  expect(capped.ok(), await capped.text()).toBeTruthy()
  const cappedBody = (await capped.json()) as {
    applied_points: number
    max_usable_points: number
  }
  expect(cappedBody.applied_points).toBeLessThanOrEqual(available_points)
  expect(cappedBody.max_usable_points).toBeLessThanOrEqual(available_points)
  if (overRequest > cappedBody.max_usable_points) {
    expect(cappedBody.applied_points).toBe(0)
  }

  await shot(page, '10-over-balance-preview')
})
