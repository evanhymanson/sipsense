import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import CheckInCard from '../components/CheckInCard'
import BadgeGrid from '../components/BadgeGrid'
import './UserProfile.css'

export default function UserProfile() {
  const { username } = useParams()
  const navigate = useNavigate()
  const addToast = useToast()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [following, setFollowing] = useState(false)
  const [followLoading, setFollowLoading] = useState(false)
  const [confirmUnfollow, setConfirmUnfollow] = useState(false)
  const [videos, setVideos] = useState([])
  const [videosLoading, setVideosLoading] = useState(false)
  const [videosError, setVideosError] = useState(false)

  let currentUser = null
  try { currentUser = localStorage.getItem('sipsense_user') } catch {}
  const isSelf = currentUser === username
  const unfollowTimerRef = useRef(null)
  useEffect(() => () => { if (unfollowTimerRef.current) clearTimeout(unfollowTimerRef.current) }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getUserProfile(username)
      .then(p => {
        setProfile(p)
        setFollowing(p.is_following)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

    setVideosLoading(true)
    setVideosError(false)
    api.getUserVideos(username, { limit: 6 })
      .then(r => setVideos(r.items || []))
      .catch(() => setVideosError(true))
      .finally(() => setVideosLoading(false))
  }, [username])

  async function toggleFollow() {
    if (!currentUser) return
    if (following && !confirmUnfollow) {
      setConfirmUnfollow(true)
      if (unfollowTimerRef.current) clearTimeout(unfollowTimerRef.current)
      unfollowTimerRef.current = setTimeout(() => setConfirmUnfollow(false), 3000)
      return
    }
    setFollowLoading(true)
    setConfirmUnfollow(false)
    if (unfollowTimerRef.current) clearTimeout(unfollowTimerRef.current)
    try {
      if (following) {
        await api.unfollowUser(username)
        setFollowing(false)
        setProfile(p => p ? { ...p, follower_count: p.follower_count - 1 } : p)
      } else {
        await api.followUser(username)
        setFollowing(true)
        setProfile(p => p ? { ...p, follower_count: p.follower_count + 1 } : p)
      }
    } catch {
      addToast('Failed to update follow status', 'error')
    } finally {
      setFollowLoading(false)
    }
  }

  if (loading) return <div className="page"><p className="status">Loading profile...</p></div>
  if (error) return (
    <div className="page">
      <p className="status error">{error}</p>
      <div style={{ textAlign: 'center', marginTop: '1rem' }}>
        <button className="retry-btn" onClick={() => window.location.reload()}>Retry</button>
      </div>
    </div>
  )
  if (!profile) return null

  const memberSince = profile.member_since
    ? new Date(profile.member_since).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : null

  return (
    <div className="page profile-page">
      <button className="back-btn" onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: 'var(--amber-light)', cursor: 'pointer', fontFamily: 'inherit', fontSize: '0.9rem', padding: '0.25rem 0', marginBottom: '0.5rem' }}>← Back</button>
      <div className="profile-hero">
        <div className="profile-hero-row">
          <div>
            <h1>{profile.username}</h1>
            {memberSince && <p className="profile-since">Member since {memberSince}</p>}
          </div>
          {!isSelf && currentUser && (
            <button
              className={`profile-follow-btn${following ? ' profile-follow-btn--following' : ''}`}
              onClick={toggleFollow}
              disabled={followLoading}
            >
              {followLoading ? '...' : confirmUnfollow ? 'Tap to confirm' : following ? 'Following' : 'Follow'}
            </button>
          )}
        </div>
      </div>

      <div className="profile-stats">
        <div className="stat-card">
          <span className="stat-value">{profile.total_checkins}</span>
          <span className="stat-label">Check-ins</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.unique_whiskeys}</span>
          <span className="stat-label">Unique</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.follower_count}</span>
          <span className="stat-label">Followers</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.following_count}</span>
          <span className="stat-label">Following</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.avg_score != null ? Number(profile.avg_score).toFixed(1) : '—'}</span>
          <span className="stat-label">Avg Score</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.badges?.length || 0}</span>
          <span className="stat-label">Badges</span>
        </div>
      </div>

      {profile.badges?.length > 0 && (
        <section className="profile-section">
          <h2>Badges</h2>
          <BadgeGrid badges={profile.badges} showDate />
        </section>
      )}

      {profile.top_categories?.length > 0 && (
        <section className="profile-section">
          <h2>Top Categories</h2>
          <div className="profile-categories">
            {profile.top_categories.map(tc => (
              <div key={tc.category} className="profile-cat-bar">
                <span className="profile-cat-name">{tc.category}</span>
                <div className="profile-cat-track">
                  <div
                    className="profile-cat-fill"
                    style={{
                      width: `${profile.total_checkins > 0 ? Math.min(100, (tc.count / profile.total_checkins) * 100) : 0}%`
                    }}
                  />
                </div>
                <span className="profile-cat-count">{tc.count}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {videosError && (
        <section className="profile-section">
          <h2>Videos</h2>
          <p className="page-subtitle">Could not load videos.</p>
        </section>
      )}

      {!videosError && videos.length > 0 && (
        <section className="profile-section">
          <h2>Videos</h2>
          <div className="profile-videos-grid">
            {videos.map(v => (
              <Link key={v.id} to={`/videos?v=${v.id}`} className="profile-video-thumb">
                {v.thumbnail_url ? (
                  <img src={`/api${v.thumbnail_url}`} alt={v.title || 'Video'} />
                ) : (
                  <div className="profile-video-placeholder">▶</div>
                )}
                <span className="profile-video-views">{v.view_count} view{v.view_count !== 1 ? 's' : ''}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {profile.recent_checkins?.length > 0 && (
        <section className="profile-section">
          <h2>Recent Check-ins</h2>
          <div className="profile-checkins">
            {profile.recent_checkins.map(item => (
              <CheckInCard key={item.rating.id} item={item} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
