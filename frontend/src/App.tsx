import { Navigate, Route, Routes } from 'react-router-dom'
import { ReactElement } from 'react'
import KiyubLogo from './components/KiyubLogo'
import { AuthProvider, useAuth } from './workflow/auth'
import { UnitsProvider } from './units/UnitsProvider'
import { roleHome } from './workflow/paths'
import type { Role } from './workflow/permissions'
import LoginPage from './pages/LoginPage'
import LandingPage from './pages/LandingPage'
import LegalPage from './pages/LegalPage'
import ClientHome from './pages/ClientHome'
import ArchitectHome from './pages/ArchitectHome'
import ArchitectProjects from './pages/ArchitectProjects'
import ArchitectClients from './pages/ArchitectClients'
import InvitePage from './pages/InvitePage'
import AuthCallback from './pages/AuthCallback'
import ArchitectCompletePage from './pages/ArchitectCompletePage'
import AdminHome from './pages/AdminHome'
import AdminProjectsPage from './pages/AdminProjectsPage'
import ArchitectInvitationsPage from './pages/ArchitectInvitationsPage'
import ArchitectProfilePage from './pages/ArchitectProfilePage'
import HistoryPage from './pages/HistoryPage'
import AdminAnalyticsPage from './pages/AdminAnalyticsPage'
import ProjectPage from './pages/ProjectPage'
import ProjectActivityPage from './pages/ProjectActivityPage'
import StaffArchitectsPage from './pages/StaffArchitectsPage'
import StaffClientsPage from './pages/StaffClientsPage'
import AboutPage from './pages/AboutPage'
import ContactPage from './pages/ContactPage'

function AuthLoading() {
  return (
    <div className="wf-login wf-login-loading">
      <KiyubLogo variant="mark" />
      <p>Loading…</p>
    </div>
  )
}

const ALL_ROLES: Role[] = ['CLIENT', 'ARCHITECT', 'ADMIN']

function Guard({ roles, children }: { roles: Role[]; children: ReactElement }) {
  const { user, ready } = useAuth()
  if (!ready) return <AuthLoading />
  if (!user) return <Navigate to="/login" replace />
  if (roles.length && !roles.includes(user.role)) return <Navigate to={roleHome(user.role)} replace />
  return children
}

function HomeRedirect() {
  const { user, ready } = useAuth()
  if (!ready) return <AuthLoading />
  if (!user) return <LandingPage />
  return <Navigate to={roleHome(user.role)} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <UnitsProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/terms" element={<LegalPage kind="terms" />} />
        <Route path="/privacy" element={<LegalPage kind="privacy" />} />
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/architect/complete/:token" element={<ArchitectCompletePage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/sandbox/*" element={<Navigate to="/" replace />} />
        <Route path="/client" element={<Guard roles={['CLIENT']}><ClientHome /></Guard>} />
        <Route path="/client/history" element={<Guard roles={['CLIENT']}><HistoryPage /></Guard>} />
        <Route path="/architect" element={<Guard roles={['ARCHITECT']}><ArchitectHome /></Guard>} />
        <Route path="/architect/projects" element={<Guard roles={['ARCHITECT']}><ArchitectProjects /></Guard>} />
        <Route path="/architect/clients" element={<Guard roles={['ARCHITECT']}><ArchitectClients /></Guard>} />
        <Route path="/architect/invitations" element={<Guard roles={['ARCHITECT']}><ArchitectInvitationsPage /></Guard>} />
        <Route path="/architect/history" element={<Guard roles={['ARCHITECT']}><HistoryPage /></Guard>} />
        <Route path="/admin" element={<Guard roles={['ADMIN']}><AdminHome /></Guard>} />
        <Route path="/admin/projects" element={<Guard roles={['ADMIN']}><AdminProjectsPage /></Guard>} />
        <Route path="/admin/clients" element={<Guard roles={['ADMIN']}><StaffClientsPage /></Guard>} />
        <Route path="/admin/architects" element={<Guard roles={['ADMIN']}><StaffArchitectsPage /></Guard>} />
        <Route path="/admin/architects/:userId" element={<Guard roles={['ADMIN']}><ArchitectProfilePage /></Guard>} />
        <Route path="/admin/analytics" element={<Guard roles={['ADMIN']}><AdminAnalyticsPage /></Guard>} />
        <Route path="/admin/history" element={<Guard roles={['ADMIN']}><HistoryPage /></Guard>} />
        <Route path="/projects/:projectId" element={<Guard roles={ALL_ROLES}><ProjectPage /></Guard>} />
        <Route path="/projects/:projectId/activity" element={<Guard roles={ALL_ROLES}><ProjectActivityPage /></Guard>} />
        <Route path="/about" element={<Guard roles={ALL_ROLES}><AboutPage /></Guard>} />
        <Route path="/contact" element={<Guard roles={ALL_ROLES}><ContactPage /></Guard>} />
        <Route path="/" element={<HomeRedirect />} />
      </Routes>
      </UnitsProvider>
    </AuthProvider>
  )
}
