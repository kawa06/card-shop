import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-4-points')

test.describe.configure({ mode: 'serial', timeout: 180_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

test('Scenario 1: admin grant and mypage balance', async ({ page }) => {
  await page.goto('/mypage', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)
  await page.goto('/admin/points')
  await expect(page.getByRole('heading', { name: 'ポイント管理' })).toBeVisible({ timeout: 60_000 })
  await shot(page, '01-admin-points')

  const usersRes = await page.request.get('/api/admin/users', { params: { q: 'rikukai0609@icloud.com' } })
  expect(usersRes.ok(), await usersRes.text()).toBeTruthy()
  const users = (await usersRes.json()) as Array<{ id: number; email: string }> 
  const user = users.find((u) => u.email.toLowerCase() === 'rikukai0609@icloud.com'.toLowerCase()) ?? users[0]
  expect(user?.id).toBeTruthy()
  const grantKey = `e2e-grant-${Date.now()}`
  const grant = await page.request.post('/api/admin/points/grant', {
    data: { user_id: user.id, amount: 1000, reason: 'E2E grant', idempotency_key: grantKey },
  })
  expect(grant.ok(), await grant.text()).toBeTruthy()

  await page.goto('/mypage/points')
  await expect(page.getByText('1,000')).toBeVisible({ timeout: 30_000 })
  await shot(page, '02-mypage-balance')
})

test('Scenario 5: admin deduct reflects on mypage', async ({ page }) => {
  const usersRes = await page.request.get('/api/admin/users', { params: { q: 'rikukai0609@icloud.com' } })
  expect(usersRes.ok(), await usersRes.text()).toBeTruthy()
  const users = (await usersRes.json()) as Array<{ id: number; email: string }> 
  const user = users.find((u) => u.email.toLowerCase() === 'rikukai0609@icloud.com'.toLowerCase()) ?? users[0]
  expect(user?.id).toBeTruthy()
  const deduct = await page.request.post('/api/admin/points/deduct', {
    data: { user_id: user.id, amount: 200, reason: 'E2E deduct', idempotency_key: `e2e-deduct-${Date.now()}` },
  })
  expect(deduct.ok(), await deduct.text()).toBeTruthy()
  await page.goto('/mypage/points')
  await expect(page.getByText('800')).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-after-deduct')
})

test('Scenario 6: over-balance checkout preview rejected', async ({ page }) => {
  const preview = await page.request.post('/api/points/checkout-preview', {
    data: { items_subtotal: 1000, shipping_fee: 0, requested_points: 999999 },
  })
  expect(preview.ok()).toBeTruthy()
  const body = await preview.json()
  expect(body.applied_points).toBe(0)
})

test('Scenario 2: partial points checkout preview', async ({ page }) => {
  const preview = await page.request.post('/api/points/checkout-preview', {
    data: { items_subtotal: 5000, shipping_fee: 500, requested_points: 500 },
  })
  expect(preview.ok(), await preview.text()).toBeTruthy()
  const body = await preview.json()
  expect(body.applied_points).toBeGreaterThan(0)
  expect(body.total_yen).toBeLessThan(5500)
  await shot(page, '03-checkout-preview')
})

test('Scenario 3: mypage points history visible', async ({ page }) => {
  await page.goto('/mypage/points')
  await expect(page.getByRole('heading', { name: /ポイント/i })).toBeVisible({ timeout: 30_000 })
  await shot(page, '04-mypage-history')
})
