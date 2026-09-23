import { logoSrc, useTheme } from '../theme/theme'

export { logoSrc }

export default function KiyubLogo({
  variant = 'full',
  decorative = false,
  className,
}: {
  variant?: 'full' | 'mark'
  decorative?: boolean
  className?: string
}) {
  const { theme } = useTheme()
  const src = logoSrc(theme, variant)
  const classes = [
    'kiyub-logo',
    variant === 'mark' ? 'kiyub-logo--mark' : 'kiyub-logo--full',
    className,
  ].filter(Boolean).join(' ')

  return (
    <img
      src={src}
      alt={decorative ? '' : 'KIYUB'}
      className={classes}
      draggable={false}
    />
  )
}
