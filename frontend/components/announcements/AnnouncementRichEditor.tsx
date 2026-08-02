'use client'

import { useEffect, useRef } from 'react'
import {
  Bold,
  Heading2,
  Image as ImageIcon,
  Link as LinkIcon,
  List,
  ListOrdered,
  Minus,
  Palette,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

type AnnouncementRichEditorProps = {
  label: string
  value: string
  onChange: (html: string) => void
  onUploadImage?: (file: File) => Promise<string>
  placeholder?: string
}

export default function AnnouncementRichEditor({
  label,
  value,
  onChange,
  onUploadImage,
  placeholder,
}: AnnouncementRichEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value || ''
    }
  }, [value])

  const sync = () => {
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML)
    }
  }

  const exec = (command: string, valueArg?: string) => {
    editorRef.current?.focus()
    document.execCommand(command, false, valueArg)
    sync()
  }

  const insertLink = () => {
    const url = window.prompt('URL')
    if (url) exec('createLink', url)
  }

  const insertImage = async () => {
    if (!onUploadImage) return
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/jpeg,image/png,image/webp'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      try {
        const url = await onUploadImage(file)
        exec('insertImage', url)
      } catch {
        window.alert('画像のアップロードに失敗しました')
      }
    }
    input.click()
  }

  const setColor = () => {
    const color = window.prompt('文字色 (#000000)')
    if (color) exec('foreColor', color)
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <div className="rounded-lg border border-gray-300 overflow-hidden bg-white">
        <div className="flex flex-wrap gap-1 border-b border-gray-200 bg-gray-50 p-2">
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => exec('bold')}>
            <Bold className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => exec('formatBlock', 'h2')}>
            <Heading2 className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={setColor}>
            <Palette className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => exec('insertUnorderedList')}>
            <List className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => exec('insertOrderedList')}>
            <ListOrdered className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={insertLink}>
            <LinkIcon className="h-4 w-4" />
          </Button>
          {onUploadImage && (
            <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={insertImage}>
              <ImageIcon className="h-4 w-4" />
            </Button>
          )}
          <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => exec('insertHorizontalRule')}>
            <Minus className="h-4 w-4" />
          </Button>
        </div>
        <div
          ref={editorRef}
          className="min-h-[180px] max-h-[420px] overflow-y-auto px-3 py-3 text-sm text-gray-900 focus:outline-none announcement-html"
          contentEditable
          suppressContentEditableWarning
          data-placeholder={placeholder}
          onInput={sync}
          onBlur={sync}
        />
      </div>
    </div>
  )
}
