import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CreateNotebookDialog } from './CreateNotebookDialog'

const mutateAsync = vi.fn()

vi.mock('@/lib/hooks/use-notebooks', () => ({
  useCreateNotebook: () => ({
    mutateAsync,
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    t: {
      common: {
        cancel: '取消',
        creating: '创建中',
        description: '描述',
        name: '名称',
        nameRequired: '这是必填项',
      },
      notebooks: {
        createNew: '创建笔记本',
        createNewDesc: '创建一个新的笔记本。',
        descPlaceholder: '添加描述',
        leaveBlankForNoPassword: '留空表示不设置密码',
        namePlaceholder: '输入笔记本名称',
        passwordOptional: '密码 (可选)',
      },
    },
  }),
}))

describe('CreateNotebookDialog', () => {
  it('uses localized validation copy when the notebook name is cleared', async () => {
    render(<CreateNotebookDialog open onOpenChange={vi.fn()} />)

    const nameInput = screen.getByLabelText('名称 *')
    fireEvent.change(nameInput, { target: { value: '临时笔记本' } })
    fireEvent.change(nameInput, { target: { value: '' } })

    await waitFor(() => {
      expect(screen.getByText('这是必填项')).toBeInTheDocument()
    })
    expect(screen.queryByText('Name is required')).not.toBeInTheDocument()
  })
})
