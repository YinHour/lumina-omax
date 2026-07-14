import { describe, expect, it } from 'vitest'
import {
  convertReferencesToMarkdownLinks,
  parseSourceReferences,
} from './source-references'

describe('source reference aliases', () => {
  it('normalizes insight references to the canonical source_insight type', () => {
    expect(parseSourceReferences('[insight:ide0gvve6vdoqm6tvt35]')).toEqual([
      expect.objectContaining({
        type: 'source_insight',
        id: 'ide0gvve6vdoqm6tvt35',
      }),
    ])
  })

  it('keeps the model label while linking insight aliases to the insight route', () => {
    expect(convertReferencesToMarkdownLinks('[insight:ide0gvve6vdoqm6tvt35]')).toBe(
      '[[insight:ide0gvve6vdoqm6tvt35]](#ref-source_insight-ide0gvve6vdoqm6tvt35)'
    )
  })
})
