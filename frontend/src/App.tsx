import { Navigate, Route, Routes } from 'react-router-dom'
import { ReactElement } from 'react'
import KiyubLogo from './components/KiyubLogo'
import { AuthProvider, useAuth } from './workflow/auth'
import { UnitsProvider } from './units/UnitsProvider'
import { roleHome } from './workflow/paths'
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
import ITAnalyticsPage from './pages/ITAnalyticsPage'
import ITHome from './pages/ITHome'
import ProjectPage from './pages/ProjectPage'
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

function Guard({ roles, children }: { roles: string[]; children: ReactElement }) {
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
        <Route path="/admin" element={<Guard roles={['MAIN_ADMIN']}><AdminHome /></Guard>} />
        <Route path="/admin/projects" element={<Guard roles={['MAIN_ADMIN']}><AdminProjectsPage /></Guard>} />
        <Route path="/admin/clients" element={<Guard roles={['MAIN_ADMIN']}><StaffClientsPage /></Guard>} />
        <Route path="/admin/architects" element={<Guard roles={['MAIN_ADMIN']}><StaffArchitectsPage /></Guard>} />
        <Route path="/admin/architects/:userId" element={<Guard roles={['MAIN_ADMIN']}><ArchitectProfilePage /></Guard>} />
        <Route path="/admin/history" element={<Guard roles={['MAIN_ADMIN']}><HistoryPage /></Guard>} />
        <Route path="/it" element={<Guard roles={['IT_PERSONNEL']}><ITHome /></Guard>} />
        <Route path="/it/clients" element={<Guard roles={['IT_PERSONNEL']}><StaffClientsPage /></Guard>} />
        <Route path="/it/architects" element={<Guard roles={['IT_PERSONNEL']}><StaffArchitectsPage /></Guard>} />
        <Route path="/it/architects/:userId" element={<Guard roles={['IT_PERSONNEL']}><ArchitectProfilePage /></Guard>} />
        <Route path="/it/analytics" element={<Guard roles={['IT_PERSONNEL']}><ITAnalyticsPage /></Guard>} />
        <Route path="/it/history" element={<Guard roles={['IT_PERSONNEL']}><HistoryPage /></Guard>} />
        <Route path="/projects/:projectId" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><ProjectPage /></Guard>} />
        <Route path="/about" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><AboutPage /></Guard>} />
        <Route path="/contact" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><ContactPage /></Guard>} />
        <Route path="/" element={<HomeRedirect />} />
      </Routes>
      </UnitsProvider>
    </AuthProvider>
  )
}
