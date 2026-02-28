import { BrowserRouter, Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Browse from './pages/Browse'
import WhiskeyDetail from './pages/WhiskeyDetail'
import Recommendations from './pages/Recommendations'
import Quiz from './pages/Quiz'
import Favorites from './pages/Favorites'
import FlavorWheel from './pages/FlavorWheel'
import Learn from './pages/Learn'
import ValuePicks from './pages/ValuePicks'
import FlightBuilder from './pages/FlightBuilder'
import GiftFinder from './pages/GiftFinder'
import MyPalate from './pages/MyPalate'
import Compare from './pages/Compare'
import Stores from './pages/Stores'
import Trending from './pages/Trending'
import Collection from './pages/Collection'
import Personality from './pages/Personality'
import BlindTasting from './pages/BlindTasting'
import DailyDiscovery from './pages/DailyDiscovery'
import Feed from './pages/Feed'
import UserProfile from './pages/UserProfile'
import Onboarding from './pages/Onboarding'
import ChatSidebar from './components/ChatSidebar'
import { isLoggedIn, getUsername, clearAuth } from './api/client'
import './App.css'

function RequireAuth({ children }) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!isLoggedIn()) {
      navigate('/onboarding', { replace: true })
    }
  }, [navigate])
  return isLoggedIn() ? children : null
}

// Primary links always visible in the top bar
const PRIMARY_LINKS = [
  { to: '/', label: 'Browse', end: true },
  { to: '/recommendations', label: 'For You' },
  { to: '/feed', label: 'Feed' },
  { to: '/quiz', label: 'Taste Quiz' },
  { to: '/learn', label: 'Learn' },
]

// Everything else goes in the "More" dropdown, organized by group
const MORE_GROUPS = [
  {
    label: 'Discover',
    links: [
      { to: '/trending', label: 'Trending' },
      { to: '/daily', label: 'Daily Discovery' },
      { to: '/flavor-wheel', label: 'Flavor Wheel' },
      { to: '/blind-tasting', label: 'Blind Tasting' },
    ],
  },
  {
    label: 'Personal',
    links: [
      { to: '/favorites', label: 'Favorites' },
      { to: '/collection', label: 'My Shelf' },
      { to: '/my-palate', label: 'My Palate' },
      { to: '/personality', label: 'Personality' },
    ],
  },
  {
    label: 'Tools',
    links: [
      { to: '/compare', label: 'Compare' },
      { to: '/flight-builder', label: 'Flights' },
      { to: '/gift-finder', label: 'Gift Finder' },
      { to: '/value-picks', label: 'Value Picks' },
      { to: '/stores', label: 'Stores' },
    ],
  },
]

function Nav() {
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  if (location.pathname === '/onboarding') return null

  const username = getUsername()

  // Close "More" dropdown when route changes
  useEffect(() => {
    setMoreOpen(false)
    setMenuOpen(false)
  }, [location.pathname])

  function handleLogout() {
    clearAuth()
    navigate('/onboarding', { replace: true })
  }

  // Check if any "More" link is active
  const moreActive = MORE_GROUPS.some(g =>
    g.links.some(l => location.pathname === l.to)
  )

  return (
    <nav className="navbar">
      <NavLink to="/" className="nav-logo">SipSense</NavLink>

      {/* Hamburger for mobile */}
      <button
        className="nav-hamburger"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
      >
        {menuOpen ? '\u2715' : '\u2630'}
      </button>

      {/* Desktop: primary links + More dropdown */}
      <div className="nav-primary">
        {PRIMARY_LINKS.map(link => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            {link.label}
          </NavLink>
        ))}
        <div className="nav-more-wrapper">
          <button
            className={`nav-more-btn ${moreActive ? 'active' : ''}`}
            onClick={() => setMoreOpen(!moreOpen)}
          >
            More {moreOpen ? '\u25B4' : '\u25BE'}
          </button>
          {moreOpen && (
            <>
              <div className="nav-more-backdrop" onClick={() => setMoreOpen(false)} />
              <div className="nav-more-dropdown">
                {MORE_GROUPS.map(group => (
                  <div key={group.label} className="nav-more-group">
                    <span className="nav-more-group-label">{group.label}</span>
                    {group.links.map(link => (
                      <NavLink key={link.to} to={link.to}>
                        {link.label}
                      </NavLink>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Mobile: full-screen menu */}
      <div className={`nav-mobile-menu ${menuOpen ? 'nav-mobile-menu--open' : ''}`}>
        <div className="nav-mobile-section">
          {PRIMARY_LINKS.map(link => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
        </div>
        {MORE_GROUPS.map(group => (
          <div key={group.label} className="nav-mobile-section">
            <span className="nav-mobile-label">{group.label}</span>
            {group.links.map(link => (
              <NavLink key={link.to} to={link.to}>
                {link.label}
              </NavLink>
            ))}
          </div>
        ))}
        <div className="nav-mobile-section nav-mobile-account">
          <span className="nav-mobile-label">Account</span>
          <span className="nav-username">{username}</span>
          <button className="nav-logout" onClick={handleLogout}>Log out</button>
        </div>
      </div>

      {/* Desktop user info */}
      <div className="nav-user nav-user--desktop">
        <span className="nav-username">{username}</span>
        <button className="nav-logout" onClick={handleLogout}>Log out</button>
      </div>
    </nav>
  )
}

function AppShell() {
  const [chatOpen, setChatOpen] = useState(false)
  const location = useLocation()
  const isOnboarding = location.pathname === '/onboarding'

  return (
    <>
      <Nav />
      <main className="main-content">
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/" element={<RequireAuth><Browse /></RequireAuth>} />
          <Route path="/whiskey/:id" element={<RequireAuth><WhiskeyDetail /></RequireAuth>} />
          <Route path="/flavor-wheel" element={<RequireAuth><FlavorWheel /></RequireAuth>} />
          <Route path="/quiz" element={<RequireAuth><Quiz /></RequireAuth>} />
          <Route path="/recommendations" element={<RequireAuth><Recommendations /></RequireAuth>} />
          <Route path="/favorites" element={<RequireAuth><Favorites /></RequireAuth>} />
          <Route path="/value-picks" element={<RequireAuth><ValuePicks /></RequireAuth>} />
          <Route path="/learn" element={<RequireAuth><Learn /></RequireAuth>} />
          <Route path="/flight-builder" element={<RequireAuth><FlightBuilder /></RequireAuth>} />
          <Route path="/gift-finder" element={<RequireAuth><GiftFinder /></RequireAuth>} />
          <Route path="/my-palate" element={<RequireAuth><MyPalate /></RequireAuth>} />
          <Route path="/compare" element={<RequireAuth><Compare /></RequireAuth>} />
          <Route path="/stores" element={<RequireAuth><Stores /></RequireAuth>} />
          <Route path="/trending" element={<RequireAuth><Trending /></RequireAuth>} />
          <Route path="/collection" element={<RequireAuth><Collection /></RequireAuth>} />
          <Route path="/personality" element={<RequireAuth><Personality /></RequireAuth>} />
          <Route path="/blind-tasting" element={<RequireAuth><BlindTasting /></RequireAuth>} />
          <Route path="/daily" element={<RequireAuth><DailyDiscovery /></RequireAuth>} />
          <Route path="/feed" element={<RequireAuth><Feed /></RequireAuth>} />
          <Route path="/user/:username" element={<RequireAuth><UserProfile /></RequireAuth>} />
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
      </main>

      {/* Chat sidebar — always mounted so state persists across navigation */}
      {!isOnboarding && (
        <>
          <ChatSidebar isOpen={chatOpen} onClose={() => setChatOpen(false)} />
          <button
            className={`chat-fab ${chatOpen ? 'chat-fab--hidden' : ''}`}
            onClick={() => setChatOpen(true)}
          >
            🥃 Ask SipSense
          </button>
        </>
      )}
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
