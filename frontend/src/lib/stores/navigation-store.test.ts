import { describe, expect, it, beforeEach } from 'vitest'
import { useNavigationStore } from './navigation-store'

describe('navigation store', () => {
  beforeEach(() => {
    sessionStorage.clear()
    useNavigationStore.getState().clearReturnTo()
  })

  it('does not provide a hard-coded English default return label', () => {
    expect(useNavigationStore.getState().getReturnLabel()).toBe('')
  })
})
