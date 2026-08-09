import { defineConfig, devices } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const envLocal = path.join(__dirname, '.env.local')
if (fs.existsSync(envLocal)) {
  for (const line of fs.readFileSync(envLocal, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
    const eq = trimmed.indexOf('=')
    const key = trimmed.slice(0, eq).trim()
    const value = trimmed.slice(eq + 1).trim().replace(/^['"]|['"]$/g, '')
    if (key && process.env[key] === undefined) process.env[key] = value
  }
}

const authFile = path.join(__dirname, 'playwright/.clerk/user.json')
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['json', { outputFile: '../artifacts/phase3-2-milestone1/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-3-offers/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-4-points/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-5-coupons/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-6-notifications/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-7-admin-enhancement/playwright-report.json' }],
    ['json', { outputFile: '../artifacts/phase3-8-inventory-restock/playwright-report.json' }],
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  use: {
    baseURL,
    trace: 'on-first-retry',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
  },
  projects: [
    {
      name: 'global setup',
      testMatch: /global\.setup\.ts/,
    },
    {
      name: 'phase2-admin-ui',
      testMatch: /phase2-admin-ui\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-live',
      testMatch: /phase3-live\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-2-auction',
      testMatch: /phase3-2-auction\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },

    {
      name: 'phase3-4-points',
      testMatch: /phase3-4-points\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-4-evidence',
      testMatch: /phase3-4-evidence\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-5-coupons',
      testMatch: /phase3-5-coupons\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-6-notifications',
      testMatch: /phase3-6-notifications\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-7-admin-enhancement',
      testMatch: /phase3-7-admin-enhancement\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-8-inventory-restock',
      testMatch: /phase3-8-inventory-restock\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
    {
      name: 'phase3-3-offers',
      testMatch: /phase3-3-offers\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
  ],
})
