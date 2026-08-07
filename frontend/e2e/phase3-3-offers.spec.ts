import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-3-offers')

test.describe.configure({ mode: 'serial', timeout: 180_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(
    page.getByText(/\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u914d\u4fe1\u7ba1\u7406|\u30e9\u30a4\u30d6|\u5e0c\u671b\u984d|\u6ce8\u6587\u7ba1\u7406|\u767a\u9001\u7ba1\u7406/).first(),
  ).toBeVisible({ timeout: 90_000 })
}

async function setupLiveStream(page: import('@playwright/test').Page) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)
  const title = `E2E Offers ${Date.now()}`
  const createRes = await page.request.post('/api/admin/live/streams', {
    data: { title, visibility: 'public' },
  })
  expect(createRes.status()).toBe(201)
  const stream = (await createRes.json()) as { id: number }
  const streamId = stream.id

  const cardsRes = await page.request.get('/api/cards?limit=50')
  expect(cardsRes.ok()).toBeTruthy()
  const cardsPayload = (await cardsRes.json()) as { items?: Array<{ id: number; stock?: number; is_active?: boolean }> }
  const card =
    cardsPayload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) > 0) ??
    cardsPayload.items?.[0]
  expect(card?.id, 'No sellable card found for E2E').toBeTruthy()

  const productRes = await page.request.post(`/api/admin/live/streams/${streamId}/products`, {
    data: { card_id: card!.id, display_price: 2000 },
  })
  expect(productRes.status(), await productRes.text()).toBe(201)
  const product = (await productRes.json()) as { id: number }

  const startRes = await page.request.post(`/api/admin/live/streams/${streamId}/start`)
  expect(startRes.ok(), await startRes.text()).toBeTruthy()

  const activateRes = await page.request.post(
    `/api/admin/live/streams/${streamId}/products/${product.id}/activate`,
  )
  expect(activateRes.ok(), await activateRes.text()).toBeTruthy()

  return { streamId: String(streamId), title }
}

async function openOffersAdmin(page: import('@playwright/test').Page, streamId: string) {
  await page.goto(`/admin/live/${streamId}/offers`)
  await expect(page.getByRole('heading', { name: '\u5e0c\u671b\u984d\u7ba1\u7406' })).toBeVisible({ timeout: 30_000 })
}

async function ensureOffersOn(page: import('@playwright/test').Page) {
  const toggle = page.getByTestId('offers-enabled-toggle')
  await expect(toggle).toBeVisible({ timeout: 15_000 })
  const label = (await toggle.textContent())?.trim()
  if (label !== 'ON') {
    await toggle.click()
    await expect(toggle).toHaveText('ON', { timeout: 15_000 })
  }
}

async function publicLivePage(page: import('@playwright/test').Page, streamId: string) {
  const publicPage = await page.context().newPage()
  await publicPage.goto('/mypage', { waitUntil: 'domcontentloaded' })
  await publicPage.goto(`/live/${streamId}`)
  await expect(publicPage.getByTestId('live-offers-panel')).toBeVisible({ timeout: 30_000 })
  await expect(publicPage.getByTestId('offer-amount-input')).toBeVisible({ timeout: 30_000 })
  return publicPage
}

async function waitAdminOffer(page: import('@playwright/test').Page, amountLabel: string) {
  await expect(page.getByTestId('admin-offers-list')).toContainText(amountLabel, { timeout: 60_000 })
}

async function submitPublicOffer(
  publicPage: import('@playwright/test').Page,
  adminPage: import('@playwright/test').Page,
  amount: string,
) {
  await publicPage.getByTestId('offer-amount-input').fill(amount)
  await publicPage.getByTestId('offer-submit').click()
  await expect(publicPage.getByTestId('offer-my-status')).toContainText('\u5be9\u67fb\u4e2d', { timeout: 30_000 })
  const amountLabel = `\u00a5${Number(amount).toLocaleString('ja-JP')}`
  await waitAdminOffer(adminPage, amountLabel)
}

test('01 admin enables offers, public submit, admin realtime', async ({ page }) => {
  const { streamId } = await setupLiveStream(page)
  await openOffersAdmin(page, streamId)
  await ensureOffersOn(page)
  await shot(page, '01-admin-offers-enabled')
  const publicPage = await publicLivePage(page, streamId)
  await shot(publicPage, '02-public-offer-input')
  await submitPublicOffer(publicPage, page, '1600')
  await shot(publicPage, '03-public-offer-card')
  await shot(page, '04-admin-offers-list')
  await publicPage.close()
})

test('02 submit hold accept user status', async ({ page }) => {
  const { streamId } = await setupLiveStream(page)
  await openOffersAdmin(page, streamId)
  await ensureOffersOn(page)
  const publicPage = await publicLivePage(page, streamId)
  await submitPublicOffer(publicPage, page, '1700')
  const row = page.getByTestId('admin-offers-list').locator('li').filter({ hasText: '\u00a51,700' }).first()
  const offerIdAttr = await row.getAttribute('data-testid')
  const offerId = offerIdAttr?.replace('admin-offer-', '') ?? ''
  expect(offerId).not.toBe('')
  await page.getByTestId(`offer-hold-${offerId}`).click()
  await expect(publicPage.getByTestId('offer-my-status')).toContainText('\u4fdd\u7559', { timeout: 30_000 })
  await shot(page, '05-admin-held')
  await shot(publicPage, '06-public-held')
  await page.getByTestId(`offer-accept-${offerId}`).click()
  await expect(publicPage.getByTestId('offer-my-status')).toContainText('\u627f\u8a8d', { timeout: 30_000 })
  await shot(page, '07-admin-accepted')
  await shot(publicPage, '08-public-accepted')
  await publicPage.close()
})

test('03 submit reject user sees rejected', async ({ page }) => {
  const { streamId } = await setupLiveStream(page)
  await openOffersAdmin(page, streamId)
  await ensureOffersOn(page)
  const publicPage = await publicLivePage(page, streamId)
  await submitPublicOffer(publicPage, page, '1800')
  const row = page.getByTestId('admin-offers-list').locator('li').filter({ hasText: '\u00a51,800' }).first()
  const offerId = (await row.getAttribute('data-testid'))?.replace('admin-offer-', '') ?? ''
  await page.getByTestId(`offer-reject-${offerId}`).click()
  await expect(publicPage.getByTestId('offer-my-status')).toContainText('\u5374\u4e0b', { timeout: 30_000 })
  await shot(page, '09-admin-rejected')
  await shot(publicPage, '10-public-rejected')
  await publicPage.close()
})

test('04 accept purchase at accepted price', async ({ page }) => {
  const { streamId } = await setupLiveStream(page)
  await openOffersAdmin(page, streamId)
  await ensureOffersOn(page)
  const publicPage = await publicLivePage(page, streamId)
  await submitPublicOffer(publicPage, page, '1900')
  const row = page.getByTestId('admin-offers-list').locator('li').filter({ hasText: '\u00a51,900' }).first()
  const offerId = (await row.getAttribute('data-testid'))?.replace('admin-offer-', '') ?? ''
  await page.getByTestId(`offer-accept-${offerId}`).click()
  await expect(publicPage.getByTestId('offer-purchase')).toBeVisible({ timeout: 30_000 })
  await shot(publicPage, '11-public-purchase-ready')
  await publicPage.setViewportSize({ width: 390, height: 844 })
  await shot(publicPage, '12-mobile-purchase-ready')
  await publicPage.getByTestId('offer-purchase').click()
  await expect(publicPage.getByText(/注文 #\d+/)).toBeVisible({ timeout: 30_000 })
  await shot(publicPage, '13-purchase-complete')
  await publicPage.close()
})
