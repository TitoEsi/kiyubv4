import { Link } from 'react-router-dom'

export default function StatCard({
  label,
  value,
  to,
}: {
  label: string
  value: number | string
  to?: string
}) {
  const inner = (
    <>
      <p className="studio-meta">{label}</p>
      <p className="studio-stat">{value}</p>
    </>
  )
  if (!to) {
    return <div className="studio-stat-card is-static">{inner}</div>
  }
  return (
    <Link className="studio-stat-card" to={to}>
      {inner}
    </Link>
  )
}
