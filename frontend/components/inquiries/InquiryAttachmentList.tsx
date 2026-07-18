'use client'

import { InquiryAttachment } from '@/lib/types'
import { Paperclip } from 'lucide-react'

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function InquiryAttachmentList({
  attachments,
  messageId,
}: {
  attachments: InquiryAttachment[]
  messageId?: number
}) {
  const items = messageId
    ? attachments.filter((a) => a.message_id === messageId)
    : attachments

  if (items.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map((att) => (
        <a
          key={att.id}
          href={att.download_url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 bg-white hover:border-yellow-400/50 text-gray-700"
        >
          {att.mime_type.startsWith('image/') && att.download_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={att.download_url}
              alt={att.original_filename}
              className="h-8 w-8 object-cover rounded"
            />
          ) : (
            <Paperclip className="h-3 w-3" />
          )}
          <span className="max-w-[120px] truncate">{att.original_filename}</span>
          <span className="text-gray-400">({formatSize(att.file_size)})</span>
        </a>
      ))}
    </div>
  )
}

export const INQUIRY_ACCEPTED_IMAGE_TYPES = 'image/jpeg,image/png,image/webp,image/gif'

export function validateInquiryFiles(files: File[], maxCount = 5): string | null {
  if (files.length > maxCount) return `添付は最大${maxCount}件までです`
  for (const file of files) {
    if (!file.type.startsWith('image/')) return '画像ファイルのみ選択できます'
    if (file.size > 5 * 1024 * 1024) return '5MB以下の画像を選択してください'
  }
  return null
}
