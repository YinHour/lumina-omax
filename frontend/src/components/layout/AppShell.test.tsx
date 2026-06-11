import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AppShell } from './AppShell'

vi.mock('./SetupBanner', () => ({
  SetupBanner: () => <div>Setup banner</div>,
}))

vi.mock('./AppSidebar', () => ({
  AppSidebar: ({
    mobileOpen,
    onMobileOpenChange,
  }: {
    mobileOpen: boolean
    onMobileOpenChange: (open: boolean) => void
  }) => (
    <div>
      <span>Mobile open: {String(mobileOpen)}</span>
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

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    expect(screen.getByText('Mobile open: true')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Mock close navigation' }))
    expect(screen.getByText('Mobile open: false')).toBeInTheDocument()
  })
})
