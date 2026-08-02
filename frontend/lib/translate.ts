import { apiClient } from './api'

export async function translateJaToEn(texts: string[]): Promise<string[]> {
  if (!texts.length) return []
  const res = await apiClient.post<{ translations: string[] }>('/translate', {
    texts,
    target: 'EN',
  })
  const translations = res.data?.translations || []
  return texts.map((text, index) => translations[index] ?? text)
}
