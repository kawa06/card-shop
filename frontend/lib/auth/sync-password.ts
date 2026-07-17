import 'server-only'

import { createHmac } from 'crypto'

export function createSyncPassword(supabaseUserId: string): string {
  const secret = process.env.AUTH_SYNC_SECRET || process.env.CLERK_SECRET_KEY
  if (!secret) {
    throw new Error('AUTH_SYNC_SECRET または CLERK_SECRET_KEY が設定されていません')
  }
  return createHmac('sha256', secret).update(supabaseUserId).digest('hex').slice(0, 32)
}
