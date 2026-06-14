import { render, screen } from '@testing-library/react'
import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'
import { getRemainingSourceSlots, getSourceBatchLimit, SourceTypeStep } from './SourceTypeStep'

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    t: {
      common: {
        optional: 'optional',
        title: 'Title',
      },
      sources: {
        addUrl: 'Add URL',
        batchUrlHint: 'Enter one URL per line.',
        enterText: 'Enter Text',
        enterUrlsPlaceholder: 'https://example.com',
        fileLabel: 'File',
        filesCount: '{count} files',
        fixInvalidUrls: 'Fix invalid URLs.',
        htmlDetected: 'HTML detected.',
        invalidUrlsDetected: 'Invalid URLs detected',
        lineLabel: 'Line {line}',
        maxFilesAllowed: 'Maximum {count} files allowed',
        maxItems: 'max {count}',
        processDescription: 'Process description',
        selectMultipleFilesHint: 'Select files.',
        selectedFiles: 'Selected files:',
        sourceLimitReached: 'This notebook already has the maximum {count} source(s).',
        textContentLabel: 'Text',
        textPlaceholder: 'Paste text',
        title: 'Sources',
        titleGenerated: 'Title generated',
        titlePlaceholder: 'Title',
        titleRequired: 'Title required',
        uploadFile: 'Upload File',
        urlLabel: 'URL',
        urlsCount: '{count} URLs',
      },
    },
  }),
}))

function SourceTypeStepHarness(props: { remainingSlots: number; sourceLimit: number }) {
  const form = useForm({
    defaultValues: {
      type: 'link' as const,
      embed: true,
      async_processing: true,
    },
  })

  return (
    <SourceTypeStep
      control={form.control}
      register={form.register}
      setValue={form.setValue}
      errors={{}}
      sourceBatchLimit={props.remainingSlots}
      sourceLimit={props.sourceLimit}
    />
  )
}

describe('getSourceBatchLimit', () => {
  it('uses configured limits and falls back to 50 for invalid values', () => {
    expect(getSourceBatchLimit(3)).toBe(3)
    expect(getSourceBatchLimit(undefined)).toBe(50)
    expect(getSourceBatchLimit(null)).toBe(50)
    expect(getSourceBatchLimit(0)).toBe(50)
    expect(getSourceBatchLimit(201)).toBe(50)
  })
})

describe('getRemainingSourceSlots', () => {
  it('uses the notebook source count to cap additional sources', () => {
    expect(getRemainingSourceSlots(49, 50)).toBe(1)
    expect(getRemainingSourceSlots(50, 50)).toBe(0)
    expect(getRemainingSourceSlots(51, 50)).toBe(0)
    expect(getRemainingSourceSlots(-1, 50)).toBe(50)
  })
})

describe('SourceTypeStep', () => {
  it('shows a notebook source limit notice when no source slots remain', () => {
    render(<SourceTypeStepHarness remainingSlots={0} sourceLimit={50} />)

    expect(
      screen.getByText('This notebook already has the maximum 50 source(s).'),
    ).toBeInTheDocument()
  })
})
