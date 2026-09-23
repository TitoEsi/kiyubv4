import { useAuth } from '../workflow/auth'
import { displayNameFromEmail, greetingWord } from '../workflow/displayName'

export default function GreetingBanner({
  lede = 'Ready to design your next space?',
}: {
  lede?: string
}) {
  const { user } = useAuth()
  const name = displayNameFromEmail(user?.email || 'there')
  return (
    <section className="studio-greeting" aria-label="Greeting">
      <h1 className="studio-greeting-title">{greetingWord()}, {name}.</h1>
      <p className="studio-greeting-lede">{lede}</p>
    </section>
  )
}
