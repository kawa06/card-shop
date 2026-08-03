'use client'

import Link from 'next/link'
import { ShieldOff } from 'lucide-react'

export function BuybackPiiForbidden() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-6">
      <div className="max-w-md text-center space-y-4">
        <ShieldOff className="h-12 w-12 text-gray-400 mx-auto" />
        <h1 className="text-xl font-bold text-gray-900">この機能は利用できません</h1>
        <p className="text-sm text-gray-600 leading-relaxed">
          本人確認書類・口座情報などの重要個人情報は、カードショップ管理サイトからは閲覧・操作できません。
          買取管理サイトの「本人確認審査」「振込管理」から操作してください。
        </p>
        <Link href="/admin" className="inline-block text-sm text-yellow-600 hover:underline">
          管理ダッシュボードへ戻る
        </Link>
      </div>
    </div>
  )
}
