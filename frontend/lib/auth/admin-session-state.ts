export type AdminSessionFailure =
  | 'transient'
  | 'unauthenticated'
  | 'forbidden'
  | 'error'

/**
 * Keeps transport/server failures separate from authorization decisions.
 * Only failures that may recover without an identity change are transient.
 */
export function classifyAdminSessionFailure(
  status: number | null
): AdminSessionFailure {
  if (status === null || status >= 500) return 'transient'
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'forbidden'
  return 'error'
}
