import { useState } from 'react'
import { DownloadSimple } from '@phosphor-icons/react'
import { exportArchitecturalPdf } from '../export/architecturalPdf'
import { useFormat } from '../units/UnitsProvider'
import { PUBLISHED_PLAN_UNAVAILABLE, type PublishedExport } from '../workflow/publishedExport'

export default function ExportPdfButton({ published }: { published: PublishedExport | null }) {
  const fmt = useFormat()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const enabled = !!published && !busy

  return (
    <>
      <button
        type="button"
        className="export-btn"
        disabled={!enabled}
        aria-disabled={!enabled}
        title={published ? `Exports Published Version v${published.version}` : 'Export is available after the project is published'}
        onClick={!enabled || !published ? undefined : async () => {
          const source = published
          setError(null)
          setBusy(true)
          try {
            await exportArchitecturalPdf(source, fmt.unit)
          } catch (err) {
            console.error('PDF export failed', {
              projectId: source.projectId,
              revisionId: source.revisionId,
              err,
            })
            setError(err instanceof Error && err.message === PUBLISHED_PLAN_UNAVAILABLE
              ? PUBLISHED_PLAN_UNAVAILABLE
              : 'Could not export PDF.')
          } finally {
            setBusy(false)
          }
        }}
      >
        <DownloadSimple size={16} aria-hidden /> Export PDF
      </button>
      {error && <span className="error-msg editor-export-error" role="alert">{error}</span>}
    </>
  )
}
