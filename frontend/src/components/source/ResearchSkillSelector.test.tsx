import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ResearchSkillSelector } from './ResearchSkillSelector'
import type { ResearchSkillSummary } from '@/lib/types/api'

const skills: ResearchSkillSummary[] = [
  {
    id: 'literature-doi-verification',
    name: 'server name',
    version: '1.0.0',
    category: 'literature',
    description: 'server description',
    source: 'Lumiton Omax curated methodology',
    license: 'MIT',
    review_status: 'approved',
    allowed_tools: [],
    order: 1,
  },
  {
    id: 'doe-statistical-plan',
    name: 'server name',
    version: '1.0.0',
    category: 'experimental-design',
    description: 'server description',
    source: 'Lumiton Omax curated methodology',
    license: 'MIT',
    review_status: 'approved',
    allowed_tools: [],
    order: 4,
  },
]

describe('ResearchSkillSelector', () => {
  it('uses localized names and emits explicit selection', () => {
    const onChange = vi.fn()
    render(
      <ResearchSkillSelector
        skills={skills}
        mode="auto"
        selectedIds={[]}
        onChange={onChange}
      />,
    )

    const trigger = screen.getByRole('button', { name: 'Research methods' })
    trigger.focus()
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })
    const doiMethod = screen.getByRole('menuitemcheckbox', {
      name: /Literature search & DOI verification/,
    })
    fireEvent.click(doiMethod)

    expect(screen.queryByText('server name')).not.toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(
      'selected',
      ['literature-doi-verification'],
    )
  })

  it('disables additional methods after three are selected', () => {
    render(
      <ResearchSkillSelector
        skills={skills}
        mode="selected"
        selectedIds={[
          'doe-statistical-plan',
          'hthp-brine-validation',
          'structured-research-report',
        ]}
        onChange={vi.fn()}
      />,
    )

    const trigger = screen.getByRole('button', { name: 'Research methods' })
    trigger.focus()
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })

    expect(screen.getByRole('menuitemcheckbox', {
      name: /Literature search & DOI verification/,
    })).toHaveAttribute('data-disabled')
  })
})
