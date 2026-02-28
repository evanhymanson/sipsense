import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import CheckInCard from '../components/CheckInCard'
import BadgeGrid from '../components/BadgeGrid'
import './UserProfile.css'

export default function UserProfile() {
  const { username } = useParams()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    api.getUserProfile(username)
      .then(setProfile)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [username])

  if (loading) return <div className="page"><p className="status">Loading profile...</p></div>
  if (error) return <div className="page"><p className="status error">{error}</p></div>
  if (!profile) return null

  const memberSince = profile.member_since
    ? new Date(profile.member_since).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : null

  return (
    <div className="page profile-page">
      <div className="profile-hero">
        <h1>{profile.username}</h1>
        {memberSince && <p className="profile-since">Member since {memberSince}</p>}
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
          <span className="stat-value">{profile.avg_score ?? '—'}</span>
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
                      width: `${Math.min(100, (tc.count / profile.total_checkins) * 100)}%`
                    }}
                  />
                </div>
                <span className="profile-cat-count">{tc.count}</span>
              </div>
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
