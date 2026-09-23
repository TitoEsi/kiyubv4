export function displayNameFromEmail(email: string): string {
  const local = (email.split('@')[0] || 'there').trim()
  const token = local.split(/[._+-]/)[0] || 'there'
  return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase()
}

export function greetingWord(now = new Date()): string {
  const h = now.getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export function formatRelative(iso?: string | null, now = new Date()): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const delta = now.getTime() - d.getTime()
  const minutes = Math.round(delta / 60000)
  if (minutes < 1) return 'Updated just now'
  if (minutes < 60) return `Updated ${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `Updated ${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  if (days < 14) return `Updated ${days} day${days === 1 ? '' : 's'} ago`
  return `Updated ${d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}`
}

export function formatDate(iso?: string | null): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
