import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-7-admin-enhancement')
const stamp = Date.now()

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function ensureAdmin(page: import('@playwright/test').Page) {
  await page.goto('/admin', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('管理ダッシュボード').first()).toBeVisible({ timeout: 60_000 })
}

test('Scenario 1: analytics dashboard KPI + sales list', async ({ page }) => {
  await ensureAdmin(page)
  await shot(page, '01-admin-home-before')

  await page.goto('/admin/analytics', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('admin-analytics-heading')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('admin-analytics-kpi')).toBeVisible({ timeout: 60_000 })
  await shot(page, '02-analytics-kpi')

  const sales = await page.request.get('/api/admin/analytics/sales', {
    params: { payment_status: 'paid', sort: 'paid_at', order: 'desc', size: 20 },
  })
  expect(sales.ok(), await sales.text()).toBeTruthy()
  const salesBody = (await sales.json()) as { total: number; items: Array<Record<string, unknown>> }
  expect(salesBody.total).toBeGreaterThanOrEqual(0)
  await shot(page, '03-sales-analysis')
})

test('Scenario 2: create coupon then see in coupon analytics', async ({ page }) => {
  await ensureAdmin(page)
  const code = `P37${stamp}`.slice(0, 20)
  const create = await page.request.post('/api/admin/coupons', {
    data: {
      code,
      name: `Phase37 Analytics ${stamp}`,
      coupon_type: 'fixed_amount',
      audience: 'public',
      amount_yen: 300,
      min_subtotal_yen: 0,
      max_uses_per_user: 1,
      is_active: true,
    },
  })
  expect(create.ok(), await create.text()).toBeTruthy()

  await page.goto('/admin/analytics', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('analytics-domain-coupons').click()
  await page.getByTestId('analytics-search').fill(code)
  await page.getByTestId('analytics-status').fill('active')
  await page.getByTestId('analytics-apply-filters').click()
  await expect(page.getByTestId('admin-analytics-table')).toBeVisible()
  await expect(page.getByText(code)).toBeVisible({ timeout: 30_000 })
  await shot(page, '04-coupon-analysis-after-create')

  const listed = await page.request.get('/api/admin/analytics/coupons', {
    params: { q: code, status: 'active' },
  })
  expect(listed.ok()).toBeTruthy()
  const body = (await listed.json()) as { items: Array<{ code: string }> }
  expect(body.items.some((i) => i.code === code)).toBeTruthy()
})

test('Scenario 3: filter/sort sales and export csv/xlsx/pdf', async ({ page }) => {
  await ensureAdmin(page)
  await page.goto('/admin/analytics', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('analytics-domain-sales').click()
  await page.getByTestId('analytics-payment-status').fill('paid')
  await page.getByTestId('analytics-sort').fill('total_amount')
  await page.getByTestId('analytics-order').selectOption('desc')
  await page.getByTestId('analytics-apply-filters').click()
  await expect(page.getByTestId('admin-analytics-total')).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-sales-filtered-sorted')

  for (const format of ['csv', 'xlsx', 'pdf'] as const) {
    const res = await page.request.get('/api/admin/analytics/export', {
      params: { domain: 'sales', format, payment_status: 'paid', sort: 'total_amount', order: 'desc' },
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    const buf = await res.body()
    if (format === 'csv') expect(buf.slice(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))).toBeTruthy()
    if (format === 'xlsx') expect(buf.slice(0, 2).toString('utf8')).toBe('PK')
    if (format === 'pdf') expect(buf.slice(0, 4).toString('utf8')).toBe('%PDF')
    fs.mkdirSync(outDir, { recursive: true })
    fs.writeFileSync(path.join(outDir, `06-export-sales.${format}`), buf)
  }
  await shot(page, '06-export-controls')
})

test('Scenario 4: live / auction / points domains + persistence of export log', async ({ page }) => {
  await ensureAdmin(page)

  for (const domain of ['live', 'auctions', 'points'] as const) {
    const res = await page.request.get(`/api/admin/analytics/${domain}`, {
      params: { sort: 'created_at', order: 'desc', size: 10 },
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    await page.goto('/admin/analytics', { waitUntil: 'domcontentloaded' })
    await page.getByTestId(`analytics-domain-${domain}`).click()
    await expect(page.getByTestId('admin-analytics-table')).toBeVisible({ timeout: 30_000 })
    await shot(page, `07-${domain}-analysis`)
  }

  const kpiExport = await page.request.get('/api/admin/analytics/export', {
    params: { domain: 'kpi', format: 'csv' },
  })
  expect(kpiExport.ok(), await kpiExport.text()).toBeTruthy()
  fs.writeFileSync(path.join(outDir, '08-export-kpi.csv'), await kpiExport.body())
  await shot(page, '08-admin-analytics-success')
})

test('Scenario 5: deactivate coupon reflected after filter refresh', async ({ page }) => {
  await ensureAdmin(page)
  const code = `P37X${stamp}`.slice(0, 20)
  const create = await page.request.post('/api/admin/coupons', {
    data: {
      code,
      name: `Phase37 Toggle ${stamp}`,
      coupon_type: 'percent',
      audience: 'public',
      percent_off: 5,
      min_subtotal_yen: 0,
      max_uses_per_user: 1,
      is_active: true,
    },
  })
  expect(create.ok(), await create.text()).toBeTruthy()
  const created = (await create.json()) as { id: number }

  const before = await page.request.get('/api/admin/analytics/coupons', {
    params: { q: code, status: 'active' },
  })
  expect(before.ok()).toBeTruthy()
  expect(((await before.json()) as { total: number }).total).toBeGreaterThanOrEqual(1)

  const patch = await page.request.patch(`/api/admin/coupons/${created.id}`, {
    data: { is_active: false },
  })
  expect(patch.ok(), await patch.text()).toBeTruthy()

  const afterActive = await page.request.get('/api/admin/analytics/coupons', {
    params: { q: code, status: 'active' },
  })
  expect(afterActive.ok()).toBeTruthy()
  expect(((await afterActive.json()) as { total: number }).total).toBe(0)

  const afterInactive = await page.request.get('/api/admin/analytics/coupons', {
    params: { q: code, status: 'inactive' },
  })
  expect(afterInactive.ok()).toBeTruthy()
  expect(((await afterInactive.json()) as { total: number }).total).toBeGreaterThanOrEqual(1)

  await page.goto('/admin/analytics', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('analytics-domain-coupons').click()
  await page.getByTestId('analytics-search').fill(code)
  await page.getByTestId('analytics-status').fill('inactive')
  await page.getByTestId('analytics-apply-filters').click()
  await expect(page.getByText(code)).toBeVisible({ timeout: 30_000 })
  await shot(page, '09-coupon-inactive-after-update')
})
