export function normalizeRecordId(id?: unknown): string | null {
  if (!id) return null

  if (typeof id === 'object') {
    const record = id as Record<string, unknown>
    return normalizeRecordId(record.id ?? record.tb ?? record.value ?? record.toString?.())
  }

  const text = String(id)
  const objectIdMatch = text.match(/['"]?id['"]?\s*:\s*['"]([^'"]+)['"]/)
  if (objectIdMatch?.[1]) {
    return normalizeRecordId(objectIdMatch[1])
  }
  return text.includes(':') ? text.split(':').pop() || text : text
}

export function sameRecordId(left?: unknown, right?: unknown): boolean {
  const normalizedLeft = normalizeRecordId(left)
  const normalizedRight = normalizeRecordId(right)
  return !!normalizedLeft && !!normalizedRight && normalizedLeft === normalizedRight
}
