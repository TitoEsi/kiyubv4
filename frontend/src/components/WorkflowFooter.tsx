import { Link } from 'react-router-dom'

export default function WorkflowFooter() {
  return (
    <footer className="wf-foot">
      <Link to="/about">About</Link>
      <Link to="/contact">Contact</Link>
      <Link to="/terms">Terms</Link>
      <Link to="/privacy">Privacy</Link>
    </footer>
  )
}
