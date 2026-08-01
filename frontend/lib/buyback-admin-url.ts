/** Production buyback admin hub (card-vault-admin). */
export const BUYBACK_ADMIN_BASE_URL = 'https://card-vault-admin-seven.vercel.app/edit.html'

export function buybackAdminUrl(tab?: string): string {
  if (!tab || tab === 'catalog') return BUYBACK_ADMIN_BASE_URL
  return `${BUYBACK_ADMIN_BASE_URL}#${tab}`
}
