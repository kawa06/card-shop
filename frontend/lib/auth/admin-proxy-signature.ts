import 'server-only'

import { createHmac } from 'node:crypto'

export function getAdminProxySecret(): string | null {
  const secret = (process.env.ADMIN_PROXY_SECRET || '').trim()
  return secret || null
}

export function adminProxyHeaders(email: string): Record<string, string> | null {
  const secret = getAdminProxySecret()
  const normalizedEmail = email.trim().toLowerCase()
  if (!secret || !normalizedEmail) return null

  const timestamp = String(Math.floor(Date.now() / 1000))
  const signature = createHmac('sha256', secret)
    .update(`${timestamp}\n${normalizedEmail}`, 'utf8')
    .digest('hex')

  return {
    'X-Admin-Email': normalizedEmail,
    'X-Admin-Timestamp': timestamp,
    'X-Admin-Signature': signature,
  }
}
