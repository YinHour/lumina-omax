import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useRef, useState } from 'react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { usePathname } from 'next/navigation'

import { AppSidebar } from './AppSidebar'
import { useAuth } from '@/lib/hooks/use-auth'
import { useSidebarStore } from '@/lib/stores/sidebar-store'
import { useRecentNotebooksStore } from '@/lib/stores/recent-notebooks-store'

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}))

// Mock Tooltip components to avoid Radix UI async issues in tests
vi.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

describe('AppSidebar', () => {
  const defaultProps = {
    mobileOpen: false,
    onMobileOpenChange: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    useRecentNotebooksStore.setState({ recentNotebooks: [] })
    vi.mocked(usePathname).mockReturnValue('')
    vi.mocked(useSidebarStore).mockReturnValue({
      isCollapsed: false,
      toggleCollapse: vi.fn(),
    })
  })

  it('renders correctly when expanded', () => {
    render(<AppSidebar {...defaultProps} />)
    
    expect(screen.getByTestId('sidebar-brand')).toBeInTheDocument()
    
    // Check for navigation items (using actual locale values)
    expect(screen.getByText(/Sources/i)).toBeDefined()
    expect(screen.getByText(/Notebooks/i)).toBeDefined()
    expect(screen.getByRole('link', { name: 'Usage' })).toHaveAttribute('href', '/usage')
  })

  it('toggles collapse state when clicking handle', () => {
    const toggleCollapse = vi.fn()
    vi.mocked(useSidebarStore).mockReturnValue({
      isCollapsed: false,
      toggleCollapse,
    })

    render(<AppSidebar {...defaultProps} />)
    
    fireEvent.click(screen.getByTestId('sidebar-toggle'))
    
    expect(toggleCollapse).toHaveBeenCalled()
  })

  it('keeps the mobile drawer expanded when the desktop sidebar is collapsed', () => {
    vi.mocked(useSidebarStore).mockReturnValue({
      isCollapsed: true,
      toggleCollapse: vi.fn(),
    })

    render(<AppSidebar {...defaultProps} />)

    expect(screen.getByRole('complementary', { name: 'Primary navigation' })).toHaveClass(
      'md:w-16'
    )
  })

  it('marks the active notebooks link as the current page', () => {
    vi.mocked(usePathname).mockReturnValue('/notebooks/123')

    render(<AppSidebar {...defaultProps} />)

    expect(screen.getByRole('link', { name: 'Notebooks' })).toHaveAttribute(
      'aria-current',
      'page'
    )
  })

  it('closes the mobile navigation when a link is clicked', () => {
    const onMobileOpenChange = vi.fn()

    render(
      <AppSidebar
        mobileOpen
        onMobileOpenChange={onMobileOpenChange}
      />
    )

    const dialog = screen.getByRole('dialog', { name: 'Primary navigation' })
    const notebooksLink = dialog.querySelector<HTMLAnchorElement>('a[href="/notebooks"]')
    expect(notebooksLink).not.toBeNull()
    notebooksLink!.addEventListener('click', event => event.preventDefault())
    fireEvent.click(notebooksLink!)

    expect(onMobileOpenChange).toHaveBeenCalledWith(false)
  })

  it('only mounts mobile navigation content while the dialog is open', () => {
    const { rerender } = render(<AppSidebar {...defaultProps} />)

    expect(screen.queryByRole('dialog', { name: 'Primary navigation' })).not.toBeInTheDocument()

    rerender(
      <AppSidebar
        mobileOpen
        onMobileOpenChange={defaultProps.onMobileOpenChange}
      />
    )

    expect(screen.getByRole('dialog', { name: 'Primary navigation' })).toBeInTheDocument()
  })

  it('closes the mobile dialog on Escape', () => {
    const onMobileOpenChange = vi.fn()

    render(
      <AppSidebar
        mobileOpen
        onMobileOpenChange={onMobileOpenChange}
      />
    )

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(onMobileOpenChange).toHaveBeenCalledWith(false)
  })

  it('provides a visible control to close the mobile navigation', () => {
    const onMobileOpenChange = vi.fn()

    render(
      <AppSidebar
        mobileOpen
        onMobileOpenChange={onMobileOpenChange}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Close navigation' }))

    expect(onMobileOpenChange).toHaveBeenCalledWith(false)
  })

  it('marks only the longest matching settings route as current', () => {
    vi.mocked(usePathname).mockReturnValue('/settings/api-keys')
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        username: 'admin',
        display_name: 'Admin',
        role: 'admin',
        status: 'active',
      },
      logout: vi.fn(),
      isLoading: false,
      error: null,
      login: vi.fn(),
      register: vi.fn(),
    })

    render(<AppSidebar {...defaultProps} />)

    expect(screen.getByRole('link', { name: 'Models' })).toHaveAttribute(
      'aria-current',
      'page'
    )
    expect(screen.getByRole('link', { name: 'Settings' })).not.toHaveAttribute(
      'aria-current'
    )
  })

  it('restores focus to the mobile opener when the dialog closes', async () => {
    function SidebarHarness() {
      const [mobileOpen, setMobileOpen] = useState(false)
      const mobileTriggerRef = useRef<HTMLButtonElement | null>(null)

      return (
        <>
          <button
            type="button"
            ref={mobileTriggerRef}
            onClick={() => setMobileOpen(true)}
          >
            Open navigation
          </button>
          <AppSidebar
            mobileOpen={mobileOpen}
            onMobileOpenChange={setMobileOpen}
            mobileTriggerRef={mobileTriggerRef}
          />
        </>
      )
    }

    render(<SidebarHarness />)

    const opener = screen.getByRole('button', { name: 'Open navigation' })
    fireEvent.click(opener)
    expect(screen.getByRole('dialog', { name: 'Primary navigation' })).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(screen.queryByRole('dialog', { name: 'Primary navigation' })).not.toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toBe(opener))
  })

  it('uses semantic sidebar tokens for active navigation state', () => {
    render(<AppSidebar {...defaultProps} />)

    const notebooksLink = screen.getByRole('link', { name: 'Notebooks' })
    const notebooksButton = notebooksLink.querySelector('button')

    expect(notebooksButton).toHaveClass(
      'data-[active=true]:bg-sidebar-accent',
      'data-[active=true]:text-sidebar-accent-foreground',
      'data-[active=true]:before:bg-sidebar-primary'
    )
    expect(notebooksButton?.className).not.toContain('indigo')
  })

  it('adds a native title to recent notebook links for long names', () => {
    const longName = 'A very long recently opened notebook title for visual verification'
    useRecentNotebooksStore.setState({
      recentNotebooks: [
        {
          id: 'notebook:new-owned',
          name: longName,
          openedAt: Date.now(),
        },
      ],
    })

    render(<AppSidebar {...defaultProps} />)

    expect(screen.getByRole('link', { name: longName })).toHaveAttribute('title', longName)
  })
})
