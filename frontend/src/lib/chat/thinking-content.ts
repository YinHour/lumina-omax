const THINK_BLOCK = /<think\b[^>]*>[\s\S]*?<\/think\s*>/gi
const THINK_OPEN = /<think\b[^>]*>/i
const THINK_CLOSE = /<\/think\s*>/i

/** Remove model reasoning tags, including incomplete blocks during streaming. */
export function stripThinkingContent(content: string): string {
  let visible = content.replace(THINK_BLOCK, '')

  const openMatch = THINK_OPEN.exec(visible)
  const closeMatch = THINK_CLOSE.exec(visible)

  if (closeMatch && (!openMatch || closeMatch.index < openMatch.index)) {
    visible = visible.slice(closeMatch.index + closeMatch[0].length)
  }

  const remainingOpen = THINK_OPEN.exec(visible)
  if (remainingOpen) {
    visible = visible.slice(0, remainingOpen.index)
  }

  return visible.trim()
}
