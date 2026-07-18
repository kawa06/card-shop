'use client'

import { useEffect, useState } from 'react'
import { paymentsApi } from '@/lib/api'
import {
  EMPTY_INVOICE_CONFIG,
  InvoiceConfig,
  mapInvoiceConfigFromApi,
} from '@/lib/invoice/qualified-invoice'

let cachedConfig: InvoiceConfig | null = null
let fetchPromise: Promise<InvoiceConfig> | null = null

async function loadInvoiceConfig(): Promise<InvoiceConfig> {
  if (cachedConfig) return cachedConfig
  if (!fetchPromise) {
    fetchPromise = paymentsApi
      .getStripeConfig()
      .then((res) => {
        cachedConfig = mapInvoiceConfigFromApi(res.data as Record<string, unknown>)
        return cachedConfig
      })
      .catch(() => {
        cachedConfig = EMPTY_INVOICE_CONFIG
        return cachedConfig
      })
  }
  return fetchPromise
}

export function invalidateInvoiceConfigCache() {
  cachedConfig = null
  fetchPromise = null
}

/** @deprecated Use useInvoiceConfig */
export function useShopConfig() {
  return useInvoiceConfig()
}

export function useInvoiceConfig() {
  const [config, setConfig] = useState<InvoiceConfig>(
    cachedConfig ?? EMPTY_INVOICE_CONFIG
  )

  useEffect(() => {
    void loadInvoiceConfig().then(setConfig)
  }, [])

  return config
}
