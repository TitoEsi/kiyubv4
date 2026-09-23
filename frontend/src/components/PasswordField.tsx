import { Eye, EyeSlash } from '@phosphor-icons/react'
import { useState } from 'react'

export default function PasswordField({
  id,
  value,
  onChange,
  autoComplete = 'current-password',
  required = false,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
  required?: boolean
}) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="password-field">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        autoComplete={autoComplete}
        required={required}
      />
      <button
        type="button"
        className="password-toggle"
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
        onClick={() => setVisible(v => !v)}
      >
        {visible ? <EyeSlash size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}
