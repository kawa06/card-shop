import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase3-1-milestone1')

test.describe.configure({ mode: 'serial' })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\/sign-in/)
  await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 60_000 })
}

test('01 admin live list', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)
  await expect(page.locator('h1')).toContainText('\u914d\u4fe1')
  await shot(page, '01-admin-live-list')
})

test('02 create start end live flow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/live')
  await waitAdminReady(page)

  const title = `E2E Live ${Date.now()}`
  await page.getByPlaceholder('\u65b0\u3057\u3044\u914d\u4fe1\u30bf\u30a4\u30c8\u30eb').fill(title)
  await page.getByRole('button', { name: '\u4f5c\u6210' }).click()
  await page.getByText(title).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible({ timeout: 30_000 })
  await shot(page, '02-admin-live-detail')

  await page.getByRole('button', { name: '\u958b\u59cb' }).click()
  await page.waitForTimeout(1500)
  await shot(page, '03-admin-live-started')

  const publicPage = await page.context().newPage()
  await publicPage.goto(page.url().replace('/admin/live/', '/live/'))
  await expect(publicPage.getByRole('textbox').first()).toBeVisible({ timeout: 30_000 })
  await publicPage.screenshot({ path: path.join(outDir, '04-public-live-viewer.png'), fullPage: true })
  await publicPage.close()

  await page.getByRole('button', { name: '\u7d42\u4e86' }).click()
  await page.waitForTimeout(1000)
  await shot(page, '05-admin-live-ended')
})
