/* eslint-disable @typescript-eslint/no-explicit-any */
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { AppSidebar } from './AppSidebar'
import { useSidebarStore } from '@/lib/stores/sidebar-store'

// Mock Tooltip components to avoid Radix UI async issues in tests
vi.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
// But setup.ts has some basic mocks, let's see.

describe('AppSidebar', () => {
  it('renders correctly when expanded', () => {
    render(<AppSidebar />)
    
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
    } as any)

    render(<AppSidebar />)
    
    // The collapse button has ChevronLeft icon when expanded
    // The collapse button has ChevronLeft icon when expanded
    // const toggleButton = screen.getAllByRole('button')[0]
    // Let's use more specific selector if possible, but AppSidebar has many buttons
    // Actually, line 147 has the button
    
    // Use data-testid for reliable selection
    fireEvent.click(screen.getByTestId('sidebar-toggle'))
    
    expect(toggleCollapse).toHaveBeenCalled()
  })

  it('shows collapsed view when isCollapsed is true', () => {
    vi.mocked(useSidebarStore).mockReturnValue({
      isCollapsed: true,
      toggleCollapse: vi.fn(),
    } as any)

    render(<AppSidebar />)
    
    // In collapsed mode, brand text shouldn't be visible
    expect(screen.queryByTestId('sidebar-brand')).not.toBeInTheDocument()
  })
})
