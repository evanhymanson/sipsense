import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { api, getUsername } from '../api/client'
import { useToast } from '../components/Toast'
import BadgeGrid from '../components/BadgeGrid'
import WhiskeyCard from '../components/WhiskeyCard'
import UserLevel from '../components/UserLevel'
import CollectionTab from '../components/CollectionTab'
import JournalTab from '../components/JournalTab'
import './Profile.css'
import './UserProfile.css'

const TABS = [
  { id: 'palate',     label: 'Palate',     emoji: '\u{1F445}' },
  { id: 'foryou',     label: 'For You',    emoji: '\u2728' },
  { id: 'collection', label: 'Collection', emoji: '\u{1F37E}' },
  { id: 'journal',    label: 'Journal',    emoji: '\u{1F4DD}' },
]

// Map old tab IDs to new ones for backward compat
const TAB_REDIRECTS = { favorites: 'foryou', badges: 'palate' }

// ── Shared sub-components ───────────────────────────────────────────────────

function BarRow({ label, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="prof-bar-row">
      <span className="prof-bar-label">{label}</span>
      <div className="prof-bar-track"><div className="prof-bar-fill" style={{ width: `${pct}%` }} /></div>
      <span className="prof-bar-count">{count}</span>
    </div>
  )
}

// ── Palate Tab ──────────────────────────────────────────────────────────────

function PalateTab({ palateData, personality }) {
  const [aiSummary, setAiSummary] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [evolution, setEvolution] = useState(null)
  const [percentiles, setPercentiles] = useState(null)

  useEffect(() => {
    api.getPalateEvolution().then(setEvolution).catch(() => {})
    api.getPalatePercentiles().then(setPercentiles).catch(() => {})
  }, [])

  if (!palateData) return <p className="prof-empty">Rate some whiskeys to start building your taste portrait.</p>

  const { narrative, stats, top_categories = [], top_flavors = [] , recent_ratings = [] } = palateData
  const badges = palateData.badges || []
  const maxCat = top_categories[0]?.count || 1
  const maxFlavor = top_flavors[0]?.count || 1
  const isNewcomer = personality?.type === 'curious_newcomer'

  async function loadAiSummary() {
    setAiLoading(true)
    try { setAiSummary((await api.getAiPalateSummary()).narrative?.replace(/\*+/g, '')) }
    catch { setAiSummary(null) }
    finally { setAiLoading(false) }
  }

  if (stats.total_rated === 0 && stats.total_favorites === 0) {
    return (
      <div className="prof-empty-state">
        <div className="prof-empty-icon">🥃</div>
        <h2>Your palate profile is empty</h2>
        <p>Rate some whiskeys in Browse to start building your taste portrait.</p>
      </div>
    )
  }

  return (
    <div className="prof-palate">
      {/* ── Flavor DNA + Go-To Styles (moved from hero) ── */}
      {!isNewcomer && personality?.top_flavors?.length > 0 && (
        <div className="prof-dna">
          <div className="prof-dna-section">
            <span className="prof-dna-label">Flavor DNA</span>
            <div className="prof-dna-tags">
              {personality.top_flavors.map(f => <span key={f} className="prof-dna-tag">{f}</span>)}
            </div>
          </div>
          {personality.top_categories?.length > 0 && (
            <div className="prof-dna-section">
              <span className="prof-dna-label">Go-To Styles</span>
              <div className="prof-dna-tags">
                {personality.top_categories.map(c => <span key={c} className="prof-dna-tag prof-dna-tag--cat">{c}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="prof-narrative">
        <p>{aiSummary || narrative}</p>
        {!aiSummary && !aiLoading && (
          <button className="prof-ai-btn" onClick={loadAiSummary}>Generate AI Portrait</button>
        )}
        {aiLoading && <p className="prof-ai-loading">Writing your taste portrait...</p>}
        <button
          className="prof-share-dna-btn"
          onClick={async () => {
            try {
              const url = api.getPalateDnaCardUrl(getUsername())
              const res = await fetch(url)
              const blob = await res.blob()
              const file = new File([blob], 'sipsense-whiskey-dna.png', { type: 'image/png' })
              if (navigator.share && navigator.canShare?.({ files: [file] })) {
                await navigator.share({ title: 'My Whiskey DNA on SipSense', files: [file] })
              } else {
                const a = document.createElement('a')
                a.href = URL.createObjectURL(blob)
                a.download = 'sipsense-whiskey-dna.png'
                a.click()
                URL.revokeObjectURL(a.href)
              }
            } catch { /* silently fail */ }
          }}
        >
          Share My Whiskey DNA
        </button>
      </div>

      {top_categories.length > 0 && (
        <div className="prof-section">
          <h3>Styles You Reach For</h3>
          <div className="prof-bars">{top_categories.map(c => <BarRow key={c.name} label={c.name} count={c.count} max={maxCat} />)}</div>
        </div>
      )}

      {top_flavors.length > 0 && (
        <div className="prof-section">
          <h3>Flavor Fingerprint</h3>
          <div className="prof-flavor-cloud">
            {top_flavors.map((f, i) => (
              <span key={f.name} className="prof-cloud-tag" style={{ fontSize: `${1.1 - i * 0.07}rem`, opacity: 1 - i * 0.06 }}>
                {f.name}
              </span>
            ))}
          </div>
          <div className="prof-bars">{top_flavors.slice(0, 6).map(f => <BarRow key={f.name} label={f.name} count={f.count} max={maxFlavor} />)}</div>
        </div>
      )}

      {/* ── Palate Evolution ─────────────────────────────────────── */}
      {evolution?.evolution_narrative && (
        <div className="prof-section">
          <h3>Your Palate Evolution</h3>
          <div className="prof-evolution-card">
            <p className="prof-evolution-narrative">{evolution.evolution_narrative}</p>
            {evolution.comparison && (
              <div className="prof-evolution-stats">
                {evolution.comparison.score_trend !== 0 && (
                  <span className="prof-evo-stat">
                    {evolution.comparison.score_trend > 0 ? '↑' : '↓'} Avg score {evolution.comparison.score_trend > 0 ? 'up' : 'down'} {Math.abs(evolution.comparison.score_trend).toFixed(1)}
                  </span>
                )}
                {evolution.comparison.new_categories?.length > 0 && (
                  <span className="prof-evo-stat">
                    + {evolution.comparison.new_categories.join(', ')}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Percentile Badges ────────────────────────────────────── */}
      {percentiles && (
        <div className="prof-section">
          <h3>How You Compare</h3>
          <div className="prof-percentile-grid">
            {percentiles.total_rated_percentile != null && (
              <div className="prof-percentile-badge">
                <div className="prof-pct-bar-track">
                  <div className="prof-pct-bar-fill" style={{ width: `${percentiles.total_rated_percentile}%` }} />
                </div>
                <span className="prof-pct-label">More bottles rated than {percentiles.total_rated_percentile}% of users</span>
              </div>
            )}
            {percentiles.top_category_percentile != null && percentiles.top_category && (
              <div className="prof-percentile-badge">
                <div className="prof-pct-bar-track">
                  <div className="prof-pct-bar-fill" style={{ width: `${percentiles.top_category_percentile}%` }} />
                </div>
                <span className="prof-pct-label">Top {100 - percentiles.top_category_percentile}% {percentiles.top_category} enthusiast</span>
              </div>
            )}
            {percentiles.diversity_score != null && (
              <div className="prof-percentile-badge">
                <div className="prof-pct-bar-track">
                  <div className="prof-pct-bar-fill" style={{ width: `${percentiles.diversity_score * 10}%` }} />
                </div>
                <span className="prof-pct-label">Diversity: {percentiles.diversity_score.toFixed(1)} / 10</span>
              </div>
            )}
          </div>
        </div>
      )}

      {recent_ratings.length > 0 && (
        <div className="prof-section">
          <h3>Recent Ratings</h3>
          <div className="prof-ratings">
            {recent_ratings.map((r) => (
              <div key={r.whiskey.id} className="prof-rating-row">
                <div className="prof-rating-info">
                  <span className="prof-rating-name">{r.whiskey.name}</span>
                  <span className="prof-rating-dist">{r.whiskey.distillery} · {r.whiskey.category}</span>
                </div>
                <div className="prof-rating-right">
                  <span className="prof-rating-score">{r.score.toFixed(1)}</span>
                  <span className="prof-rating-stars">{'★'.repeat(Math.min(5, Math.max(0, Math.round(r.score || 0))))}{'☆'.repeat(Math.max(0, 5 - Math.min(5, Math.round(r.score || 0))))}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Badges (merged from standalone tab) ────────────────── */}
      {badges.length > 0 && (
        <div className="prof-section">
          <h3>Badges</h3>
          <BadgeGrid badges={badges} showDate />
        </div>
      )}
    </div>
  )
}

// ── For You Tab (now includes Favorites) ────────────────────────────────────

function ForYouTab() {
  const [recs, setRecs] = useState([])
  const [favs, setFavs] = useState([])
  const [loading, setLoading] = useState(true)
  const [favsLoading, setFavsLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.getExplainedRecommendations(12)
      .then(setRecs)
      .catch(() =>
        api.getRecommendations(12)
          .then(data => setRecs(data.map(r => ({ ...r, reason: null }))))
          .catch(() => setRecs([]))
      )
      .finally(() => setLoading(false))

    api.getFavorites()
      .then(setFavs)
      .catch(() => setFavs([]))
      .finally(() => setFavsLoading(false))
  }, [])

  if (loading) return <p className="prof-loading">Finding your next bottles...</p>

  if (recs.length === 0 && favs.length === 0 && !favsLoading) {
    return (
      <div className="prof-empty-state">
        <div className="prof-empty-icon">✦</div>
        <h2>No recommendations yet</h2>
        <p>Rate a few whiskeys and we'll suggest bottles tailored to your taste.</p>
        <button className="prof-cta-btn" onClick={() => navigate('/')}>Browse Whiskeys</button>
      </div>
    )
  }

  return (
    <div className="prof-foryou">
      {recs.length > 0 && (
        <>
          <p className="prof-foryou-subtitle">Picked for your palate</p>
          <div className="prof-foryou-grid">
            {recs.map(({ whiskey, score, reason }) => (
              <div key={whiskey.id} className="prof-foryou-item">
                <WhiskeyCard whiskey={whiskey} score={score} />
                {reason && <div className="prof-foryou-reason">{reason}</div>}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Saved Favorites ── */}
      {!favsLoading && favs.length > 0 && (
        <div className="prof-section" style={recs.length > 0 ? { marginTop: '1.5rem' } : undefined}>
          <h3>Saved ({favs.length})</h3>
          <div className="prof-foryou-grid">
            {favs.map(w => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Profile Page ───────────────────────────────────────────────────────

export default function Profile() {
  const navigate = useNavigate()
  const addToast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [currentUser] = useState(() => {
    try { return localStorage.getItem('sipsense_user') } catch { return null }
  })

  // Resolve tab from URL with backward compat
  const rawTab = searchParams.get('tab')
  const resolvedTab = TAB_REDIRECTS[rawTab] || rawTab
  const [activeTab, setActiveTabRaw] = useState(
    TABS.some(t => t.id === resolvedTab) ? resolvedTab : 'palate'
  )
  const [visitedTabs, setVisitedTabs] = useState(() => new Set([
    TABS.some(t => t.id === resolvedTab) ? resolvedTab : 'palate'
  ]))
  const setActiveTab = useCallback((id) => {
    setActiveTabRaw(id)
    setVisitedTabs(prev => prev.has(id) ? prev : new Set([...prev, id]))
    setSearchParams({ tab: id }, { replace: true })
  }, [setSearchParams])
  const [personality, setPersonality] = useState(null)
  const [palateData, setPalateData] = useState(null)
  const [tabCounts, setTabCounts] = useState({})
  const [heroLoading, setHeroLoading] = useState(true)
  const [initialColStats, setInitialColStats] = useState(null)
  const [initialJournal, setInitialJournal] = useState(null)
  const [followerCount, setFollowerCount] = useState(0)
  const [followingCount, setFollowingCount] = useState(0)
  const [listModal, setListModal] = useState(null)
  const [listUsers, setListUsers] = useState([])
  const [listLoading, setListLoading] = useState(false)
  const [profileData, setProfileData] = useState(null)
  const [showPrefs, setShowPrefs] = useState(false)
  const [emailPrefs, setEmailPrefs] = useState(null)
  const [emailPrefsSaving, setEmailPrefsSaving] = useState(false)

  useEffect(() => {
    api.getEmailPreferences()
      .then(setEmailPrefs)
      .catch(() => {})
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const opts = { signal: controller.signal }

    // Tier 1: hero data — unblocks first paint
    Promise.all([
      api.getPersonality(opts).catch(() => null),
      currentUser ? api.getUserProfile(currentUser, opts).catch(() => null) : Promise.resolve(null),
    ]).then(([pers, profile]) => {
      if (controller.signal.aborted) return
      setPersonality(pers)
      if (profile) {
        setProfileData(profile)
        setFollowerCount(profile.follower_count || 0)
        setFollowingCount(profile.following_count || 0)
      }
    }).finally(() => {
      if (!controller.signal.aborted) setHeroLoading(false)
    })

    // Tier 2: tab data — populates tabs after hero is visible
    Promise.all([
      api.getPalate(opts).catch(() => null),
      api.getCollectionStats(opts).catch(() => null),
      api.getJournal(opts).catch(() => null),
    ]).then(([pal, colStats, journal]) => {
      if (controller.signal.aborted) return
      setPalateData(pal)
      setInitialColStats(colStats)
      setInitialJournal(journal)
      setTabCounts({
        collection: colStats?.total ?? 0,
        journal: Array.isArray(journal?.entries) ? journal.entries.length : (journal?.total ?? 0),
      })
    })

    return () => controller.abort()
  }, [currentUser])

  async function openList(type) {
    setListModal(type)
    setListLoading(true)
    try {
      const users = type === 'followers'
        ? await api.getFollowers(currentUser)
        : await api.getFollowing(currentUser)
      setListUsers(users)
    } catch { setListUsers([]) }
    finally { setListLoading(false) }
  }

  async function toggleListFollow(target) {
    const user = listUsers.find(u => u.username === target)
    if (!user) return
    try {
      if (user.is_following) {
        await api.unfollowUser(target)
      } else {
        await api.followUser(target)
      }
      setListUsers(prev => prev.map(u =>
        u.username === target ? { ...u, is_following: !u.is_following } : u
      ))
    } catch {
      addToast('Failed to update follow', 'error')
    }
  }

  if (heroLoading) {
    return (
      <div className="profile-page">
        <div className="prof-loading-state">
          <span className="prof-loading-icon">🥃</span>
          <p>Loading your profile...</p>
        </div>
      </div>
    )
  }

  const stats = palateData?.stats
  const isNewcomer = personality?.type === 'curious_newcomer'

  return (
    <div className="profile-page">
      {/* ── Hero: Personality Card ───────────────────────────── */}
      <div className="prof-hero">
        <div className="prof-hero-top">
          {personality && (
            <div className="prof-personality">
              <span className="prof-personality-emoji">{personality.emoji}</span>
              <div className="prof-personality-info">
                <h1>{personality.title}</h1>
                <p className="prof-personality-tagline">{personality.tagline}</p>
                {personality.spirit_bottle && (
                  <span className="prof-spirit">Spirit bottle: {personality.spirit_bottle}</span>
                )}
              </div>
            </div>
          )}
          <button
            className="prof-gear-btn"
            onClick={() => setShowPrefs(!showPrefs)}
            title="Notification preferences"
            aria-label="Notification preferences"
          >
            ⚙
          </button>
        </div>

        {profileData?.level && (
          <UserLevel level={profileData.level} showProgress />
        )}

        {/* Stats row */}
        <div className="prof-stats">
          <div className="prof-stat"><span className="prof-stat-val">{stats ? stats.total_rated : profileData?.total_checkins ?? '–'}</span><span>Rated</span></div>
          <div className="prof-stat"><span className="prof-stat-val">{stats?.total_favorites ?? '–'}</span><span>Favorites</span></div>
          <div className="prof-stat prof-stat--clickable" onClick={() => openList('followers')}>
            <span className="prof-stat-val">{followerCount}</span><span>Followers</span>
          </div>
          <div className="prof-stat prof-stat--clickable" onClick={() => openList('following')}>
            <span className="prof-stat-val">{followingCount}</span><span>Following</span>
          </div>
        </div>

        {isNewcomer && (
          <div className="prof-cta">
            <p>Rate a few whiskeys and your personality will emerge!</p>
            <button onClick={() => navigate('/discover')}>Start Exploring</button>
          </div>
        )}

        {/* ── Notification Preferences (collapsible) ── */}
        {showPrefs && emailPrefs && (
          <div className="prof-prefs-panel">
            <h3>Email Preferences</h3>
            <div className="prof-email-prefs">
              {[
                { key: 'weekly_digest', label: 'Weekly Digest' },
                { key: 're_engagement', label: 'Re-engagement Tips' },
                { key: 'onboarding_drip', label: 'Onboarding Emails' },
                { key: 'marketing', label: 'Marketing & News' },
              ].map(({ key, label }) => (
                <div key={key} className="prof-email-toggle">
                  <span className="prof-email-label">{label}</span>
                  <input
                    type="checkbox"
                    checked={emailPrefs[key] ?? true}
                    disabled={emailPrefsSaving}
                    onChange={async (e) => {
                      const updated = { ...emailPrefs, [key]: e.target.checked }
                      setEmailPrefs(updated)
                      setEmailPrefsSaving(true)
                      try { await api.updateEmailPreferences(updated) }
                      catch { setEmailPrefs(emailPrefs) }
                      finally { setEmailPrefsSaving(false) }
                    }}
                  />
                </div>
              ))}
            </div>
            <h3 style={{ marginTop: '1.2rem' }}>Push Notifications</h3>
            <div className="prof-email-prefs">
              {[
                { key: 'push_social', label: 'Follows & Comments' },
                { key: 'push_price_drop', label: 'Price Drop Alerts' },
                { key: 'push_streak', label: 'Streak Reminders' },
                { key: 'push_weekly', label: 'Weekly Highlights' },
              ].map(({ key, label }) => (
                <div key={key} className="prof-email-toggle">
                  <span className="prof-email-label">{label}</span>
                  <input
                    type="checkbox"
                    checked={emailPrefs[key] ?? true}
                    disabled={emailPrefsSaving}
                    onChange={async (e) => {
                      const updated = { ...emailPrefs, [key]: e.target.checked }
                      setEmailPrefs(updated)
                      setEmailPrefsSaving(true)
                      try { await api.updateEmailPreferences(updated) }
                      catch { setEmailPrefs(emailPrefs) }
                      finally { setEmailPrefsSaving(false) }
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Tabs ─────────────────────────────────────────────── */}
      <div className="prof-tabs-wrapper">
        <div className="prof-tabs" role="tablist" aria-label="Profile sections">
          {TABS.map(tab => {
            const count = tabCounts[tab.id]
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`prof-tab${activeTab === tab.id ? ' prof-tab--active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span className="prof-tab-emoji">{tab.emoji}</span>
                {tab.label}
                {count > 0 && <span className="prof-tab-count">{count}</span>}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Tab Content ──────────────────────────────────────── */}
      <div className="prof-tab-content" role="tabpanel">
        {visitedTabs.has('palate') && <div style={{ display: activeTab === 'palate' ? undefined : 'none' }}><PalateTab palateData={palateData} personality={personality} /></div>}
        {visitedTabs.has('foryou') && <div style={{ display: activeTab === 'foryou' ? undefined : 'none' }}><ForYouTab /></div>}
        {visitedTabs.has('collection') && <div style={{ display: activeTab === 'collection' ? undefined : 'none' }}><CollectionTab initialStats={initialColStats} /></div>}
        {visitedTabs.has('journal') && <div style={{ display: activeTab === 'journal' ? undefined : 'none' }}><JournalTab initialEntries={initialJournal?.entries} /></div>}
      </div>

      {/* ── Followers / Following Modal ──────────────────────── */}
      {listModal && (
        <div className="follow-modal-overlay" onClick={() => setListModal(null)}>
          <div className="follow-modal" onClick={e => e.stopPropagation()}>
            <div className="follow-modal-header">
              <h3>{listModal === 'followers' ? 'Followers' : 'Following'}</h3>
              <button className="follow-modal-close" onClick={() => setListModal(null)}>✕</button>
            </div>
            <div className="follow-modal-body">
              {listLoading ? (
                <p className="status">Loading...</p>
              ) : listUsers.length === 0 ? (
                <p className="status">{listModal === 'followers' ? 'No followers yet' : 'Not following anyone yet'}</p>
              ) : (
                listUsers.map(u => (
                  <div key={u.username} className="follow-modal-row">
                    <Link to={`/user/${u.username}`} className="follow-modal-username" onClick={() => setListModal(null)}>
                      {u.username}
                    </Link>
                    <span className="follow-modal-meta">{u.total_checkins} check-in{u.total_checkins !== 1 ? 's' : ''}</span>
                    {currentUser && u.username !== currentUser && (
                      <button
                        className={`follow-modal-btn${u.is_following ? ' follow-modal-btn--following' : ''}`}
                        onClick={() => toggleListFollow(u.username)}
                      >
                        {u.is_following ? 'Following' : 'Follow'}
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
