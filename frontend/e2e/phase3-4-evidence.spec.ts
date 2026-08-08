import { test, expect, devices } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-4-points')

test.describe.configure({ mode: 'serial', timeout: 300_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(
    page
      .getByText(
        /\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u914d\u4fe1\u7ba1\u7406|\u30e9\u30a4\u30d6|\u30aa\u30fc\u30af\u30b7\u30e7\u30f3|\u5e0c\u671b\u984d|\u6ce8\u6587\u7ba1\u7406|\u767a\u9001\u7ba1\u7406|\u30dd\u30a4\u30f3\u30c8/,
      )
      .first(),
  ).toBeVisible({ timeout: 90_000 })
}

async function resolveSellableCard(page: import('@playwright/test').Page) {
  const cardsRes = await page.request.get('/api/cards', { params: { per_page: 50, page: 1 } })
  expect(cardsRes.ok(), await cardsRes.text()).toBeTruthy()
  const payload = (await cardsRes.json()) as {
    items?: Array<{ id: number; stock?: number; is_active?: boolean }>
  }
  const card =
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) >= 3) ??
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) > 0)
  expect(card?.id, 'No sellable card').toBeTruthy()
  return card!
}

async function setupLiveWithProduct(page: import('@playwright/test').Page, titlePrefix: string) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live', { waitUntil: 'domcontentloaded' })
  await waitAdminReady(page)

  const card = await resolveSellableCard(page)
  const createRes = await page.request.post('/api/admin/live/streams', {
    data: { title: `${titlePrefix} ${Date.now()}`, visibility: 'public' },
  })
  expect(createRes.status(), await createRes.text()).toBe(201)
  const stream = (await createRes.json()) as { id: number }

  const productRes = await page.request.post(`/api/admin/live/streams/${stream.id}/products`, {
    data: { card_id: card.id, display_price: 2000 },
  })
  expect(productRes.status(), await productRes.text()).toBe(201)
  const product = (await productRes.json()) as { id: number }

  expect((await page.request.post(`/api/admin/live/streams/${stream.id}/start`)).ok()).toBeTruthy()
  expect(
    (
      await page.request.post(
        `/api/admin/live/streams/${stream.id}/products/${product.id}/activate`,
      )
    ).ok(),
  ).toBeTruthy()

  return { streamId: stream.id, productId: product.id, cardId: card.id }
}

async function grantPointsToSelf(page: import('@playwright/test').Page, amount: number) {
  await page.goto('/admin/points', { waitUntil: 'domcontentloaded' })
  await waitAdminReady(page)
  const usersRes = await page.request.get('/api/admin/users', {
    params: { q: 'rikukai0609@icloud.com' },
  })
  expect(usersRes.ok(), await usersRes.text()).toBeTruthy()
  const users = (await usersRes.json()) as Array<{ id: number }>
  expect(users[0]?.id).toBeTruthy()
  const grant = await page.request.post('/api/admin/points/grant', {
    data: {
      user_id: users[0].id,
      amount,
      reason: 'E2E evidence grant',
      idempotency_key: `evidence-grant-${Date.now()}`,
    },
  })
  expect(grant.ok(), await grant.text()).toBeTruthy()
}

test('desktop live offer points evidence', async ({ page }) => {
  await grantPointsToSelf(page, 20000)
  const { streamId } = await setupLiveWithProduct(page, 'E2E Offer Points')

  await page.goto(`/admin/live/${streamId}/offers`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '\u5e0c\u671b\u984d\u7ba1\u7406' })).toBeVisible({ timeout: 30_000 })
  const toggle = page.getByTestId('offers-enabled-toggle')
  if ((await toggle.textContent())?.trim() !== 'ON') {
    await toggle.click()
    await expect(toggle).toHaveText('ON', { timeout: 15_000 })
  }

  const publicPage = await page.context().newPage()
  await publicPage.goto(`/live/${streamId}`, { waitUntil: 'domcontentloaded' })
  await expect(publicPage.getByTestId('offer-amount-input')).toBeVisible({ timeout: 30_000 })
  await publicPage.getByTestId('offer-amount-input').fill('1900')
  await publicPage.getByTestId('offer-submit').click()
  await expect(publicPage.getByTestId('offer-my-status')).toContainText('\u5be9\u67fb\u4e2d', { timeout: 30_000 })

  await page.goto(`/admin/live/${streamId}/offers`, { waitUntil: 'domcontentloaded' })
  const row = page.getByTestId('admin-offers-list').locator('li').filter({ hasText: '¥1,900' }).first()
  const offerId = (await row.getAttribute('data-testid'))?.replace('admin-offer-', '') ?? ''
  expect(offerId).not.toBe('')
  await page.getByTestId(`offer-accept-${offerId}`).click()

  await expect(publicPage.getByTestId('offer-points-panel')).toBeVisible({ timeout: 30_000 })
  await expect(publicPage.getByText(/\u30dd\u30a4\u30f3\u30c8\u6b8b\u9ad8/)).toBeVisible()
  await publicPage.getByTestId('offer-points-to-use-input').fill('500')
  await expect(publicPage.getByText(/\u304a\u652f\u6255\u3044\u4e88\u5b9a/)).toBeVisible({ timeout: 30_000 })
  await expect(publicPage.getByTestId('offer-purchase')).toBeVisible()
  await shot(publicPage, '11-live-offer-points')
  await publicPage.close()
})

test('desktop live auction points evidence', async ({ page }) => {
  await grantPointsToSelf(page, 20000)
  const { streamId, productId } = await setupLiveWithProduct(page, 'E2E Auction Points')

  const auctionRes = await page.request.post(`/api/admin/live/streams/${streamId}/auctions`, {
    data: {
      live_product_id: productId,
      start_price: 1000,
      min_bid_increment: 100,
      buy_now_price: 5000,
      duration_seconds: 120,
    },
  })
  expect(auctionRes.status(), await auctionRes.text()).toBe(201)
  const auction = (await auctionRes.json()) as { id: number }

  expect(
    (await page.request.post(`/api/admin/live/streams/${streamId}/auctions/${auction.id}/start`))
      .ok(),
  ).toBeTruthy()

  // Ensure backend JWT exists for member bid
  await page.goto('/mypage/points', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '\u30dd\u30a4\u30f3\u30c8', exact: true })).toBeVisible({
    timeout: 60_000,
  })
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('auth_token')), {
      timeout: 60_000,
      message: 'backend JWT missing',
    })
    .toBeTruthy()
  const token = await page.evaluate(() => localStorage.getItem('auth_token'))

  const bidRes = await page.request.post(`/api/live/auctions/${auction.id}/bids`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { amount: 1100 },
  })
  expect(bidRes.ok(), await bidRes.text()).toBeTruthy()

  expect(
    (await page.request.post(`/api/admin/live/streams/${streamId}/auctions/${auction.id}/finish`))
      .ok(),
  ).toBeTruthy()

  const publicPage = await page.context().newPage()
  await publicPage.goto(`/live/${streamId}`, { waitUntil: 'domcontentloaded' })
  await expect(publicPage.getByTestId('auction-points-panel')).toBeVisible({ timeout: 60_000 })
  await expect(publicPage.getByText(/\u30dd\u30a4\u30f3\u30c8\u6b8b\u9ad8/)).toBeVisible()
  await publicPage.getByTestId('auction-points-to-use-input').fill('400')
  await expect(publicPage.getByText(/\u304a\u652f\u6255\u3044\u4e88\u5b9a/)).toBeVisible({
    timeout: 30_000,
  })
  await expect(publicPage.getByTestId('auction-purchase')).toBeVisible()
  await shot(publicPage, '12-live-auction-points')
  await publicPage.close()
})

test('mobile mypage and checkout evidence', async ({ page }) => {
  test.setTimeout(300_000)
  await page.setViewportSize(devices['iPhone 12'].viewport!)
  await grantPointsToSelf(page, 5000)

  await page.goto('/mypage/points', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: '\u30dd\u30a4\u30f3\u30c8', exact: true })).toBeVisible({
    timeout: 60_000,
  })
  await expect(page.locator('p.text-4xl')).toBeVisible({ timeout: 90_000 })
  await shot(page, '13-mobile-mypage-points')
  await expect(page.getByRole('heading', { name: '\u30dd\u30a4\u30f3\u30c8\u5c65\u6b74' })).toBeVisible()
  await shot(page, '14-mobile-point-history')

  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(token).toBeTruthy()
  const cardsRes = await page.request.get('/api/cards', { params: { per_page: 10, page: 1 } })
  const cards = (await cardsRes.json()) as { items?: Array<{ id: number; stock?: number }> }
  const cardId = cards.items?.find((c) => (c.stock ?? 0) > 0)?.id ?? cards.items?.[0]?.id
  expect(cardId).toBeTruthy()
  await page.request.post('/api/cart', {
    headers: { Authorization: `Bearer ${token}` },
    data: { card_id: cardId, quantity: 1 },
  })
  await page.goto('/cart', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /\u8cfc\u5165\u624b\u7d9a\u304d\u3078|Proceed to checkout/i }).click()
  await expect(page.getByRole('heading', { name: /\u6ce8\u6587\u78ba\u8a8d|Checkout/i })).toBeVisible({
    timeout: 60_000,
  })
  await page.locator('#points').fill('300')
  await expect(page.getByText(/\u304a\u652f\u6255\u3044|\u652f\u6255\u3044|pt/i).first()).toBeVisible({ timeout: 30_000 })
  await shot(page, '15-mobile-checkout-partial')
  await page.locator('#points').fill('50000')
  await shot(page, '16-mobile-checkout-zero')
})

test('mobile live offer points evidence', async ({ page }) => {
  test.setTimeout(300_000)
  await grantPointsToSelf(page, 5000)
  const { streamId } = await setupLiveWithProduct(page, 'E2E Mobile Offer')

  await page.goto(`/admin/live/${streamId}/offers`, { waitUntil: 'domcontentloaded' })
  await waitAdminReady(page)
  const toggle = page.getByTestId('offers-enabled-toggle')
  if ((await toggle.textContent())?.trim() !== 'ON') {
    await toggle.click()
    await expect(toggle).toHaveText('ON', { timeout: 15_000 })
  }

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/live/${streamId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('offer-amount-input')).toBeVisible({ timeout: 30_000 })
  await page.getByTestId('offer-amount-input').fill('1500')
  await page.getByTestId('offer-submit').click()
  await expect(page.getByTestId('offer-my-status')).toContainText('\u5be9\u67fb\u4e2d', { timeout: 30_000 })

  const offersRes = await page.request.get(`/api/admin/live/streams/${streamId}/offers`)
  expect(offersRes.ok(), await offersRes.text()).toBeTruthy()
  const offersPayload = await offersRes.json()
  const offers = (Array.isArray(offersPayload) ? offersPayload : offersPayload.items ?? []) as Array<{
    id: number
    status: string
    amount: number
  }>
  const pending =
    offers.find((o) => o.status === 'pending' && o.amount === 1500) ??
    offers.find((o) => o.status === 'pending')
  expect(pending?.id).toBeTruthy()
  const acceptRes = await page.request.post(
    `/api/admin/live/streams/${streamId}/offers/${pending!.id}/accept`,
  )
  expect(acceptRes.ok(), await acceptRes.text()).toBeTruthy()

  await page.goto(`/live/${streamId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('offer-points-panel')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('offer-points-to-use-input').fill('200')
  await expect(page.getByText(/\u304a\u652f\u6255\u3044\u4e88\u5b9a/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('offer-purchase')).toBeVisible()
  await shot(page, '17-mobile-live-offer')
})

test('mobile live auction points evidence', async ({ page }) => {
  test.setTimeout(300_000)
  await grantPointsToSelf(page, 5000)
  const { streamId, productId } = await setupLiveWithProduct(page, 'E2E Mobile Auction')

  const auctionCreate = await page.request.post(`/api/admin/live/streams/${streamId}/auctions`, {
    data: {
      live_product_id: productId,
      start_price: 1000,
      min_bid_increment: 100,
      buy_now_price: 5000,
      duration_seconds: 120,
    },
  })
  expect(auctionCreate.status(), await auctionCreate.text()).toBe(201)
  const auctionId = ((await auctionCreate.json()) as { id: number }).id
  expect(
    (await page.request.post(`/api/admin/live/streams/${streamId}/auctions/${auctionId}/start`)).ok(),
  ).toBeTruthy()

  await page.goto('/mypage/points', { waitUntil: 'domcontentloaded' })
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('auth_token')), { timeout: 60_000 })
    .toBeTruthy()
  const memberToken = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(memberToken).toBeTruthy()

  const bidRes = await page.request.post(`/api/live/auctions/${auctionId}/bids`, {
    headers: { Authorization: `Bearer ${memberToken}` },
    data: { amount: 1100 },
  })
  expect(bidRes.ok(), await bidRes.text()).toBeTruthy()
  expect(
    (await page.request.post(`/api/admin/live/streams/${streamId}/auctions/${auctionId}/finish`)).ok(),
  ).toBeTruthy()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/live/${streamId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('auction-points-panel')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('auction-points-to-use-input').fill('300')
  await expect(page.getByText(/\u304a\u652f\u6255\u3044\u4e88\u5b9a/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('auction-purchase')).toBeVisible()
  await shot(page, '18-mobile-live-auction')
})
