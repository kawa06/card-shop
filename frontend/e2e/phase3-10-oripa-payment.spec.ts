// Phase 3-10 Playwright: oripa payment reservation + confirm (DEBUG auto-confirm when no Stripe).

import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'
import { execFileSync } from 'child_process'

const outDir = path.join(__dirname, '../../artifacts/phase3-10-oripa-payment')
const backendDir = path.join(__dirname, '../../backend')

test.describe.configure({ mode: 'serial', timeout: 360_000 })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

function seedOripa(): { oripa_id: number; title: string } {
  const stdout = execFileSync('python', ['scripts/seed_oripa_e2e.py'], {
    cwd: backendDir,
    encoding: 'utf8',
  })
  const line = stdout.trim().split(/\r?\n/).filter(Boolean).pop() || '{}'
  return JSON.parse(line) as { oripa_id: number; title: string }
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
  expect(token, 'missing auth token').toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

test('Phase3-10: oripa purchase payment confirm + mobile', async ({ page }) => {
  fs.mkdirSync(outDir, { recursive: true })
  const seed = seedOripa()
  const headers = await clerkAuthHeaders(page)

  // Scenario 1+2: purchase → (DEBUG) confirm → numbers
  const purchase = await page.request.post(`/api/oripas/${seed.oripa_id}/purchase`, {
    headers,
    data: { quantity: 1, idempotency_key: `p310-${Date.now()}` },
  })
  expect(purchase.ok(), await purchase.text()).toBeTruthy()
  const body = (await purchase.json()) as {
    status: string
    entry_labels: string[]
    purchase_id: number
    checkout_url?: string
  }
  expect(['completed', 'pending']).toContain(body.status)
  if (body.status === 'completed') {
    expect(body.entry_labels.length).toBe(1)
  } else {
    expect(body.entry_labels).toEqual([])
    expect(body.checkout_url).toBeTruthy()
  }
  fs.writeFileSync(path.join(outDir, 'purchase-api.json'), JSON.stringify(body, null, 2))

  await page.goto(`/oripa/${seed.oripa_id}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('oripa-detail-heading')).toBeVisible({ timeout: 60_000 })
  await shot(page, '01-oripa-detail-desktop')

  // Scenario 4: mobile
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/oripa/${seed.oripa_id}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('oripa-purchase-form')).toBeVisible()
  await shot(page, '02-oripa-detail-mobile')

  await page.goto('/mypage/oripa', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('mypage-oripa-heading')).toBeVisible({ timeout: 60_000 })
  await shot(page, '03-mypage-oripa-mobile')

  // Scenario 3: orders surface (mixed normal+oripa shipping remains order-scoped)
  await page.goto('/orders', { waitUntil: 'domcontentloaded' })
  await shot(page, '04-orders-mixed-ready')
})
