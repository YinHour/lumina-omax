import { describe, expect, it } from 'vitest'
import {
  convertReferencesToCompactMarkdown,
  convertReferencesToMarkdownLinks,
  normalizeBracketedReferenceList,
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

describe('already-numbered anchor links are not double-converted', () => {
  it('keeps plain [1](#ref-source-abc) links untouched in compact conversion', () => {
    const input = 'Evidence [1](#ref-source-6462jcxkee5dqz25avy8).'
    expect(convertReferencesToCompactMarkdown(input)).toBe(input)
  })

  it('keeps plain [1](#ref-source-abc) links untouched in markdown-links conversion', () => {
    const input = 'Evidence [1](#ref-source-6462jcxkee5dqz25avy8).'
    expect(convertReferencesToMarkdownLinks(input)).toBe(input)
  })

  it('normalizes a bracketed comma-separated list of anchor links', () => {
    const input =
      '[[1](#ref-source-6462jcxkee5dqz25avy8), [2](#ref-source-nuiny1vir6aernyc2npo)].'
    const expected =
      '[1](#ref-source-6462jcxkee5dqz25avy8), [2](#ref-source-nuiny1vir6aernyc2npo).'
    expect(normalizeBracketedReferenceList(input)).toBe(expected)
    expect(convertReferencesToCompactMarkdown(input)).toBe(expected)
  })

  it('still converts bare [source:abc] references next to protected links', () => {
    const input =
      'Text [1](#ref-source-6462jcxkee5dqz25avy8) and [source:nuiny1vir6aernyc2npo].'
    const result = convertReferencesToCompactMarkdown(input)
    expect(result).toContain('[1](#ref-source-6462jcxkee5dqz25avy8)')
    expect(result).toContain('[1] - [source:nuiny1vir6aernyc2npo](#ref-source-nuiny1vir6aernyc2npo)')
  })

  it('unescapes backtick-wrapped anchor links in markdown-links conversion', () => {
    const input = 'Evidence `[1](#ref-source-6462jcxkee5dqz25avy8)`.'
    expect(convertReferencesToMarkdownLinks(input)).toBe(
      'Evidence [1](#ref-source-6462jcxkee5dqz25avy8).'
    )
  })

  it('unescapes backtick-wrapped anchor links in compact conversion', () => {
    const input = 'Evidence `[1](#ref-source-6462jcxkee5dqz25avy8)`.'
    expect(convertReferencesToCompactMarkdown(input)).toBe(
      'Evidence [1](#ref-source-6462jcxkee5dqz25avy8).'
    )
  })

  it('handles backtick-wrapped anchor links next to bare references', () => {
    const input =
      'Evidence `[1](#ref-source-6462jcxkee5dqz25avy8)` and [source:nuiny1vir6aernyc2npo].'
    const result = convertReferencesToMarkdownLinks(input)
    expect(result).toContain('[1](#ref-source-6462jcxkee5dqz25avy8)')
    expect(result).not.toContain('`[1]')
  })
})
