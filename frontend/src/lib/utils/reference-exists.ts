import { apiClient } from '@/lib/api/client'
import type { ModalType } from '@/lib/hooks/use-modal-manager'

const REF_ENDPOINTS: Record<ModalType, string> = {
  source: '/sources/',
  note: '/notes/',
  insight: '/insights/',
}

/**
 * Verify a referenced document ID exists before opening its modal.
 *
 * LLMs occasionally truncate record IDs in citations, and the backend repair
 * can only fix unambiguous cases. When a broken ID slips through, surface a
 * clear toast instead of opening a modal that just shows "not found".
 */
export async function referenceExists(
  type: ModalType,
  id: string
): Promise<boolean> {
  const fullId = id.includes(':') ? id : `${type}:${id}`
  try {
    await apiClient.get(`${REF_ENDPOINTS[type]}${encodeURIComponent(fullId)}`)
    return true
  } catch {
    return false
  }
}
