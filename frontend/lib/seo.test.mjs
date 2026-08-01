import test from 'node:test'
import assert from 'node:assert/strict'

const SHOP_SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://frontend-one-topaz-20.vercel.app').replace(/\/$/, '')

function absoluteUrl(path = '/') {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${SHOP_SITE_URL}${normalized}`
}

function buildOrganizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'KRX TCG',
    url: SHOP_SITE_URL,
  }
}

function buildWebsiteJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'KRX TCG',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${SHOP_SITE_URL}/?q={search_term_string}`,
      },
    },
  }
}

function buildProductJsonLd(card) {
  return {
    '@type': 'Product',
    name: card.name,
    offers: {
      '@type': 'Offer',
      priceCurrency: 'JPY',
      availability:
        card.stock > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
    },
  }
}

test('absoluteUrl builds shop URLs', () => {
  assert.equal(absoluteUrl('/terms'), `${SHOP_SITE_URL}/terms`)
})

test('organization json-ld includes site name', () => {
  const data = buildOrganizationJsonLd()
  assert.equal(data['@type'], 'Organization')
  assert.equal(data.name, 'KRX TCG')
})

test('website json-ld includes search action', () => {
  const data = buildWebsiteJsonLd()
  assert.equal(data.potentialAction['@type'], 'SearchAction')
})

test('product json-ld marks in-stock availability', () => {
  const data = buildProductJsonLd({ name: 'テストカード', stock: 2 })
  assert.equal(data.offers.availability, 'https://schema.org/InStock')
})
