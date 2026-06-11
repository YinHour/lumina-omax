import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PageContainer } from './PageContainer'
import { PageHeader } from './PageHeader'

describe('page layout primitives', () => {
  it('renders title, description, breadcrumb, and actions', () => {
    render(
      <PageHeader
        eyebrow="Workspace"
        title="Notebooks"
        description="Organize research materials."
        actions={<button type="button">Create</button>}
      />
    )

    expect(screen.getByText('Workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Notebooks' })).toBeInTheDocument()
    expect(screen.getByText('Organize research materials.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('supports readable and wide page widths', () => {
    const { rerender } = render(<PageContainer width="readable">Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-4xl')

    rerender(<PageContainer width="wide">Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-7xl')
  })

  it('defaults to wide and supports full page width', () => {
    const { rerender } = render(<PageContainer>Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-7xl')

    rerender(<PageContainer width="full">Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-none')
  })

  it('forwards scroll area props to the outer element and content classes to the inner element', () => {
    const onScroll = vi.fn()

    render(
      <PageContainer
        aria-label="Research content"
        className="space-y-6"
        onScroll={onScroll}
        style={{ height: 320 }}
      >
        Body
      </PageContainer>
    )

    const scrollArea = screen.getByLabelText('Research content')
    const content = screen.getByText('Body')

    expect(scrollArea).toHaveAttribute('data-slot', 'page-scroll-area')
    expect(scrollArea).toHaveClass('min-h-0', 'flex-1', 'overflow-y-auto')
    expect(scrollArea).toHaveStyle({ height: '320px' })
    expect(content).toHaveAttribute('data-slot', 'page-container')
    expect(content).toHaveClass('space-y-6')
    expect(scrollArea).not.toHaveClass('space-y-6')

    fireEvent.scroll(scrollArea)
    expect(onScroll).toHaveBeenCalledOnce()
  })

  it('can disable scrolling on the outer element', () => {
    render(
      <PageContainer aria-label="Static content" scroll={false}>
        Body
      </PageContainer>
    )

    expect(screen.getByLabelText('Static content')).not.toHaveClass('overflow-y-auto')
  })
})
