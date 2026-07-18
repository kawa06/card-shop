'use client'

import { useEffect, useState } from 'react'
import { paymentsApi } from '@/lib/api'

export interface ShopConfig {
  invoiceRegistrationNumber: string | null
}

let cachedConfig: ShopConfig | null = null
let fetchPromise: Promise<ShopConfig> | null = null

async function loadShopConfig(): Promise<ShopConfig> {
  if (cachedConfig) return cachedConfig
  if (!fetchPromise) {
    fetchPromise = paymentsApi
      .getStripeConfig()
      .then((res) => {
        const inv = res.data?.invoice_registration_number
        cachedConfig = {
          invoiceRegistrationNumber: inv && String(inv).trim() ? String(inv).trim() : null,
        }
        return cachedConfig
      })
      .catch(() => {
        cachedConfig = { invoiceRegistrationNumber: null }
        return cachedConfig
      })
  }
  return fetchPromise
}

export function useShopConfig() {
  const [config, setConfig] = useState<ShopConfig>({
    invoiceRegistrationNumber: cachedConfig?.invoiceRegistrationNumber ?? null,
  })

  useEffect(() => {
    void loadShopConfig().then(setConfig)
  }, [])

  return config
}
