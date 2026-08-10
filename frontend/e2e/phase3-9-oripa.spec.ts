import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'
import { execFileSync } from 'child_process'

const outDir = path.join(__dirname, '../../artifacts/phase3-9-oripa')
const backendDir = path.join(__dirname, '../../backend')

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

const FORBIDDEN = [
  'linked_product_id',
  'linked_product_name',
  'linked_inventory_id',
  'prize_tier',
  'SECRET_PRIZE',
]

function assertNoLeak(body: unknown) {
  const raw = JSON.stringify(body)
  for (const key of FORBIDDEN) {
    expect(raw, `leaked ${key}`).not.toContain(key)
  }
  expect(raw).not.toContain('\u5f53\u305f\u308a')
  expect(raw).not.toContain('\u30cf\u30ba\u30ec')
}

function seedOripa(): { oripa_id: number; title: string; secret_name: string } {
  const stdout = execFileSync('python', ['scripts/seed_oripa_e2e.py'], {
    cwd: backendDir,
    encoding: 'utf8',
  })
  const line = stdout.trim().split(/\r?\n/).filter(Boolean).pop() || '{}'
  return JSON.parse(line) as { oripa_id: number; title: string; secret_name: string }
}

async function clerkAuthHeaders(page: import('@playwright/test').Page): Promise<Record<string, string>> {
  await page.goto('/mypage', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)
  const token = await page.evaluate(async () => {
    const w = window as unknown as {
      Clerk?: { session?: { getToken: () => Promise<string | null> } }
    }
    return (await w.Clerk?.session?.getToken?.()) || localStorage.getItem('auth_token')
  })
  expect(token, 'missing clerk/backend auth token').toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

test('Gate3/4: customer oripa secrecy + UI', async ({ page }) => {
  const seed = seedOripa()
  const oripaId = seed.oripa_id
  const headers = await clerkAuthHeaders(page)

  // Admin UI (best-effort screenshot; RBAC may redirect on fresh sqlite)
  await page.goto('/admin/oripas', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  await shot(page, '01-admin-oripa-list')
  await page.goto(`/admin/oripas/${oripaId}`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1500)
  await shot(page, '01b-admin-oripa-detail')

  const pubList = await page.request.get('/api/oripas')
  expect(pubList.ok(), await pubList.text()).toBeTruthy()
  assertNoLeak(await pubList.json())

  const pubDetail = await page.request.get(`/api/oripas/${oripaId}`)
  expect(pubDetail.ok(), await pubDetail.text()).toBeTruthy()
  const detailBody = await pubDetail.json()
  assertNoLeak(detailBody)
  expect(JSON.stringify(detailBody)).not.toContain('SECRET_PRIZE')
  expect(JSON.stringify(detailBody)).not.toContain(seed.secret_name)

  await page.goto('/oripa', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('oripa-list-heading')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText(seed.title)).toBeVisible()
  await shot(page, '02-customer-oripa-list')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/oripa', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('oripa-list-heading')).toBeVisible()
  await shot(page, '02b-customer-oripa-list-mobile')
  await page.setViewportSize({ width: 1280, height: 720 })

  await page.goto(`/oripa/${oripaId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('oripa-detail-heading')).toBeVisible({ timeout: 60_000 })
  await shot(page, '03-customer-oripa-detail')

  const purchase = await page.request.post(`/api/oripas/${oripaId}/purchase`, {
    headers,
    data: { quantity: 2, idempotency_key: `e2e-${Date.now()}` },
  })
  expect(purchase.ok(), await purchase.text()).toBeTruthy()
  const bought = (await purchase.json()) as { entry_labels: string[]; quantity: number }
  assertNoLeak(bought)
  expect(bought.quantity).toBe(2)
  expect(bought.entry_labels).toHaveLength(2)
  for (const label of bought.entry_labels) {
    expect(label).toMatch(/^No\.\d+$/)
  }
  expect(JSON.stringify(bought)).not.toContain('SECRET_PRIZE')
  expect(JSON.stringify(bought)).not.toContain(seed.secret_name)
  fs.writeFileSync(path.join(outDir, 'purchase-result.json'), JSON.stringify(bought, null, 2))

  await page.goto(`/oripa/${oripaId}`, { waitUntil: 'domcontentloaded' })
  await page.getByTestId('oripa-purchase-qty').fill('1')
  await page.getByTestId('oripa-purchase-btn').click()
  const result = page.getByTestId('oripa-purchase-result')
  await expect(result).toBeVisible({ timeout: 60_000 })
  await expect(result.getByText(/決済が確定しました|口購入しました/)).toBeVisible()
  await shot(page, '04-customer-purchase-result')

  const held = await page.request.get('/api/me/oripa-entries', {
    headers,
    params: { shipment_status: 'held' },
  })
  expect(held.ok(), await held.text()).toBeTruthy()
  const heldBody = await held.json()
  assertNoLeak(heldBody)
  expect(JSON.stringify(heldBody)).not.toContain('SECRET_PRIZE')
  expect(JSON.stringify(heldBody)).not.toContain(seed.secret_name)

  await page.goto('/mypage/oripa', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-oripa-heading')).toBeVisible({ timeout: 60_000 })
  await shot(page, '05-mypage-held-oripa')
})
