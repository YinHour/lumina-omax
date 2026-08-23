import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { RedactionCard } from './RedactionCard'

const state = vi.hoisted(() => ({
  user: { role: 'admin' as string | null },
  settings: { redaction_enabled: false },
  rules: [
    {
      id: 'redaction_rule:1',
      original: '张三',
      alias: '工程师A',
      category: 'person',
      enabled: true,
      source: 'manual',
      note: null,
    },
    {
      id: 'redaction_rule:2',
      original: '兴305-2井',
      alias: '实验井C',
      category: 'well',
      enabled: true,
      source: 'auto',
      note: null,
    },
  ],
}))

const mutations = vi.hoisted(() => ({
  create: { mutateAsync: vi.fn(), isPending: false },
  update: { mutateAsync: vi.fn(), isPending: false },
  remove: { mutateAsync: vi.fn(), isPending: false },
  updateSettings: { mutateAsync: vi.fn(), isPending: false },
}))

vi.mock('@/lib/stores/auth-store', () => ({
  useAuthStore: () => ({ user: state.user, token: 't' }),
}))

vi.mock('@/lib/hooks/use-settings', () => ({
  useSettings: () => ({
    data: state.settings,
    isLoading: false,
    isFetching: false,
    error: null,
  }),
  useUpdateSettings: () => ({
    mutateAsync: mutations.updateSettings.mutateAsync,
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/use-redaction-rules', () => ({
  useRedactionRules: () => ({
    data: state.rules,
    isLoading: false,
    error: null,
  }),
  useCreateRedactionRule: () => mutations.create,
  useUpdateRedactionRule: () => mutations.update,
  useDeleteRedactionRule: () => mutations.remove,
}))

vi.mock('sonner', () => ({
  toast: vi.fn(),
}))

describe('RedactionCard', () => {
  beforeEach(() => {
    state.user = { role: 'admin' }
    state.settings = { redaction_enabled: false }
    mutations.create.mutateAsync.mockReset()
    mutations.update.mutateAsync.mockReset()
    mutations.remove.mutateAsync.mockReset()
    mutations.updateSettings.mutateAsync.mockReset()
  })

  it('renders nothing for non-admin users', () => {
    state.user = { role: 'user' }
    const { container } = render(<RedactionCard />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders title, dictionary and rules for admins', () => {
    render(<RedactionCard />)
    expect(
      screen.getByText('Content Redaction (Egress Protection)')
    ).toBeInTheDocument()
    expect(screen.getByText('张三')).toBeInTheDocument()
    expect(screen.getByText('工程师A')).toBeInTheDocument()
    expect(screen.getByText('Manual')).toBeInTheDocument() // source of rule 1
    expect(screen.getByText('Auto')).toBeInTheDocument() // source of rule 2
    // 'Person' appears in the table cell and in the category select
    expect(screen.getAllByText('Person').length).toBeGreaterThan(1)
  })

  it('add-rule button disabled until both fields are filled', () => {
    render(<RedactionCard />)
    const addButton = screen.getByRole('button', { name: /add/i })
    expect(addButton).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Sensitive term'), {
      target: { value: '王五' },
    })
    expect(addButton).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Alias'), {
      target: { value: '工程师B' },
    })
    expect(addButton).not.toBeDisabled()
  })

  it('adding a rule calls the create mutation and clears inputs', async () => {
    render(<RedactionCard />)
    fireEvent.change(screen.getByLabelText('Sensitive term'), {
      target: { value: '王五' },
    })
    fireEvent.change(screen.getByLabelText('Alias'), {
      target: { value: '工程师B' },
    })
    fireEvent.click(screen.getByRole('button', { name: /add/i }))
    await waitFor(() =>
      expect(mutations.create.mutateAsync).toHaveBeenCalledWith({
        original: '王五',
        alias: '工程师B',
        category: 'person',
      })
    )
    await waitFor(() =>
      expect(screen.getByLabelText('Sensitive term')).toHaveValue('')
    )
  })

  it('delete asks for confirmation then calls the delete mutation', async () => {
    render(<RedactionCard />)
    fireEvent.click(screen.getAllByLabelText('Delete')[0])
    expect(
      await screen.findByText('Delete dictionary entry')
    ).toBeInTheDocument()
    expect(screen.getByText(/Delete '张三'\?/)).toBeInTheDocument()
    const confirmButton = screen.getByRole('button', { name: 'Delete', exact: true })
    fireEvent.click(confirmButton)
    await waitFor(() =>
      expect(mutations.remove.mutateAsync).toHaveBeenCalledWith(
        'redaction_rule:1'
      )
    )
  })

  it('toggling a rule status calls the update mutation', async () => {
    render(<RedactionCard />)
    fireEvent.click(screen.getAllByText('Enabled')[0])
    await waitFor(() =>
      expect(mutations.update.mutateAsync).toHaveBeenCalledWith({
        id: 'redaction_rule:1',
        data: { enabled: false },
      })
    )
  })
})
