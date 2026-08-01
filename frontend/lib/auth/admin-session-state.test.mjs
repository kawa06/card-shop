import test from 'node:test'
import assert from 'node:assert/strict'

function classifyAdminSessionFailure(status) {
  if (status === null || status >= 500) return 'transient'
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'forbidden'
  return 'error'
}

test('classifyAdminSessionFailure maps transport failures to transient', () => {
  assert.equal(classifyAdminSessionFailure(null), 'transient')
  assert.equal(classifyAdminSessionFailure(503), 'transient')
  assert.equal(classifyAdminSessionFailure(500), 'transient')
})

test('classifyAdminSessionFailure maps auth failures distinctly', () => {
  assert.equal(classifyAdminSessionFailure(401), 'unauthenticated')
  assert.equal(classifyAdminSessionFailure(403), 'forbidden')
  assert.equal(classifyAdminSessionFailure(404), 'error')
})
