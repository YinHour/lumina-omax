function normalizeOutsideInlineCode(line: string): string {
  let result = ''
  let cursor = 0

  while (cursor < line.length) {
    const codeStart = line.indexOf('`', cursor)
    const plainEnd = codeStart === -1 ? line.length : codeStart
    result += line.slice(cursor, plainEnd).replace(
      /\$\$([^\r\n]+?)\$\$/g,
      (_match, formula: string) => `\n\n$$\n${formula.trim()}\n$$\n\n`
    )

    if (codeStart === -1) break

    let delimiterEnd = codeStart
    while (line[delimiterEnd] === '`') delimiterEnd++
    const delimiter = line.slice(codeStart, delimiterEnd)
    const codeEnd = line.indexOf(delimiter, delimiterEnd)

    if (codeEnd === -1) {
      result += line.slice(codeStart)
      break
    }

    result += line.slice(codeStart, codeEnd + delimiter.length)
    cursor = codeEnd + delimiter.length
  }

  return result
}

export function normalizeMathMarkdown(content: string): string {
  let fence: { marker: string; length: number } | null = null

  return content.split('\n').map((line) => {
    if (fence) {
      const closingFence = new RegExp(
        `^ {0,3}${fence.marker}{${fence.length},}\\s*$`
      )
      if (closingFence.test(line)) fence = null
      return line
    }

    const openingFence = line.match(/^ {0,3}(`{3,}|~{3,})/)
    if (openingFence) {
      fence = {
        marker: openingFence[1][0],
        length: openingFence[1].length,
      }
      return line
    }

    return normalizeOutsideInlineCode(line)
  }).join('\n')
}
