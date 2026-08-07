import { clerk, clerkSetup, setupClerkTestingToken } from '@clerk/testing/playwright'
import { test as setup, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

setup.describe.configure({ mode: 'serial' })

const authFile = path.join(__dirname, '../playwright/.clerk/user.json')
const adminEmail =
  process.env.E2E_CLERK_USER_EMAIL ??
  process.env.PHASE1_ADMIN_EMAIL ??
  'rikukai0609@icloud.com'

setup('configure Clerk testing', async () => {
  await clerkSetup()
})

setup('authenticate admin and save storageState', async ({ page }) => {
  fs.mkdirSync(path.dirname(authFile), { recursive: true })
  if (fs.existsSync(authFile) && process.env.E2E_FORCE_REAUTH !== '1') {
    try {
      const state = JSON.parse(fs.readFileSync(authFile, 'utf8')) as { cookies?: unknown[] }
      if ((state.cookies?.length ?? 0) > 0) return
    } catch {
      // fall through to fresh sign-in
    }
  }

  await setupClerkTestingToken({ page })

  await page.goto('/sign-in', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await clerk.signIn({
    page,
    emailAddress: adminEmail,
  })

  await page.goto('/auth/after-sign-in', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForURL(/\/admin/, { timeout: 120_000 })

  await expect(
    page.getByText(/\u7ba1\u7406\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9|\u7ba1\u7406\u753b\u9762|\u767a\u9001\u7ba1\u7406|\u6ce8\u6587\u7ba1\u7406/).first(),
  ).toBeVisible({
    timeout: 120_000,
  })

  await page.context().storageState({ path: authFile })
})
