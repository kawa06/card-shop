export interface InvoiceConfig {
  invoiceEnabled: boolean
  invoiceRegistrationNumber: string | null
  invoiceIssuerName: string | null
  defaultTaxRate: number
  qualifiedInvoiceEnabled: boolean
}

export const INVOICE_NUMBER_PATTERN = /^T\d{13}$/

export function normalizeRegistrationNumber(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim()
  if (!value) return null
  return INVOICE_NUMBER_PATTERN.test(value) ? value : null
}

export function canComputeTaxBreakdown(defaultTaxRate: number): boolean {
  return defaultTaxRate === 8 || defaultTaxRate === 10
}

export function isQualifiedInvoiceEnabled(config: InvoiceConfig): boolean {
  const reg = normalizeRegistrationNumber(config.invoiceRegistrationNumber)
  const issuer = (config.invoiceIssuerName ?? '').trim()
  return (
    config.invoiceEnabled === true &&
    reg !== null &&
    Boolean(issuer) &&
    canComputeTaxBreakdown(config.defaultTaxRate)
  )
}

export function mapInvoiceConfigFromApi(data: Record<string, unknown> | null | undefined): InvoiceConfig {
  const reg = normalizeRegistrationNumber(
    typeof data?.invoice_registration_number === 'string'
      ? data.invoice_registration_number
      : null
  )
  const enabled = Boolean(data?.invoice_enabled)
  const issuer =
    typeof data?.invoice_issuer_name === 'string' && data.invoice_issuer_name.trim()
      ? data.invoice_issuer_name.trim()
      : null
  const defaultTaxRate =
    typeof data?.default_tax_rate === 'number' ? data.default_tax_rate : 10

  const base: InvoiceConfig = {
    invoiceEnabled: enabled,
    invoiceRegistrationNumber: reg,
    invoiceIssuerName: issuer,
    defaultTaxRate,
    qualifiedInvoiceEnabled: false,
  }
  return {
    ...base,
    qualifiedInvoiceEnabled: isQualifiedInvoiceEnabled(base),
  }
}

export const EMPTY_INVOICE_CONFIG: InvoiceConfig = {
  invoiceEnabled: false,
  invoiceRegistrationNumber: null,
  invoiceIssuerName: null,
  defaultTaxRate: 10,
  qualifiedInvoiceEnabled: false,
}
