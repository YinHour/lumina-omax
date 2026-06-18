import { beforeEach, describe, expect, it } from 'vitest'
import { useAskStore } from './ask-store'

describe('useAskStore', () => {
  beforeEach(() => {
    useAskStore.setState({
      isStreaming: false,
      strategy: null,
      answers: [],
      finalAnswer: null,
      coverage: null,
      history: [],
      error: null,
      abortController: null,
    })
  })

  it('stores coverage metadata separately from the final answer', () => {
    useAskStore.getState().setCoverage({
      total_sources: 32,
      embedded_sources: 31,
      retrieved_sources: 10,
      retrieved_source_ids: ['source:a'],
    })

    expect(useAskStore.getState().coverage?.total_sources).toBe(32)
    expect(useAskStore.getState().coverage?.retrieved_sources).toBe(10)
  })

  it('keeps Ask history when clearing the active response', () => {
    useAskStore.getState().addHistoryEntry({
      question: 'How many files?',
      answer: 'Based on retrieved sources...',
      coverage: {
        total_sources: 32,
        embedded_sources: 31,
        retrieved_sources: 10,
        retrieved_source_ids: ['source:a'],
      },
    })

    useAskStore.getState().clearState()

    expect(useAskStore.getState().history).toHaveLength(1)
    expect(useAskStore.getState().history[0].question).toBe('How many files?')
  })
})
