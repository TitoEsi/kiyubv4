import WorkflowShell from './WorkflowShell'

export default function AboutPage() {
  return (
    <WorkflowShell title="About" crumbs={[{ label: 'About' }]}>
      <article className="studio-home studio-prose">
        <p className="studio-meta">About KIYUB</p>
        <h1 className="studio-greeting-title">Design smarter. Explore faster.</h1>
        <p>
          KIYUB helps clients and architectural professionals transform requirements into
          residential floor-plan concepts through an interactive, AI-assisted design workflow.
        </p>
        <p>
          From the initial brief to floor-plan exploration and review, KIYUB brings the design
          process into one collaborative workspace.
        </p>
        <p>
          KIYUB is a conceptual design and planning tool. It does not replace licensed architects,
          and generated designs are not claimed to be building-code compliant.
        </p>
      </article>
    </WorkflowShell>
  )
}
