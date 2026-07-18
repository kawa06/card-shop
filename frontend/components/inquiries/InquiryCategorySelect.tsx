'use client'

import { INQUIRY_CATEGORY_PLACEHOLDER } from '@/lib/inquiry-labels'

const selectClassName =
  'mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2.5 text-base text-gray-900 min-h-[44px] appearance-auto cursor-pointer'

type Props = {
  id?: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  error?: string
  includeAllOption?: boolean
  allOptionLabel?: string
  disabled?: boolean
}

export function InquiryCategorySelect({
  id = 'inquiry-category',
  value,
  onChange,
  options,
  placeholder = INQUIRY_CATEGORY_PLACEHOLDER,
  error,
  includeAllOption = false,
  allOptionLabel = 'すべてのカテゴリ',
  disabled = false,
}: Props) {
  return (
    <div>
      <select
        id={id}
        className={`${selectClassName} ${error ? 'border-red-400 ring-1 ring-red-400' : ''}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
      >
        {includeAllOption ? (
          <option value="">{allOptionLabel}</option>
        ) : (
          <option value="" disabled hidden>
            {placeholder}
          </option>
        )}
        {options.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
