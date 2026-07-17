export interface ShippingMethodInfo {
  code: string
  nameJa: string
  nameEn: string
  carrier: 'yamato' | 'japan_post'
  feeNote: string
  feeNoteEn: string
  tracking: boolean
  insurance: boolean
  insuranceDetail: string
  insuranceDetailEn: string
  sizeLimit: string
  sizeLimitEn: string
  deliveryDays: string
  deliveryDaysEn: string
  recommended?: boolean
  sourceUrl: string
}

export const SHIPPING_POLICY_INTRO =
  '当ショップでは、商品の性質（トレーディングカード等）に応じて、以下の配送方法をご用意しています。配送料はご注文時に配送先に応じて自動計算されます。高額商品や状態管理が重要な商品については、補償付きの配送方法を強く推奨いたします。'

export const SHIPPING_POLICY_INTRO_EN =
  'We offer the following shipping methods depending on the product. Shipping fees are calculated automatically at checkout based on your destination. For high-value or condition-sensitive items, we strongly recommend insured shipping methods.'

export const SHIPPING_METHODS: ShippingMethodInfo[] = [
  {
    code: 'takkyubin_compact',
    nameJa: '宅急便コンパクト（ヤマト運輸）',
    nameEn: 'Takkyubin Compact (Yamato Transport)',
    carrier: 'yamato',
    feeNote: '地域により600円〜（関東発送基準）',
    feeNoteEn: 'From ¥600 depending on region (Kanto origin)',
    tracking: true,
    insurance: true,
    insuranceDetail: '最大30,000円までの補償あり（当店推奨）',
    insuranceDetailEn: 'Insurance up to ¥30,000 (Recommended)',
    sizeLimit: '25cm × 20cm × 5cm 以内',
    sizeLimitEn: 'Max 25cm × 20cm × 5cm',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    recommended: true,
    sourceUrl: 'https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/',
  },
  {
    code: 'nekopos',
    nameJa: 'ネコポス（ヤマト運輸）',
    nameEn: 'Nekopos (Yamato Transport)',
    carrier: 'yamato',
    feeNote: '全国一律385円',
    feeNoteEn: 'Flat ¥385 nationwide',
    tracking: true,
    insurance: true,
    insuranceDetail: '最大3,000円までの補償あり',
    insuranceDetailEn: 'Insurance up to ¥3,000',
    sizeLimit: '31.2cm × 22.8cm × 3cm 以内・A4厚さまで',
    sizeLimitEn: 'Max 31.2cm × 22.8cm × 3cm, A4 thickness',
    deliveryDays: 'おおむね1〜2日',
    deliveryDaysEn: 'Approx. 1–2 business days',
    sourceUrl: 'https://www.kuronekoyamato.co.jp/ytc/customer/send/services/nekopos/',
  },
  {
    code: 'click_post',
    nameJa: 'クリックポスト（日本郵便）',
    nameEn: 'Click Post (Japan Post)',
    carrier: 'japan_post',
    feeNote: '全国一律185〜200円',
    feeNoteEn: 'Flat ¥185–200 nationwide',
    tracking: true,
    insurance: false,
    insuranceDetail: '補償なし（紛失・破損時の補償対象外）',
    insuranceDetailEn: 'No insurance (loss/damage not covered)',
    sizeLimit: '34cm × 25cm × 3cm 以内・1kgまで',
    sizeLimitEn: 'Max 34cm × 25cm × 3cm, up to 1kg',
    deliveryDays: 'おおむね2〜5日',
    deliveryDaysEn: 'Approx. 2–5 business days',
    sourceUrl: 'https://www.post.japanpost.jp/service/click_post/',
  },
  {
    code: 'letter_pack_light',
    nameJa: 'レターパックライト（日本郵便）',
    nameEn: 'Letter Pack Light (Japan Post)',
    carrier: 'japan_post',
    feeNote: '全国一律430円',
    feeNoteEn: 'Flat ¥430 nationwide',
    tracking: true,
    insurance: false,
    insuranceDetail: '補償なし（追跡のみ）',
    insuranceDetailEn: 'No insurance (tracking only)',
    sizeLimit: '34cm × 24.8cm × 3cm 以内',
    sizeLimitEn: 'Max 34cm × 24.8cm × 3cm',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    sourceUrl: 'https://www.post.japanpost.jp/service/letterpack/',
  },
  {
    code: 'letter_pack_plus',
    nameJa: 'レターパックプラス（日本郵便）',
    nameEn: 'Letter Pack Plus (Japan Post)',
    carrier: 'japan_post',
    feeNote: '全国一律600円',
    feeNoteEn: 'Flat ¥600 nationwide',
    tracking: true,
    insurance: false,
    insuranceDetail: '補償なし（追跡のみ）',
    insuranceDetailEn: 'No insurance (tracking only)',
    sizeLimit: '34cm × 24.8cm 以内・厚さ制限なし',
    sizeLimitEn: 'Max 34cm × 24.8cm, no thickness limit',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    sourceUrl: 'https://www.post.japanpost.jp/service/letterpack/',
  },
  {
    code: 'takkyubin_60',
    nameJa: '宅急便 60サイズ（ヤマト運輸）',
    nameEn: 'Takkyubin Size 60 (Yamato Transport)',
    carrier: 'yamato',
    feeNote: '地域により940円〜',
    feeNoteEn: 'From ¥940 depending on region',
    tracking: true,
    insurance: true,
    insuranceDetail: '基本補償あり（詳細は各社規定に準ずる）',
    insuranceDetailEn: 'Basic insurance included (per carrier terms)',
    sizeLimit: '3辺合計60cm以内・2kgまで',
    sizeLimitEn: 'Total dimensions up to 60cm, up to 2kg',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    sourceUrl: 'https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/',
  },
  {
    code: 'takkyubin_80',
    nameJa: '宅急便 80サイズ（ヤマト運輸）',
    nameEn: 'Takkyubin Size 80 (Yamato Transport)',
    carrier: 'yamato',
    feeNote: '地域により1,230円〜',
    feeNoteEn: 'From ¥1,230 depending on region',
    tracking: true,
    insurance: true,
    insuranceDetail: '基本補償あり（詳細は各社規定に準ずる）',
    insuranceDetailEn: 'Basic insurance included (per carrier terms)',
    sizeLimit: '3辺合計80cm以内・5kgまで',
    sizeLimitEn: 'Total dimensions up to 80cm, up to 5kg',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    sourceUrl: 'https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/',
  },
  {
    code: 'yu_pack_60',
    nameJa: 'ゆうパック 60サイズ（日本郵便）',
    nameEn: 'Yu-Pack Size 60 (Japan Post)',
    carrier: 'japan_post',
    feeNote: '地域により970円〜',
    feeNoteEn: 'From ¥970 depending on region',
    tracking: true,
    insurance: true,
    insuranceDetail: '基本補償あり（詳細は各社規定に準ずる）',
    insuranceDetailEn: 'Basic insurance included (per carrier terms)',
    sizeLimit: '3辺合計60cm以内',
    sizeLimitEn: 'Total dimensions up to 60cm',
    deliveryDays: 'おおむね1〜3日',
    deliveryDaysEn: 'Approx. 1–3 business days',
    sourceUrl: 'https://www.post.japanpost.jp/service/you_pack/',
  },
  {
    code: 'international',
    nameJa: '国際郵便（EMS・国際小包）',
    nameEn: 'International Shipping (EMS / Parcel)',
    carrier: 'japan_post',
    feeNote: '配送先・重量により1,400円〜',
    feeNoteEn: 'From ¥1,400 depending on destination and weight',
    tracking: true,
    insurance: true,
    insuranceDetail: '最大20,000円までの補償（EMS等）',
    insuranceDetailEn: 'Insurance up to ¥20,000 (EMS etc.)',
    sizeLimit: '商品・地域により異なる',
    sizeLimitEn: 'Varies by product and region',
    deliveryDays: 'おおむね3〜14日',
    deliveryDaysEn: 'Approx. 3–14 business days',
    sourceUrl: 'https://www.post.japanpost.jp/int/index.html',
  },
]

export const SHIPPING_COMPENSATION_SECTIONS = [
  {
    title: '補償の考え方',
    titleEn: 'About Insurance Coverage',
    paragraphs: [
      'トレーディングカードは、状態や希少性により商品価値が大きく異なります。補償なしの配送方法を選択された場合、配送中の紛失・破損・水濡れ等について、当店は一切の責任を負いかねます。',
      '高額商品・美品・PSA鑑定品等については、必ず「宅急便コンパクト」等の補償付き配送方法をご選択ください。',
      '各配送会社の補償上限額・免責事項・申請期限等は、各社の最新規定が優先されます。下記リンクより必ずご確認ください。',
    ],
    paragraphsEn: [
      'Trading cards vary greatly in value depending on condition and rarity. If you choose a shipping method without insurance, we cannot be held responsible for loss, damage, or water damage during transit.',
      'For high-value items, mint condition cards, or PSA-graded cards, please always choose insured methods such as Takkyubin Compact.',
      'Insurance limits, exclusions, and claim deadlines are governed by each carrier\'s latest terms. Please review the official links below.',
    ],
  },
  {
    title: '発送までの流れ',
    titleEn: 'Shipping Process',
    paragraphs: [
      'ご入金確認後、通常1〜3営業日以内に発送いたします（在庫状況・注文集中時は除く）。',
      '発送完了後、追跡番号をメール等でお知らせします（追跡対応の配送方法の場合）。',
      '商品により選択可能な配送方法が制限される場合があります。カート画面でご確認ください。',
    ],
    paragraphsEn: [
      'After payment confirmation, we typically ship within 1–3 business days (excluding stock shortages or high order volume).',
      'Once shipped, we will notify you of the tracking number via email (for trackable methods).',
      'Some products may restrict available shipping methods. Please check your cart before checkout.',
    ],
  },
  {
    title: '配送事故時の対応',
    titleEn: 'Handling Shipping Incidents',
    paragraphs: [
      '配送中の事故（紛失・破損等）が発生した場合、補償付き配送方法については各配送会社の規定に基づき補償申請を行ってください。',
      '当店は、配送会社の補償規定の範囲内でサポートいたしますが、各社の規定を超える責任は負いかねます。',
      '補償なし配送方法を選択された場合、配送事故に関する当店での返金・再発送等の対応は原則行っておりません。',
    ],
    paragraphsEn: [
      'If a shipping incident (loss, damage, etc.) occurs, please file a claim with the carrier according to their terms for insured methods.',
      'We will assist within the scope of each carrier\'s insurance policy, but cannot accept liability beyond those terms.',
      'For uninsured shipping methods, we generally cannot offer refunds or reshipments for shipping incidents.',
    ],
  },
]

export const SHIPPING_CARRIER_LINKS = [
  {
    labelJa: 'ヤマト運輸（宅急便コンパクト・ネコポス等）',
    labelEn: 'Yamato Transport (Takkyubin Compact, Nekopos, etc.)',
    url: 'https://www.kuronekoyamato.co.jp/ytc/customer/',
  },
  {
    labelJa: '日本郵便（クリックポスト・レターパック・ゆうパック等）',
    labelEn: 'Japan Post (Click Post, Letter Pack, Yu-Pack, etc.)',
    url: 'https://www.post.japanpost.jp/service/index.html',
  },
  {
    labelJa: '日本郵便 国際郵便（EMS・小包）',
    labelEn: 'Japan Post International (EMS / Parcel)',
    url: 'https://www.post.japanpost.jp/int/index.html',
  },
]

export const SHIPPING_POLICY_REVISED = '2026年7月17日'
