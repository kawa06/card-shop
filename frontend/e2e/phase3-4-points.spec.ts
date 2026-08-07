import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-4-points')
const TEST_EMAIL = 'rikukai0609@icloud.com'

/** Serial flow: grant balance is reused in later scenarios. */
let expectedAvailablePoints: number | null = null

test.describe.configure({ mode: 'serial', timeout: 180_000 })

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

async function getAdminUserAvailablePoints(page: import('@playwright/test').Page, userId: number) {
  await ensureAdminSession(page)
  const res = await page.request.get(`/api/admin/points/users/${userId}`)
  expect(res.ok(), await res.text()).toBeTruthy()
  const body = (await res.json()) as { available_points: number }
  return body.available_points
}

async function getUserAuthHeaders(page: import('@playwright/test').Page) {
  const syncResponse = page.waitForResponse(
    (res) => res.url().includes('/api/auth/backend-sync') && res.ok(),
    { timeout: 60_000 },
  )
  await page.goto('/mypage/points', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: /ポイント/i })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('p.text-4xl')).toBeVisible({ timeout: 30_000 })

  let token = await page.evaluate(() => localStorage.getItem('auth_token'))
  if (!token) {
    const sync = await syncResponse
    const body = (await sync.json()) as { access_token?: string }
    token = body.access_token ?? null
  }
  expect(token, 'backend JWT missing after mypage auth sync').toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

test('Scenario 1: admin grant and mypage balance', async ({ page }) => {
  await page.goto('/admin/points')
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

  expectedAvailablePoints = await getAdminUserAvailablePoints(page, user.id)

  await page.goto('/mypage/points')
  await expect(
    page.locator('p.text-4xl').filter({ hasText: formatMypageBalance(expectedAvailablePoints) }),
  ).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('付与').first()).toBeVisible()
  await shot(page, '02-mypage-balance')
})

test('Scenario 2: partial points checkout preview', async ({ page }) => {
  const authHeaders = await getUserAuthHeaders(page)
  const preview = await page.request.post('/api/points/checkout-preview', {
    headers: authHeaders,
    data: { items_subtotal: 5000, shipping_fee: 500, requested_points: 500 },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const body = (await preview.json()) as {
    applied_points: number
    total_yen: number
    max_usable_points: number
  }
  expect(body.applied_points).toBeGreaterThan(0)
  expect(body.applied_points).toBeLessThanOrEqual(body.max_usable_points)
  expect(body.total_yen).toBeLessThan(5500)
  await shot(page, '03-checkout-preview')
})

test('Scenario 3: mypage points history visible', async ({ page }) => {
  await page.goto('/mypage/points')
  await expect(page.getByRole('heading', { name: /ポイント/i })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('付与').first()).toBeVisible({ timeout: 30_000 })
  await shot(page, '04-mypage-history')
})

test('Scenario 5: admin deduct reflects on mypage', async ({ page }) => {
  const user = await resolveTestUser(page)
  const beforeDeduct =
    expectedAvailablePoints ?? (await getAdminUserAvailablePoints(page, user.id))
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

  const afterDeduct = await getAdminUserAvailablePoints(page, user.id)
  expect(afterDeduct).toBe(beforeDeduct - deductAmount)
  expectedAvailablePoints = afterDeduct

  await page.goto('/mypage/points')
  await expect(
    page.locator('p.text-4xl').filter({ hasText: formatMypageBalance(afterDeduct) }),
  ).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-after-deduct')
})

test('Scenario 6: over-balance checkout preview rejected', async ({ page }) => {
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

  await shot(page, '06-over-balance-preview')
})
