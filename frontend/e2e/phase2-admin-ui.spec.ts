import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase2-manual-verify')

test.describe.configure({ mode: 'serial' })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(
    page.getByText(/\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u7ba1\u7406\u753b\u9762|\u767a\u9001\u7ba1\u7406|\u6ce8\u6587\u7ba1\u7406|\u8cb7\u53d6\u7533\u8acb\u7ba1\u7406/).first(),
  ).toBeVisible({ timeout: 60_000 })
}

test('01 dashboard KPI (desktop)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin')
  await waitAdminReady(page)
  await shot(page, '01-dashboard-kpi')
})

test('01 dashboard KPI (mobile)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin')
  await waitAdminReady(page)
  await shot(page, '01-dashboard-kpi-mobile')
})

test('02 notification bell open', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin')
  await waitAdminReady(page)
  const bell = page.getByRole('button', { name: '\u901a\u77e5' })
  await expect(bell).toBeVisible()
  await bell.click()
  await page.waitForTimeout(1000)
  await shot(page, '02-notification-bell-open')

  const unreadItem = page.locator('button.bg-amber-50').first()
  if ((await unreadItem.count()) > 0) {
    await unreadItem.click()
    await page.waitForTimeout(500)
    await shot(page, '02-notification-mark-read')
  }
})

test('03 fulfillment (desktop + mobile)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  await expect(page.getByText('\u767a\u9001\u7ba1\u7406')).toBeVisible()
  await page.waitForSelector('table tbody tr, p:has-text("\u767a\u9001\u5f85\u3061\u306e\u6ce8\u6587\u306f\u3042\u308a\u307e\u305b\u3093")', { timeout: 60_000 })
  await shot(page, '03-fulfillment')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  await shot(page, '03-fulfillment-mobile')
})

test('04 order scan page', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/orders/scan')
  await waitAdminReady(page)
  await expect(page.getByRole('heading', { name: '\u6ce8\u6587\u30b9\u30ad\u30e3\u30f3' })).toBeVisible()
  await shot(page, '04-order-scan')
})

test('08 buyback list CSV', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/buyback/requests')
  await waitAdminReady(page)
  await shot(page, '08-buyback-list-csv')

  const csvBtn = page.getByRole('button', { name: /CSV/ })
  if ((await csvBtn.count()) > 0) {
    const downloadPromise = page.waitForEvent('download', { timeout: 60_000 })
    await csvBtn.first().click()
    const download = await downloadPromise
    const csvPath = path.join(outDir, 'buyback-export.csv')
    await download.saveAs(csvPath)
    const raw = fs.readFileSync(csvPath)
    expect(raw.slice(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))).toBeTruthy()
    await shot(page, '08-buyback-csv-clicked')
  }
})

test('05 order detail + shipment log, 06 label, 07 scan', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })

  let orderId: string | null = process.env.E2E_ORDER_ID ?? null
  if (!orderId) {
    for (const url of ['/api/admin/orders?payment_status=paid', '/api/admin/orders']) {
      const apiRes = await page.request.get(url)
      if (!apiRes.ok()) continue
      const orders = (await apiRes.json()) as Array<{ id: number }>
      if (orders.length > 0) {
        orderId = String(orders[0].id)
        break
      }
    }
  }

  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  const orderLink = page.locator('a[href*="/admin/orders/"]').first()
  if ((await orderLink.count()) > 0) {
    const href = (await orderLink.getAttribute('href')) ?? ''
    const m = href.match(/\/admin\/orders\/(\d+)/)
    if (m) orderId = m[1]
  }

  if (!orderId) {
    await page.goto('/admin/orders')
    await waitAdminReady(page)
    const link = page.locator('a[href*="/admin/orders/"]').first()
    if ((await link.count()) > 0) {
      const href = (await link.getAttribute('href')) ?? ''
      const m = href.match(/\/admin\/orders\/(\d+)/)
      if (m) orderId = m[1]
    }
  }

  if (!orderId) {
    await page.goto('/admin/orders', { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await waitAdminReady(page)
    await page.waitForTimeout(3000)
    const bodyText = await page.innerText('body')
    const hashMatch = bodyText.match(/#(\d+)/)
    if (hashMatch) orderId = hashMatch[1]
  }

  test.skip(!orderId, 'No order found for detail/label/scan checks')
  const oid = orderId!

  await page.goto(`/admin/orders/${oid}`)
  await waitAdminReady(page)
  await expect(page.getByRole('heading', { name: '\u767a\u9001\u30ed\u30b0' })).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-order-detail-shipment-log')

  await page.goto(`/admin/orders/${oid}/print/shipping-label`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await waitAdminReady(page)
  const barcodeImg = page.locator('img[alt="Order barcode"]').first()
  await expect(barcodeImg).toBeVisible({ timeout: 90_000 })
  await expect
    .poll(async () => barcodeImg.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBeTruthy()
  await shot(page, '06-shipping-label-barcode')

  const barcodeEnsure = await page.request.get(`/api/admin/orders/${oid}/barcode`)
  expect(barcodeEnsure.ok()).toBeTruthy()
  const barcodeMeta = (await barcodeEnsure.json()) as {
    human_readable?: string | null
    order_id: number
  }
  const scanCode = barcodeMeta.human_readable?.trim() || `#${oid}`

  const scanApi = await page.request.post('/api/admin/orders/scan', {
    data: { code: scanCode },
  })
  expect(scanApi.ok()).toBeTruthy()
  const scanJson = (await scanApi.json()) as { order_id: number }
  expect(scanJson.order_id).toBe(Number(oid))
  expect(JSON.stringify(scanJson)).not.toContain('scan_token')

  await page.goto('/admin/orders/scan', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await waitAdminReady(page)
  const input = page.getByPlaceholder('\u30d0\u30fc\u30b3\u30fc\u30c9\u3092\u30b9\u30ad\u30e3\u30f3\u307e\u305f\u306f\u624b\u5165\u529b...')
  await input.fill(scanCode)
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: '\u30b9\u30ad\u30e3\u30f3\u7d50\u679c' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('\u6ce8\u6587\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093')).toHaveCount(0)
  await shot(page, '07-barcode-scan-result')
})
