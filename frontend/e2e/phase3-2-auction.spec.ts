import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-2-milestone1')

test.describe.configure({ mode: 'serial', timeout: 180_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(
    page.getByText(/\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u914d\u4fe1\u7ba1\u7406|\u30e9\u30a4\u30d6|\u30aa\u30fc\u30af\u30b7\u30e7\u30f3|\u6ce8\u6587\u7ba1\u7406|\u767a\u9001\u7ba1\u7406/).first(),
  ).toBeVisible({ timeout: 90_000 })
}

async function findOrCreateAuctionCard(page: import('@playwright/test').Page) {
  const cardsRes = await page.request.get('/api/cards', { params: { per_page: 50, page: 1 } })
  expect(cardsRes.ok(), await cardsRes.text()).toBeTruthy()
  const payload = (await cardsRes.json()) as {
    items?: Array<{ id: number; stock?: number; is_active?: boolean }>
  }
  let card =
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) >= 3) ??
    payload.items?.find((c) => c.is_active !== false && (c.stock ?? 0) > 0)

  if (!card?.id) {
    const createRes = await page.request.post('/api/admin/cards', {
      data: {
        name: `E2E Auction Card ${Date.now()}`,
        price: 2000,
        stock: 20,
        condition: 'a',
        is_active: true,
        allowed_shipping_methods: JSON.stringify(['takkyubin_compact']),
      },
    })
    expect(createRes.ok(), await createRes.text()).toBeTruthy()
    card = (await createRes.json()) as { id: number }
  }

  expect(card?.id, 'No sellable card for auction E2E').toBeTruthy()
  return card!
}

async function setupLiveStreamWithProduct(page: import('@playwright/test').Page) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)

  const card = await findOrCreateAuctionCard(page)
  const title = `E2E Auction ${Date.now()}`
  const createRes = await page.request.post('/api/admin/live/streams', {
    data: { title, visibility: 'public' },
  })
  expect(createRes.status(), await createRes.text()).toBe(201)
  const stream = (await createRes.json()) as { id: number; title: string }

  const productRes = await page.request.post(`/api/admin/live/streams/${stream.id}/products`, {
    data: { card_id: card.id, display_price: 2000 },
  })
  expect(productRes.status(), await productRes.text()).toBe(201)
  const product = (await productRes.json()) as { id: number; card_id: number }

  const startRes = await page.request.post(`/api/admin/live/streams/${stream.id}/start`)
  expect(startRes.ok(), await startRes.text()).toBeTruthy()

  const activateRes = await page.request.post(
    `/api/admin/live/streams/${stream.id}/products/${product.id}/activate`,
  )
  expect(activateRes.ok(), await activateRes.text()).toBeTruthy()

  return { streamId: stream.id, title: stream.title, cardId: card.id, productId: product.id }
}

async function createAuctionViaUi(page: import('@playwright/test').Page, streamId: number) {
  await page.goto(`/admin/live/${streamId}/auctions`)
  await expect(page.getByRole('heading', { name: '\u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406' })).toBeVisible({
    timeout: 30_000,
  })

  const section = page.locator('section').filter({ hasText: '\u65b0\u898f\u30aa\u30fc\u30af\u30b7\u30e7\u30f3' })
  const select = section.locator('select')
  await expect(select).toBeVisible({ timeout: 30_000 })
  await expect.poll(async () => select.inputValue(), { timeout: 30_000 }).not.toBe('')

  const createResponse = page.waitForResponse(
    (resp) =>
      resp.request().method() === 'POST' &&
      resp.url().includes(`/api/admin/live/streams/${streamId}/auctions`) &&
      resp.status() !== 0,
  )
  await section.getByRole('button', { name: '\u4f5c\u6210' }).click()
  const response = await createResponse
  expect(response.status(), await response.text()).toBe(201)
  const auction = (await response.json()) as { id: number; start_price: number; status: string }
  expect(auction.id).toBeGreaterThan(0)

  await expect(page.getByRole('button', { name: new RegExp(`#${auction.id}`) })).toBeVisible({ timeout: 30_000 })
  return auction
}

test('01 admin auction page setup', async ({ page }) => {
  const { streamId, title } = await setupLiveStreamWithProduct(page)

  await page.goto(`/admin/live/${streamId}`)
  await expect(page.getByRole('heading', { name: title })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('section ul li').first()).toBeVisible({ timeout: 15_000 })

  const auction = await createAuctionViaUi(page, streamId)
  const listRes = await page.request.get(`/api/admin/live/streams/${streamId}/auctions`)
  expect(listRes.ok(), await listRes.text()).toBeTruthy()
  const listPayload = (await listRes.json()) as { items: Array<{ id: number }> }
  expect(listPayload.items.some((a) => a.id === auction.id)).toBeTruthy()
  await shot(page, '01-admin-auction-page')
})

test('02 auction bid flow', async ({ page }) => {
  const { streamId } = await setupLiveStreamWithProduct(page)
  const auction = await createAuctionViaUi(page, streamId)

  await page.getByRole('button', { name: new RegExp(`#${auction.id}`) }).click()
  await page.getByRole('button', { name: '\u958b\u59cb' }).click()
  await expect(page.locator('.rounded-full').filter({ hasText: 'running' })).toBeVisible({ timeout: 15_000 })
  await shot(page, '02-admin-auction-started')

  const publicPage = await page.context().newPage()
  await publicPage.goto('/mypage', { waitUntil: 'domcontentloaded' })
  await publicPage.goto(`/live/${streamId}`)
  await expect(publicPage.getByTestId('live-auction-panel')).toBeVisible({ timeout: 30_000 })

  await publicPage.getByTestId('bid-amount-input').fill('1100')
  await publicPage.getByTestId('bid-submit').click()
  await expect(publicPage.getByTestId('live-auction-panel')).toContainText('\u00a51,100', { timeout: 30_000 })
  await expect(publicPage.getByTestId('live-auction-panel').getByText('\u5165\u672d\u306f\u3042\u308a\u307e\u305b\u3093')).toHaveCount(0)
  await publicPage.screenshot({ path: path.join(outDir, '03-public-bid-placed.png'), fullPage: true })
  await publicPage.close()

  const detailRes = await page.request.get(`/api/admin/live/streams/${streamId}/auctions/${auction.id}`)
  expect(detailRes.ok(), await detailRes.text()).toBeTruthy()
  const detail = (await detailRes.json()) as { current_price: number; bid_count: number }
  expect(detail.current_price).toBe(1100)
  expect(detail.bid_count).toBe(1)

  await page.reload()
  await page.getByRole('button', { name: new RegExp(`#${auction.id}`) }).click()
  await expect(page.getByText(/\u5165\u672d 1\u4ef6/)).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('dd').filter({ hasText: '\u00a51,100' })).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: '\u7d42\u4e86' }).click()
  await page.waitForTimeout(1000)
  await shot(page, '04-admin-auction-finished')
})
