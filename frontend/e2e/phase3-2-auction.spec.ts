import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-2-milestone1')

test.describe.configure({ mode: 'serial' })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(
    page.getByText(/\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u914d\u4fe1\u7ba1\u7406|\u30e9\u30a4\u30d6|\u6ce8\u6587\u7ba1\u7406|\u767a\u9001\u7ba1\u7406/).first(),
  ).toBeVisible({ timeout: 60_000 })
}

test('01 admin auction page setup', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)

  const title = `E2E Auction ${Date.now()}`
  await page.getByPlaceholder('\u65b0\u3057\u3044\u914d\u4fe1\u30bf\u30a4\u30c8\u30eb').fill(title)
  await page.getByRole('button', { name: '\u4f5c\u6210' }).click()
  await page.getByText(title).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible({ timeout: 30_000 })

  await page.getByPlaceholder('\u30ab\u30fc\u30c9ID').fill('1')
  await page.getByRole('button', { name: '\u8ffd\u52a0' }).click()
  await page.waitForTimeout(1000)

  await page.getByRole('link', { name: '\u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406' }).click()
  await expect(page.getByRole('heading', { name: '\u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406' })).toBeVisible({ timeout: 30_000 })
  await shot(page, '01-admin-auction-page')
})

test('02 auction bid flow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)

  const title = `E2E Auction Flow ${Date.now()}`
  await page.getByPlaceholder('\u65b0\u3057\u3044\u914d\u4fe1\u30bf\u30a4\u30c8\u30eb').fill(title)
  await page.getByRole('button', { name: '\u4f5c\u6210' }).click()
  await page.getByText(title).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible({ timeout: 30_000 })

  await page.getByPlaceholder('\u30ab\u30fc\u30c9ID').fill('1')
  await page.getByRole('button', { name: '\u8ffd\u52a0' }).click()
  await page.waitForTimeout(1000)

  await page.getByRole('link', { name: '\u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406' }).click()
  await expect(page.getByRole('heading', { name: '\u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406' })).toBeVisible({ timeout: 30_000 })

  await page.getByRole('button', { name: '\u4f5c\u6210' }).click()
  await page.waitForTimeout(1000)
  await page.getByRole('button', { name: /#\d+/ }).first().click()

  await page.getByRole('button', { name: '\u958b\u59cb' }).click()
  await page.waitForTimeout(1500)
  await shot(page, '02-admin-auction-started')

  const streamMatch = page.url().match(/\/admin\/live\/(\d+)\/auctions/)
  expect(streamMatch).toBeTruthy()
  const streamId = streamMatch![1]

  const publicPage = await page.context().newPage()
  await publicPage.goto(`/live/${streamId}`)
  await expect(publicPage.getByTestId('live-auction-panel')).toBeVisible({ timeout: 30_000 })

  await publicPage.getByTestId('bid-amount-input').fill('1100')
  await publicPage.getByTestId('bid-submit').click()
  await expect(publicPage.getByTestId('live-auction-panel')).toContainText('1,100', { timeout: 30_000 })
  await publicPage.screenshot({ path: path.join(outDir, '03-public-bid-placed.png'), fullPage: true })
  await publicPage.close()

  await page.getByRole('button', { name: '\u7d42\u4e86' }).click()
  await page.waitForTimeout(1000)
  await shot(page, '04-admin-auction-finished')
})
