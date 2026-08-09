import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-6-notifications')
const TEST_EMAIL = 'rikukai0609@icloud.com'

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function ensureAdminSession(page: import('@playwright/test').Page) {
  if (!page.url().includes('/admin')) {
    await page.goto('/admin', { waitUntil: 'domcontentloaded' })
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

async function waitForAuth(page: import('@playwright/test').Page) {
  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-notifications-heading')).toBeVisible({ timeout: 60_000 })
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem('auth_token')), { timeout: 60_000 })
    .toBeTruthy()
}

async function authHeaders(page: import('@playwright/test').Page) {
  await waitForAuth(page)
  const token = await page.evaluate(() => localStorage.getItem('auth_token'))
  expect(token).toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

test('Scenario 1: notification list + badge', async ({ page }) => {
  const user = await resolveTestUser(page)
  await ensureAdminSession(page)
  const stamp = Date.now()
  const broadcast = await page.request.post('/api/admin/user-notifications/broadcast', {
    data: {
      title: `E2E Notice ${stamp}`,
      body: 'Phase 3-6 notification list smoke',
      user_id: user.id,
      action_url: '/mypage/notifications',
    },
  })
  expect(broadcast.ok(), await broadcast.text()).toBeTruthy()

  const headers = await authHeaders(page)
  const unread = await page.request.get('/api/notifications/unread-count', { headers })
  expect(unread.ok()).toBeTruthy()
  expect(((await unread.json()) as { unread_count: number }).unread_count).toBeGreaterThan(0)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('header-notification-bell')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('header-notification-badge')).toBeVisible({ timeout: 30_000 })
  await shot(page, '01-notification-badge')

  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-notifications-heading')).toBeVisible()
  await expect(page.getByText(`E2E Notice ${stamp}`)).toBeVisible({ timeout: 30_000 })
  await shot(page, '02-notification-list')
  await shot(page, '03-unread-notification')
})

test('Scenario 2: mark one read', async ({ page }) => {
  const headers = await authHeaders(page)
  const list = await page.request.get('/api/notifications', { headers, params: { unread_only: true, limit: 5 } })
  expect(list.ok()).toBeTruthy()
  const body = (await list.json()) as { items: Array<{ id: number }>; unread_count: number }
  expect(body.items.length).toBeGreaterThan(0)
  const before = body.unread_count
  const id = body.items[0].id

  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await page.getByTestId(`notification-item-${id}`).click()
  await expect
    .poll(async () => {
      const res = await page.request.get('/api/notifications/unread-count', { headers })
      return ((await res.json()) as { unread_count: number }).unread_count
    })
    .toBeLessThan(before)

  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId(`notification-item-${id}`)).toHaveAttribute('data-read', 'true')
  await shot(page, '04-read-notification')
})

test('Scenario 3: mark all read', async ({ page }) => {
  const user = await resolveTestUser(page)
  await ensureAdminSession(page)
  for (let i = 0; i < 2; i++) {
    await page.request.post('/api/admin/user-notifications/broadcast', {
      data: { title: `E2E Bulk ${Date.now()}-${i}`, body: 'bulk', user_id: user.id },
    })
  }
  const headers = await authHeaders(page)
  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('notifications-mark-all-read').click()
  await expect
    .poll(async () => {
      const res = await page.request.get('/api/notifications/unread-count', { headers })
      return ((await res.json()) as { unread_count: number }).unread_count
    })
    .toBe(0)
  await shot(page, '05-mark-all-read')
})

test('Scenario 4: coupon assignment event notification', async ({ page }) => {
  const user = await resolveTestUser(page)
  await ensureAdminSession(page)
  const stamp = Date.now()
  const created = await page.request.post('/api/admin/coupons', {
    data: {
      code: `NTF${stamp}`,
      name: 'Notif Coupon',
      coupon_type: 'fixed_amount',
      amount_yen: 100,
      audience: 'assigned',
    },
  })
  expect(created.ok() || created.status() === 201, await created.text()).toBeTruthy()
  const coupon = (await created.json()) as { id: number; code: string }
  const assign = await page.request.post(`/api/admin/coupons/${coupon.id}/assign`, {
    data: { user_id: user.id },
  })
  expect(assign.ok(), await assign.text()).toBeTruthy()

  const headers = await authHeaders(page)
  await expect
    .poll(async () => {
      const res = await page.request.get('/api/notifications', { headers, params: { limit: 20 } })
      const items = ((await res.json()) as { items: Array<{ type: string; title: string }> }).items
      return items.some((i) => i.type === 'coupon_assigned')
    })
    .toBe(true)

  await page.goto('/mypage/notifications', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('\u30af\u30fc\u30dd\u30f3\u304c\u914d\u5e03\u3055\u308c\u307e\u3057\u305f').first()).toBeVisible({
    timeout: 30_000,
  })
  await shot(page, '06-event-notification')
})

test('Scenario 5: settings disable campaign in-app', async ({ page }) => {
  const headers = await authHeaders(page)
  const patch = await page.request.patch('/api/notifications/settings', {
    headers,
    data: { campaign_in_app: false },
  })
  expect(patch.ok(), await patch.text()).toBeTruthy()

  const user = await resolveTestUser(page)
  await ensureAdminSession(page)
  const stamp = Date.now()
  const before = await page.request.get('/api/notifications/unread-count', { headers })
  const beforeCount = ((await before.json()) as { unread_count: number }).unread_count
  await page.request.post('/api/admin/user-notifications/broadcast', {
    data: {
      title: `Muted ${stamp}`,
      body: 'should not create when campaign_in_app false',
      user_id: user.id,
      category: 'campaign',
    },
  })
  const after = await page.request.get('/api/notifications/unread-count', { headers })
  expect(((await after.json()) as { unread_count: number }).unread_count).toBe(beforeCount)

  await page.request.patch('/api/notifications/settings', {
    headers,
    data: { campaign_in_app: true },
  })

  await page.goto('/mypage/notification-settings', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('notification-settings-heading')).toBeVisible({ timeout: 60_000 })
  await page.setViewportSize({ width: 390, height: 844 })
  await shot(page, '07-mobile-view')
})
