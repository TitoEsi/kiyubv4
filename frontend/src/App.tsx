import { Navigate, Route, Routes } from 'react-router-dom'
import { ReactElement } from 'react'
import KiyubLogo from './components/KiyubLogo'
import { AuthProvider, useAuth } from './workflow/auth'
import { roleHome } from './workflow/paths'
import LoginPage from './pages/LoginPage'
import LandingPage from './pages/LandingPage'
import LegalPage from './pages/LegalPage'
import ClientHome from './pages/ClientHome'
import ArchitectHome from './pages/ArchitectHome'
import ArchitectProjects from './pages/ArchitectProjects'
import ArchitectClients from './pages/ArchitectClients'
import InvitePage from './pages/InvitePage'
import AdminHome from './pages/AdminHome'
import ITHome from './pages/ITHome'
import ProjectPage from './pages/ProjectPage'
import SandboxGenerate from './pages/SandboxGenerate'
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
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/terms" element={<LegalPage kind="terms" />} />
        <Route path="/privacy" element={<LegalPage kind="privacy" />} />
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/sandbox" element={<SandboxGenerate />} />
        <Route path="/client" element={<Guard roles={['CLIENT']}><ClientHome /></Guard>} />
        <Route path="/architect" element={<Guard roles={['ARCHITECT']}><ArchitectHome /></Guard>} />
        <Route path="/architect/projects" element={<Guard roles={['ARCHITECT']}><ArchitectProjects /></Guard>} />
        <Route path="/architect/clients" element={<Guard roles={['ARCHITECT']}><ArchitectClients /></Guard>} />
        <Route path="/admin" element={<Guard roles={['MAIN_ADMIN']}><AdminHome /></Guard>} />
        <Route path="/it" element={<Guard roles={['IT_PERSONNEL']}><ITHome /></Guard>} />
        <Route path="/projects/:projectId" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><ProjectPage /></Guard>} />
        <Route path="/about" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><AboutPage /></Guard>} />
        <Route path="/contact" element={<Guard roles={['CLIENT', 'ARCHITECT', 'MAIN_ADMIN', 'IT_PERSONNEL']}><ContactPage /></Guard>} />
        <Route path="/" element={<HomeRedirect />} />
      </Routes>
    </AuthProvider>
  )
}
