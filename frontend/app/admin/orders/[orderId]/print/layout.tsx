'use client'

import { useEffect } from 'react'
import '@/styles/print-documents.css'

export default function AdminOrderPrintLayout({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    document.body.classList.add('admin-print-document-page')
    return () => {
      document.body.classList.remove('admin-print-document-page')
    }
  }, [])

  return children
}
