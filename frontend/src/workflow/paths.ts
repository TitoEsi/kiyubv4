export function roleHome(role?: string | null): string {
  switch (role) {
    case 'CLIENT':
      return '/client'
    case 'ARCHITECT':
      return '/architect'
    case 'MAIN_ADMIN':
      return '/admin'
    case 'IT_PERSONNEL':
      return '/it'
    default:
      return '/login'
  }
}
