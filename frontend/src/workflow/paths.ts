export function roleHome(role?: string | null): string {
  switch (role) {
    case 'CLIENT':
      return '/client'
    case 'ARCHITECT':
      return '/architect'
    case 'ADMIN':
      return '/admin'
    default:
      return '/login'
  }
}
