import { isAxiosError } from 'axios'

export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first === 'object' && first && 'msg' in first) {
        return String((first as { msg: string }).msg)
      }
    }
    if (err.response?.status === 401) {
      return '認証が必要です。ページを再読み込みして再度お試しください。'
    }
    if (err.response?.status === 403) {
      return '管理者権限が必要です。'
    }
  }
  if (err instanceof Error && err.message.trim()) return err.message
  return fallback
}
