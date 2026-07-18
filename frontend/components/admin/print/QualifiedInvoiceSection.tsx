import { AdminOrderDetail } from '@/lib/types'
import { InvoiceConfig, isQualifiedInvoiceEnabled } from '@/lib/invoice/qualified-invoice'
import { buildOrderTaxBreakdown } from '@/lib/invoice/tax-breakdown'
import { formatDocumentDate, formatYen } from '@/lib/admin/order-documents'

interface QualifiedInvoiceSectionProps {
  order: AdminOrderDetail
  config: InvoiceConfig
}

export function QualifiedInvoiceSection({ order, config }: QualifiedInvoiceSectionProps) {
  if (!isQualifiedInvoiceEnabled(config)) return null

  const reg = config.invoiceRegistrationNumber!
  const issuer = config.invoiceIssuerName!
  const rows = buildOrderTaxBreakdown(order, config.defaultTaxRate)
  const transactionDate = order.paid_at || order.created_at

  return (
    <section className="print-doc-qualified-invoice">
      <h2 className="print-doc-section-title">適格請求書発行事業者</h2>
      <div className="print-doc-info-grid">
        <div className="print-doc-info-row">
          <span className="print-doc-info-label">事業者名</span>
          <span className="print-doc-info-value">{issuer}</span>
        </div>
        <div className="print-doc-info-row">
          <span className="print-doc-info-label">登録番号</span>
          <span className="print-doc-info-value mono">{reg}</span>
        </div>
        <div className="print-doc-info-row">
          <span className="print-doc-info-label">取引年月日</span>
          <span className="print-doc-info-value">{formatDocumentDate(transactionDate)}</span>
        </div>
      </div>

      <table className="print-doc-table print-doc-tax-table">
        <thead>
          <tr>
            <th>税率</th>
            <th className="num">税込金額</th>
            <th className="num">消費税額</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ratePercent}>
              <td>{row.ratePercent}%</td>
              <td className="num">{formatYen(row.amountInclusive)}</td>
              <td className="num">{formatYen(row.consumptionTax)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
