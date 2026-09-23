import WorkflowShell from './WorkflowShell'

export default function ContactPage() {
  return (
    <WorkflowShell title="Contact" crumbs={[{ label: 'Contact' }]}>
      <article className="studio-home studio-prose">
        <p className="studio-meta">Contact us</p>
        <h1 className="studio-greeting-title">Have a question about your project?</h1>
        <p>We are here to help with project access, review, and studio workflow.</p>
        {/* CONTACT_EMAIL: set when studio contact is configured. Do not invent addresses. */}
        <dl className="studio-contact-dl">
          <div>
            <dt>Email</dt>
            <dd className="wf-hint">Not configured</dd>
          </div>
          <div>
            <dt>Studio</dt>
            <dd className="wf-hint">Not configured</dd>
          </div>
        </dl>
      </article>
    </WorkflowShell>
  )
}
