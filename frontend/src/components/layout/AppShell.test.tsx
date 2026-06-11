import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

vi.mock('./SetupBanner', () => ({
  SetupBanner: () => <div>Setup banner</div>,
}))

vi.mock('./AppSidebar', () => ({
  AppSidebar: ({
    mobileOpen,
    onMobileOpenChange,
    mobileTriggerRef,
  }: {
    mobileOpen: boolean
    onMobileOpenChange: (open: boolean) => void
    mobileTriggerRef: React.RefObject<HTMLButtonElement | null>
  }) => (
    <div>
      <span>Mobile open: {String(mobileOpen)}</span>
      <span>Trigger ref provided: {String(Boolean(mobileTriggerRef))}</span>
      <button type="button" onClick={() => onMobileOpenChange(false)}>
        Mock close navigation
      </button>
    </div>
  ),
}))

describe('AppShell', () => {
  it('controls the mobile navigation state', () => {
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>
    )

    expect(screen.getByText('Mobile open: false')).toBeInTheDocument()
    expect(screen.getByText('Trigger ref provided: true')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getByText('Mobile open: true')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Mock close navigation' }))
    expect(screen.getByText('Mobile open: false')).toBeInTheDocument()
  })

  it('closes mobile navigation when the viewport reaches the desktop breakpoint', () => {
    let handleBreakpointChange: ((event: { matches: boolean }) => void) | undefined
    const removeEventListener = vi.fn()

    vi.mocked(window.matchMedia).mockReturnValue({
      matches: false,
      media: '(min-width: 768px)',
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((event, listener) => {
        if (event === 'change') {
          handleBreakpointChange = listener as (event: { matches: boolean }) => void
        }
      }),
      removeEventListener,
      dispatchEvent: vi.fn(),
    })

    const { unmount } = render(
      <AppShell>
        <div>Page content</div>
      </AppShell>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getByText('Mobile open: true')).toBeInTheDocument()

    act(() => {
      handleBreakpointChange?.({ matches: true })
    })
    expect(screen.getByText('Mobile open: false')).toBeInTheDocument()

    unmount()
    expect(removeEventListener).toHaveBeenCalledWith(
      'change',
      expect.any(Function)
    )
  })
})
