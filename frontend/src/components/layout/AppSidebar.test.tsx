import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { usePathname } from 'next/navigation'

import { AppSidebar } from './AppSidebar'
import { useSidebarStore } from '@/lib/stores/sidebar-store'

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
      'w-64',
      'md:w-16'
    )
    expect(screen.getByTestId('sidebar-brand').parentElement).toHaveClass('md:hidden')
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

    const notebooksLink = screen.getByRole('link', { name: 'Notebooks' })
    notebooksLink.addEventListener('click', event => event.preventDefault())
    fireEvent.click(notebooksLink)

    expect(onMobileOpenChange).toHaveBeenCalledWith(false)
  })
})
