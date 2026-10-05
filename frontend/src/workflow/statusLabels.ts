const DISPLAY: Record<string, string> = {
  FOR_CHECKING: 'Reviewing',
}

/** Display text only; the underlying status values are unchanged. */
export function statusLabel(status: string | null | undefined): string {
  if (!status) return ''
  return DISPLAY[status] ?? status.replace(/_/g, ' ')
}
