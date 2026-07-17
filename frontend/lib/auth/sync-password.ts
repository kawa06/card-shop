import 'server-only'

import { createHmac } from 'crypto'

export function createSyncPassword(supabaseUserId: string): string {
  const secret = process.env.AUTH_SYNC_SECRET
  if (!secret) {
    throw new Error('AUTH_SYNC_SECRET が設定されていません')
  }
  return createHmac('sha256', secret).update(supabaseUserId).digest('hex').slice(0, 32)
}
