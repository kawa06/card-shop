/** A-one 72265 / ラベル屋さん layout helpers (official face size; derived margins). */

export type BuybackLabelLayout = {
  product_code: string
  format_code: string
  sheet_width_mm: number
  sheet_height_mm: number
  label_width_mm: number
  label_height_mm: number
  columns: number
  rows: number
  faces: number
  gap_h_mm: number
  gap_v_mm: number
  margin_left_mm: number
  margin_top_mm: number
  margin_right_mm: number
  margin_bottom_mm: number
  margins_confirmed: boolean
  margins_note: string
  source_url: string
  shop_name: string
}

export type BuybackLabelSheetCell = {
  package_id: number
  package_code: string
  scan_token?: string | null
  barcode_human_readable?: string | null
  public_buyback_code?: string | null
  request_number?: string | null
  inbound_mgmt_id?: string | null
  box_index?: number | null
  total_boxes?: number | null
  package_kind?: string | null
  package_kind_label?: string | null
  applicant_name?: string | null
  handling_note?: string
  shop_name?: string
  title?: string | null
}

/** Place labels onto a 65-face sheet starting at 1-based position. */
export function placeLabelsOnSheet<T>(
  labels: T[],
  startPosition: number,
  faces: number
): Array<T | null> {
  const start = Math.max(1, Math.min(startPosition || 1, faces))
  const cells: Array<T | null> = Array.from({ length: faces }, () => null)
  let idx = start - 1
  for (const label of labels) {
    if (idx >= faces) break
    cells[idx] = label
    idx += 1
  }
  return cells
}

export function layoutCssVars(layout: BuybackLabelLayout): Record<string, string> {
  return {
    '--sheet-w': `${layout.sheet_width_mm}mm`,
    '--sheet-h': `${layout.sheet_height_mm}mm`,
    '--label-w': `${layout.label_width_mm}mm`,
    '--label-h': `${layout.label_height_mm}mm`,
    '--cols': String(layout.columns),
    '--rows': String(layout.rows),
    '--gap-h': `${layout.gap_h_mm}mm`,
    '--gap-v': `${layout.gap_v_mm}mm`,
    '--margin-l': `${layout.margin_left_mm}mm`,
    '--margin-t': `${layout.margin_top_mm}mm`,
  }
}
