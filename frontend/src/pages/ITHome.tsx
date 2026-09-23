import { useEffect, useState } from 'react'
import WorkflowShell from './WorkflowShell'
import { listAccounts, listAudit, listInquiries, Inquiry, patchAccount, WorkflowUser } from '../workflow/api'

function pad(n: number) {
  return String(n).padStart(2, '0')
}

export default function ITHome() {
  const [users, setUsers] = useState<WorkflowUser[]>([])
  const [audit, setAudit] = useState<Array<{ id: string; event_type: string; target?: string; created_at: string | null }>>([])
  const [inquiries, setInquiries] = useState<Inquiry[]>([])
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setUsers(await listAccounts())
    setAudit(await listAudit())
    setInquiries(await listInquiries())
  }

  useEffect(() => {
    refresh().catch(e => setError(String(e)))
  }, [])

  async function toggleApproved(user: WorkflowUser) {
    try {
      await patchAccount(user.id, { approved: !user.approved })
      await refresh()
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || 'Could not update account')
    }
  }

  return (
    <WorkflowShell title="IT personnel" crumbs={[{ label: 'Accounts' }]}>
      <div className="studio-home">
        <p className="wf-hint">Account approval and audit. No canvas editing.</p>
        {error && <div className="error-msg" role="alert">{error}</div>}
        <section className="studio-section">
          <h2 className="studio-section-title">Accounts</h2>
          <ol className="studio-register">
            {users.map((u, i) => (
              <li key={u.id} className="studio-row studio-row-static">
                <span className="studio-index">{pad(i + 1)}</span>
                <span className="studio-row-copy">
                  <span className="studio-row-name">{u.email}</span>
                  <span className="studio-row-status">{u.role.replace(/_/g, ' ')} · {u.approved ? 'approved' : 'pending'}</span>
                </span>
                {u.role === 'ARCHITECT' && (
                  <button className="wf-action" type="button" onClick={() => toggleApproved(u)}>
                    {u.approved ? 'Revoke' : 'Approve architect'}
                  </button>
                )}
              </li>
            ))}
          </ol>
        </section>
        <section className="studio-section">
          <h2 className="studio-section-title">Access requests</h2>
          {inquiries.length === 0 ? (
            <p className="wf-hint">No inquiries yet.</p>
          ) : (
            <ol className="studio-notes">
              {inquiries.map((item, i) => (
                <li key={item.id} className="studio-note">
                  <span className="studio-index">{pad(i + 1)}</span>
                  <span>{item.name} · {item.email}</span>
                  <span className="studio-row-activity">{item.message}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
        <section className="studio-section">
          <h2 className="studio-section-title">Audit</h2>
          <ol className="studio-notes">
            {audit.slice(0, 80).map((e, i) => (
              <li key={e.id} className="studio-note">
                <span className="studio-index">{pad(i + 1)}</span>
                <span>{e.event_type}{e.target ? ` · ${e.target}` : ''}</span>
                <span className="studio-row-activity">{e.created_at}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </WorkflowShell>
  )
}
