import type { Revision } from './api'

/** Display-only description of how a version came to exist. */
export function versionSourceLabel(rev: Revision, all: Revision[] = []): string {
  switch (rev.source_type) {
    case 'AI_GENERATED':
      return 'AI generated'
    case 'REVIEW':
      return 'Sent for review'
    case 'RESTORED': {
      const from = all.find(r => r.id === rev.source_revision_id)
      const base = from ? `Restored from Version ${from.version}` : 'Restored'
      return rev.submitted_at ? `${base} · sent for review` : `${base} · draft`
    }
    case 'PUBLISHED':
      return 'Published'
    case 'ARCHITECT_EDIT':
    case 'REVISION':
      return 'Architect edit'
    default:
      return rev.source_type
  }
}
