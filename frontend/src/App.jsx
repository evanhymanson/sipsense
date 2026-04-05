import { BrowserRouter, Routes, Route, NavLink, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { useState, useEffect, Component, lazy, Suspense } from 'react'
import { isLoggedIn, getUsername, clearAuth, api } from './api/client'
import { trackPageView, trackEvent, startPageTimer, endPageTimer } from './api/analytics'
import { ToastProvider } from './components/Toast'
import './App.css'

// Lazy-load page components and non-critical UI for code splitting
const Onboarding = lazy(() => import('./pages/Onboarding'))
const ChatSidebar = lazy(() => import('./components/ChatSidebar'))
const InstallPrompt = lazy(() => import('./components/InstallPrompt'))
const PushPermissionBanner = lazy(() => import('./components/PushPermissionBanner'))
const Browse = lazy(() => import('./pages/Browse'))
const WhiskeyDetail = lazy(() => import('./pages/WhiskeyDetail'))
const Discover = lazy(() => import('./pages/Discover'))
const Profile = lazy(() => import('./pages/Profile'))
const Feed = lazy(() => import('./pages/Feed'))
const UserProfile = lazy(() => import('./pages/UserProfile'))
const TasteQuiz = lazy(() => import('./pages/TasteQuiz'))
const ScanBottle = lazy(() => import('./pages/ScanBottle'))
const JourneyDetail = lazy(() => import('./pages/JourneyDetail'))
const Alerts = lazy(() => import('./pages/Alerts'))
const VideoFeed = lazy(() => import('./pages/VideoFeed'))
const Premium = lazy(() => import('./pages/Premium'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const TopLists = lazy(() => import('./pages/TopLists'))
const UserLists = lazy(() => import('./pages/UserLists'))
const Learn = lazy(() => import('./pages/Learn'))
const LearnCategory = lazy(() => import('./pages/LearnCategory'))
const LearnDistillery = lazy(() => import('./pages/LearnDistillery'))
const LearnGlossary = lazy(() => import('./pages/LearnGlossary'))
const Blog = lazy(() => import('./pages/Blog'))
const BlogArticle = lazy(() => import('./pages/BlogArticle'))
const Regions = lazy(() => import('./pages/Regions'))
const RegionDetail = lazy(() => import('./pages/RegionDetail'))
const LearnGrain = lazy(() => import('./pages/LearnGrain'))
const Leaderboard = lazy(() => import('./pages/Leaderboard'))
const Awards = lazy(() => import('./pages/Awards'))
const Marketplace = lazy(() => import('./pages/Marketplace'))
const SubscriptionBox = lazy(() => import('./pages/SubscriptionBox'))

function RequireAuth({ children }) {
  if (!isLoggedIn()) {
    return <Navigate to="/onboarding" replace />
  }
  return children
}

function isChunkLoadError(error) {
  return error?.name === 'ChunkLoadError' ||
    error?.message?.includes('Failed to fetch dynamically imported module') ||
    error?.message?.includes('Importing a module script failed') ||
    error?.message?.includes('Loading chunk') ||
    error?.message?.includes('Loading CSS chunk')
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, errorInfo) {
    // On chunk load failure after a deploy, force a hard reload to get fresh assets
    if (isChunkLoadError(error)) {
      const reloadKey = 'sipsense_chunk_reload'
      if (!sessionStorage.getItem(reloadKey)) {
        sessionStorage.setItem(reloadKey, '1')
        window.location.reload()
        return
      }
      // Already tried once this session — clear flag and show error UI
      sessionStorage.removeItem(reloadKey)
    }
    trackEvent('frontend_error', {
      message: error.message,
      stack: error.stack?.slice(0, 1000),
      component: errorInfo.componentStack?.slice(0, 500),
    })
  }
  componentDidUpdate(prevProps) {
    if (this.state.hasError && prevProps.children !== this.props.children) {
      this.setState({ hasError: false, error: null })
    }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="page" style={{ textAlign: 'center', padding: '4rem 1rem' }}>
          <h1>Something went wrong</h1>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            className="btn-secondary"
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = '/' }}
          >
            Back to Browse
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

const PUBLIC_LINKS = [
  { to: '/',         label: 'Browse',   end: true },
  { to: '/quiz',     label: 'Quiz' },
]

const AUTH_LINKS = [
  { to: '/discover', label: 'Discover' },
  { to: '/feed',     label: 'Feed' },
  { to: '/me',       label: 'My Profile' },
]

function Nav() {
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [unreadAlerts, setUnreadAlerts] = useState(0)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  // Redirect to onboarding on auth expiry (fired from api client)
  useEffect(() => {
    const onExpired = () => navigate('/onboarding', { replace: true })
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [navigate])

  useEffect(() => {
    if (!isLoggedIn()) return
    const fetchAlerts = () => {
      if (!isLoggedIn()) return
      api.getUnreadAlertCount().then(r => setUnreadAlerts(r.count)).catch(() => {})
    }
    fetchAlerts()
    const interval = setInterval(() => {
      // Skip polling when tab is not visible
      if (document.visibilityState === 'visible') fetchAlerts()
    }, 300000)  // 5 minutes
    return () => clearInterval(interval)
  }, [])

  if (location.pathname === '/onboarding' || location.pathname === '/quiz' || location.pathname === '/videos') return null

  const username = getUsername()

  function handleLogout() {
    clearAuth()
    navigate('/onboarding', { replace: true })
  }

  return (
    <nav className="navbar">
      <NavLink to="/" className="nav-logo">Sip <span className="nav-logo-accent">Sense</span></NavLink>

      {/* Hamburger for mobile */}
      <button
        className="nav-hamburger"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
      >
        {menuOpen ? '\u2715' : '\u2630'}
      </button>

      {/* Desktop: primary links */}
      <div className="nav-primary">
        {PUBLIC_LINKS.map(link => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            {link.label}
          </NavLink>
        ))}
        {isLoggedIn() && AUTH_LINKS.map(link => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            {link.label}
          </NavLink>
        ))}
      </div>

      {/* Mobile: full-screen menu */}
      <div className={`nav-mobile-menu ${menuOpen ? 'nav-mobile-menu--open' : ''}`}>
        <div className="nav-mobile-section">
          {PUBLIC_LINKS.map(link => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
          {isLoggedIn() && AUTH_LINKS.map(link => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
          {isLoggedIn() && (
            <NavLink to="/alerts">
              Notifications{unreadAlerts > 0 && ` (${unreadAlerts})`}
            </NavLink>
          )}
        </div>
        <div className="nav-mobile-section nav-mobile-account">
          {isLoggedIn() ? (
            <>
              <span className="nav-mobile-label">Account</span>
              <span className="nav-username">{username}</span>
              <button className="nav-logout" onClick={handleLogout}>Log out</button>
            </>
          ) : (
            <NavLink to="/onboarding" className="nav-login-link">Sign In</NavLink>
          )}
        </div>
      </div>

      {/* Desktop user info */}
      <div className="nav-user nav-user--desktop">
        {isLoggedIn() ? (
          <>
            <button
              className="nav-bell"
              onClick={() => navigate('/alerts')}
              title="Notifications"
            >
              🔔{unreadAlerts > 0 && <span className="nav-bell-badge">{unreadAlerts}</span>}
            </button>
            <span className="nav-username">{username}</span>
            <button className="nav-logout" onClick={handleLogout}>Log out</button>
          </>
        ) : (
          <NavLink to="/onboarding" className="nav-login-link">Sign In</NavLink>
        )}
      </div>
    </nav>
  )
}

function AppShell() {
  const [chatOpen, setChatOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const isOnboarding = location.pathname === '/onboarding' || location.pathname === '/quiz'
  const isFullscreen = location.pathname === '/videos'

  // Track page views and time-on-page
  useEffect(() => {
    trackPageView(location.pathname)
    startPageTimer()
    return () => endPageTimer(location.pathname)
  }, [location.pathname])

  // Handle push notification click → navigate within the app
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    function handleSwMessage(event) {
      if (event.data?.type === 'NAVIGATE') {
        navigate(event.data.url)
      }
    }
    navigator.serviceWorker.addEventListener('message', handleSwMessage)
    return () => navigator.serviceWorker.removeEventListener('message', handleSwMessage)
  }, [navigate])

  return (
    <>
      <Nav />
      <main className="main-content">
        <Suspense fallback={<div className="page" style={{ textAlign: 'center', padding: '4rem' }}>Loading...</div>}>
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/quiz" element={<TasteQuiz />} />
          {/* Public routes */}
          <Route path="/" element={<ErrorBoundary key="browse"><Browse /></ErrorBoundary>} />
          <Route path="/whiskey/:id" element={<ErrorBoundary key="detail"><WhiskeyDetail /></ErrorBoundary>} />
          <Route path="/lists" element={<ErrorBoundary key="toplists"><TopLists /></ErrorBoundary>} />
          <Route path="/lists/:slug" element={<ErrorBoundary key="toplist-detail"><TopLists /></ErrorBoundary>} />
          <Route path="/learn" element={<ErrorBoundary key="learn"><Learn /></ErrorBoundary>} />
          <Route path="/learn/categories/:slug" element={<ErrorBoundary key="learn-cat"><LearnCategory /></ErrorBoundary>} />
          <Route path="/learn/distilleries/:slug" element={<ErrorBoundary key="learn-dist"><LearnDistillery /></ErrorBoundary>} />
          <Route path="/learn/glossary" element={<ErrorBoundary key="learn-gloss"><LearnGlossary /></ErrorBoundary>} />
          <Route path="/learn/grains/:slug" element={<ErrorBoundary key="learn-grain"><LearnGrain /></ErrorBoundary>} />
          <Route path="/regions" element={<ErrorBoundary key="regions"><Regions /></ErrorBoundary>} />
          <Route path="/regions/:slug" element={<ErrorBoundary key="region-detail"><RegionDetail /></ErrorBoundary>} />
          <Route path="/leaderboard" element={<ErrorBoundary key="leaderboard"><Leaderboard /></ErrorBoundary>} />
          <Route path="/awards" element={<ErrorBoundary key="awards"><Awards /></ErrorBoundary>} />
          <Route path="/marketplace" element={<ErrorBoundary key="marketplace"><Marketplace /></ErrorBoundary>} />
          <Route path="/subscription-box" element={<ErrorBoundary key="sub-box"><SubscriptionBox /></ErrorBoundary>} />
          <Route path="/blog" element={<ErrorBoundary key="blog"><Blog /></ErrorBoundary>} />
          <Route path="/blog/:slug" element={<ErrorBoundary key="blog-article"><BlogArticle /></ErrorBoundary>} />
          {/* Auth-required routes */}
          <Route path="/discover" element={<RequireAuth><ErrorBoundary key="discover"><Discover /></ErrorBoundary></RequireAuth>} />
          <Route path="/me" element={<RequireAuth><ErrorBoundary key="profile"><Profile /></ErrorBoundary></RequireAuth>} />
          <Route path="/feed" element={<RequireAuth><ErrorBoundary key="feed"><Feed /></ErrorBoundary></RequireAuth>} />
          <Route path="/scan" element={<RequireAuth><ErrorBoundary key="scan"><ScanBottle /></ErrorBoundary></RequireAuth>} />
          <Route path="/journeys/:slug" element={<RequireAuth><ErrorBoundary key="journey"><JourneyDetail /></ErrorBoundary></RequireAuth>} />
          <Route path="/videos" element={<RequireAuth><ErrorBoundary key="videos"><VideoFeed /></ErrorBoundary></RequireAuth>} />
          <Route path="/premium" element={<RequireAuth><ErrorBoundary key="premium"><Premium /></ErrorBoundary></RequireAuth>} />
          <Route path="/alerts" element={<RequireAuth><ErrorBoundary key="alerts"><Alerts /></ErrorBoundary></RequireAuth>} />
          <Route path="/my-lists" element={<RequireAuth><ErrorBoundary key="userlists"><UserLists /></ErrorBoundary></RequireAuth>} />
          <Route path="/my-lists/:slug" element={<RequireAuth><ErrorBoundary key="userlist-detail"><UserLists /></ErrorBoundary></RequireAuth>} />
          <Route path="/user/:username" element={<RequireAuth><ErrorBoundary key="userprofile"><UserProfile /></ErrorBoundary></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth><ErrorBoundary key="admin"><AdminDashboard /></ErrorBoundary></RequireAuth>} />
          <Route path="*" element={
            <div className="page">
              <h1>Page Not Found</h1>
              <p className="page-subtitle">
                The page you're looking for doesn't exist.{' '}
                <NavLink to="/" style={{ color: 'var(--amber)' }}>Browse whiskeys</NavLink>
              </p>
            </div>
          } />
        </Routes>
        </Suspense>
      </main>

      {/* Chat sidebar — always mounted so state persists across navigation */}
      {!isOnboarding && !isFullscreen && (
        <>
          <ChatSidebar isOpen={chatOpen} onClose={() => setChatOpen(false)} />
          <button
            className={`chat-fab ${chatOpen ? 'chat-fab--hidden' : ''}`}
            onClick={() => setChatOpen(true)}
          >
            🥃 Ask Sip Sense
          </button>
        </>
      )}
    </>
  )
}

export default function App() {
  return (
    <HelmetProvider>
      <BrowserRouter>
        <ToastProvider>
          <AppShell />
          <InstallPrompt />
          <PushPermissionBanner />
        </ToastProvider>
      </BrowserRouter>
    </HelmetProvider>
  )
}
