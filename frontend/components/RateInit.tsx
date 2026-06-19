'use client'

import { useEffect } from 'react'
import { useRateStore } from '@/store/rate'
import { exchangeApi } from '@/lib/api'

export function RateInit() {
  const { lastUpdated, setRate } = useRateStore()

  useEffect(() => {
    const fetchRate = async () => {
      // 1 hour cache on frontend (1 hour = 3600000 ms)
      const ONE_HOUR = 3600000
      if (Date.now() - lastUpdated < ONE_HOUR) {
        return
      }

      try {
        const response = await exchangeApi.getRate()
        if (response.data && response.data.rate) {
          setRate(response.data.rate)
        }
      } catch (error) {
        console.error('Failed to fetch exchange rate:', error)
      }
    }

    fetchRate()
  }, [lastUpdated, setRate])

  return null
}
