/** 管理画面（開発者モード）に入れるメールアドレス */
export const ADMIN_EMAIL = 'rikukai0609@icloud.com'

export function isAdminEmail(email: string | null | undefined): boolean {
  if (!email) return false
  return email.toLowerCase() === ADMIN_EMAIL.toLowerCase()
}
