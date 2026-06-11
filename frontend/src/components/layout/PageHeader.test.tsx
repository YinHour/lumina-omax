import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
})
