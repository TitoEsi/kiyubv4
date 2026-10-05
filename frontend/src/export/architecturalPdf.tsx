import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import type { jsPDF } from 'jspdf'
import ScenePlan2D from '../components/ScenePlan2D'
import { UnitsScope } from '../units/UnitsProvider'
import { formatStamp } from '../workflow/commentThreads'
import { questionnaireDetailRows, type DetailRow } from '../workflow/questionnaireDetails'
import { PUBLISHED_PLAN_UNAVAILABLE, type PublishedExport } from '../workflow/publishedExport'
import { roomSchedule, scheduleSummary } from './roomSchedule'
import { titleBlockUnit } from './titleBlock'
import type { MeasurementUnit } from '../units/measurement'

const MARGIN = 40
const CHROME = 72
const INK: [number, number, number] = [23, 25, 28]
const MUTED: [number, number, number] = [95, 102, 112]
const RULE: [number, number, number] = [214, 210, 202]
const BAND: [number, number, number] = [247, 244, 239]

function renderSheet(
  published: PublishedExport,
  frame: { width: number; height: number },
  unit: MeasurementUnit,
): { svg: SVGSVGElement; cleanup: () => void } {
  const host = document.createElement('div')
  host.style.position = 'fixed'
  host.style.left = '-10000px'
  host.style.top = '0'
  host.style.width = `${frame.width}px`
  host.style.height = `${frame.height}px`
  document.body.appendChild(host)
  const root = createRoot(host)
  flushSync(() => {
    root.render(
      <UnitsScope unit={unit}>
        <ScenePlan2D
          frame={frame}
          scene={published.scene}
          lot={published.lot}
          tool="select"
          snapEnabled={false}
          grid={0}
          editingEnabled={false}
          selected={null}
          onSelect={() => undefined}
          zoom={1}
          pan={{ x: 0, y: 0 }}
        />
      </UnitsScope>,
    )
  })
  const svg = host.querySelector('svg')
  if (!svg) {
    root.unmount()
    host.remove()
    throw new Error(PUBLISHED_PLAN_UNAVAILABLE)
  }
  return {
    svg,
    cleanup: () => {
      root.unmount()
      host.remove()
    },
  }
}

async function logoDataUrl(): Promise<string | null> {
  try {
    const res = await fetch('/kiyub-logo-dark.png')
    if (!res.ok) return null
    const bytes = new Uint8Array(await res.arrayBuffer())
    let binary = ''
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return `data:image/png;base64,${btoa(binary)}`
  } catch {
    return null
  }
}

function drawChrome(
  pdf: jsPDF,
  meta: PublishedExport,
  drawingTitle: string,
  unit: MeasurementUnit,
  logo: string | null,
) {
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const y = pageH - 46
  pdf.setDrawColor(...INK)
  pdf.setLineWidth(0.7)
  pdf.line(MARGIN, y - 16, pageW - MARGIN, y - 16)
  let textX = MARGIN
  if (logo) {
    pdf.addImage(logo, 'PNG', MARGIN, y - 10, 78, 18)
    textX = MARGIN + 88
  }
  pdf.setTextColor(...INK)
  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(9)
  pdf.text('KIYUB', textX, y)
  pdf.setFont('helvetica', 'normal')
  pdf.setFontSize(8)
  pdf.setTextColor(...MUTED)
  pdf.text(pdf.splitTextToSize(meta.projectName, 220)[0] || 'Project', textX, y + 12)
  pdf.text(`Units: ${titleBlockUnit(unit)}`, textX, y + 24)
  pdf.setTextColor(...INK)
  pdf.setFont('helvetica', 'bold')
  pdf.text(drawingTitle, pageW / 2, y, { align: 'center' })
  pdf.setFont('helvetica', 'normal')
  pdf.setTextColor(...MUTED)
  pdf.text(`Client: ${meta.clientName}`, pageW / 2, y + 12, { align: 'center' })
  pdf.setTextColor(...INK)
  pdf.text(`Published Version v${meta.version}`, pageW - MARGIN, y, { align: 'right' })
  pdf.setTextColor(...MUTED)
  pdf.text(formatStamp(meta.publishedAt) || '—', pageW - MARGIN, y + 12, { align: 'right' })
}

function stampPages(pdf: jsPDF) {
  const total = pdf.getNumberOfPages()
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  for (let i = 1; i <= total; i++) {
    pdf.setPage(i)
    pdf.setFont('helvetica', 'normal')
    pdf.setFontSize(8)
    pdf.setTextColor(...MUTED)
    pdf.text(`Page ${i} of ${total}`, pageW - MARGIN, pageH - 22, { align: 'right' })
  }
}

function heading(pdf: jsPDF, text: string, x: number, y: number): number {
  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(12)
  pdf.setTextColor(...INK)
  pdf.text(text, x, y)
  pdf.setDrawColor(...INK)
  pdf.setLineWidth(0.8)
  pdf.line(x, y + 6, x + 196, y + 6)
  return y + 26
}

function detailTable(pdf: jsPDF, x: number, y: number, width: number, rows: DetailRow[]): number {
  const labelW = 176
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i]
    const value = pdf.splitTextToSize(row.value, width - labelW - 20) as string[]
    const rowH = Math.max(18, value.length * 12 + 6)
    if (i % 2 === 0) {
      pdf.setFillColor(...BAND)
      pdf.rect(x, y - 12, width, rowH, 'F')
    }
    pdf.setFont('helvetica', 'bold')
    pdf.setFontSize(9)
    pdf.setTextColor(...INK)
    pdf.text(row.label, x + 8, y)
    pdf.setFont('helvetica', 'normal')
    pdf.text(value, x + labelW, y)
    y += rowH
  }
  return y
}

function drawProjectPage(pdf: jsPDF, meta: PublishedExport, unit: MeasurementUnit, logo: string | null) {
  const pageW = pdf.internal.pageSize.getWidth()
  const width = pageW - MARGIN * 2
  let y = heading(pdf, 'PROJECT DETAILS', MARGIN, 52)
  const projectRows: DetailRow[] = [
    { label: 'Project name', value: meta.projectName },
    { label: 'Client', value: meta.clientName },
    { label: 'Published version', value: `v${meta.version}` },
    { label: 'Publication date', value: formatStamp(meta.publishedAt) || '—' },
  ]
  y = detailTable(pdf, MARGIN, y, width, projectRows) + 18
  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(10)
  pdf.setTextColor(...INK)
  pdf.text('Client questionnaire', MARGIN, y)
  y += 16
  detailTable(pdf, MARGIN, y, width, questionnaireDetailRows(meta.questionnaire, unit))
  drawChrome(pdf, meta, 'Project Information', unit, logo)
}

function drawSchedulePage(pdf: jsPDF, meta: PublishedExport, unit: MeasurementUnit, logo: string | null) {
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()
  const width = pageW - MARGIN * 2
  const lines = roomSchedule(meta.scene, unit)
  const summary = scheduleSummary(meta.scene, unit)
  const cols = [width * 0.4, width * 0.2, width * 0.2, width * 0.2]
  const headers = ['Room', 'Width', 'Depth', 'Area']
  let y = heading(pdf, 'ROOM SCHEDULE', MARGIN, 52)
  const limit = () => pageH - CHROME - 8

  const header = () => {
    pdf.setFillColor(...INK)
    pdf.rect(MARGIN, y - 12, width, 20, 'F')
    pdf.setTextColor(255, 255, 255)
    pdf.setFont('helvetica', 'bold')
    pdf.setFontSize(8)
    let x = MARGIN
    headers.forEach((label, i) => {
      pdf.text(label, x + 8, y)
      x += cols[i]
    })
    pdf.setTextColor(...INK)
    y += 16
  }

  const nextPage = () => {
    drawChrome(pdf, meta, 'Room Schedule', unit, logo)
    pdf.addPage()
    y = heading(pdf, 'ROOM SCHEDULE', MARGIN, 52)
    header()
  }

  header()
  pdf.setFont('helvetica', 'normal')
  pdf.setFontSize(9)
  lines.forEach((line, i) => {
    if (y + 16 > limit()) nextPage()
    if (i % 2 === 0) {
      pdf.setFillColor(...BAND)
      pdf.rect(MARGIN, y - 11, width, 18, 'F')
    }
    const cells = [line.row.name, line.widthLabel, line.depthLabel, line.areaLabel]
    let x = MARGIN
    cells.forEach((cell, col) => {
      const text = pdf.splitTextToSize(cell, cols[col] - 12)[0] || ''
      pdf.text(text, x + 8, y)
      x += cols[col]
    })
    y += 18
  })

  if (y + 78 > limit()) nextPage()
  y += 12
  pdf.setDrawColor(...RULE)
  pdf.setLineWidth(0.4)
  pdf.line(MARGIN, y - 8, MARGIN + width, y - 8)
  const summaryRows: DetailRow[] = [
    { label: 'Rooms', value: summary.rooms },
    { label: 'Living area', value: summary.livingArea },
    { label: 'Building footprint', value: summary.footprint },
    { label: 'Ceiling Height', value: summary.ceiling },
  ]
  detailTable(pdf, MARGIN, y + 8, width * 0.55, summaryRows)
  drawChrome(pdf, meta, 'Room Schedule', unit, logo)
}

/** Draw the three-page sheet. The download wrapper saves it. */
export async function renderArchitecturalPdf(meta: PublishedExport, unit: MeasurementUnit): Promise<jsPDF> {
  if (!meta.scene.walls?.length && !meta.scene.rooms?.length) {
    throw new Error(PUBLISHED_PLAN_UNAVAILABLE)
  }
  const { jsPDF } = await import('jspdf')
  const { svg2pdf } = await import('svg2pdf.js')
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a3' })
  const logo = await logoDataUrl()
  const pageW = pdf.internal.pageSize.getWidth()
  const pageH = pdf.internal.pageSize.getHeight()

  drawProjectPage(pdf, meta, unit, logo)

  pdf.addPage()
  const drawY = 68
  const frame = { width: pageW - MARGIN * 2, height: pageH - drawY - CHROME }
  pdf.setFont('helvetica', 'bold')
  pdf.setFontSize(12)
  pdf.setTextColor(...INK)
  pdf.text('FLOOR PLAN', MARGIN, 52)
  pdf.setDrawColor(...INK)
  pdf.setLineWidth(0.8)
  pdf.line(MARGIN, 58, MARGIN + 196, 58)

  const sheet = renderSheet(meta, frame, unit)
  try {
    await svg2pdf(sheet.svg, pdf, { x: MARGIN, y: drawY, width: frame.width, height: frame.height })
  } catch (err) {
    console.error('PDF export failed while drawing the floor plan', {
      projectId: meta.projectId,
      revisionId: meta.revisionId,
      err,
    })
    throw err
  } finally {
    sheet.cleanup()
  }
  pdf.setDrawColor(...RULE)
  pdf.setLineWidth(0.6)
  pdf.rect(MARGIN, drawY, frame.width, frame.height)
  drawChrome(pdf, meta, 'Floor Plan', unit, logo)

  pdf.addPage()
  drawSchedulePage(pdf, meta, unit, logo)
  stampPages(pdf)
  return pdf
}

/** Download a three-page architectural PDF of the published scene. */
export async function exportArchitecturalPdf(meta: PublishedExport, unit: MeasurementUnit): Promise<void> {
  const pdf = await renderArchitecturalPdf(meta, unit)
  const safe = meta.projectName.replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'KIYUB'
  pdf.save(`${safe}_v${meta.version}.pdf`)
}
