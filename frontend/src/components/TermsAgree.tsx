import { Link } from 'react-router-dom'

export default function TermsAgree({
  id,
  checked,
  onChange,
}: {
  id: string
  checked: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <label className="terms-agree" htmlFor={id}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        required
      />
      <span>
        I agree to the{' '}
        <Link to="/terms" target="_blank" rel="noreferrer">Terms and Conditions</Link>
        {' '}and{' '}
        <Link to="/privacy" target="_blank" rel="noreferrer">Privacy Policy</Link>.
      </span>
    </label>
  )
}
