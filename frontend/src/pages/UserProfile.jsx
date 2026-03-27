import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from '../components/Toast'
import CheckInCard from '../components/CheckInCard'
import BadgeGrid from '../components/BadgeGrid'
import { mediaUrl } from '../utils/media'
import UserLevel from '../components/UserLevel'
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
  const [_videosLoading, setVideosLoading] = useState(false)
  const [videosError, setVideosError] = useState(false)
  const [listModal, setListModal] = useState(null) // 'followers' | 'following' | null
  const [listUsers, setListUsers] = useState([])
  const [listLoading, setListLoading] = useState(false)
  const [palateMatch, setPalateMatch] = useState(null)
  const [reviews, setReviews] = useState([])
  const [reviewsTotal, setReviewsTotal] = useState(0)
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [reviewsHasMore, setReviewsHasMore] = useState(false)
  const [reviewSort, setReviewSort] = useState('recent')
  const [reviewsLoadingMore, setReviewsLoadingMore] = useState(false)
  const REVIEW_PAGE_SIZE = 10

  let currentUser = null
  try { currentUser = localStorage.getItem('sipsense_user') } catch { /* private browsing */ }
  const isSelf = currentUser === username
  const unfollowTimerRef = useRef(null)
  useEffect(() => () => { if (unfollowTimerRef.current) clearTimeout(unfollowTimerRef.current) }, [])

  useEffect(() => {
    let stale = false
    setLoading(true)
    setError(null)
    setListModal(null)

    // Fire all initial requests in parallel (including reviews)
    api.getUserProfile(username)
      .then(p => {
        if (stale) return
        setProfile(p)
        setFollowing(p.is_following)
      })
      .catch(e => { if (!stale) setError(e.message) })
      .finally(() => { if (!stale) setLoading(false) })

    setVideosLoading(true)
    setVideosError(false)
    api.getUserVideos(username, { limit: 6 })
      .then(r => { if (!stale) setVideos(r.items || []) })
      .catch(() => { if (!stale) setVideosError(true) })
      .finally(() => { if (!stale) setVideosLoading(false) })

    setPalateMatch(null)
    if (currentUser && currentUser !== username) {
      api.getPalateMatch(username)
        .then(m => { if (!stale) setPalateMatch(m) })
        .catch(() => {})
    }

    setReviewsLoading(true)
    setReviewSort('recent')
    api.getUserRatings(username, { sort_by: 'recent', skip: 0, limit: REVIEW_PAGE_SIZE })
      .then(data => {
        if (stale) return
        setReviews(data.items || [])
        setReviewsTotal(data.total || 0)
        setReviewsHasMore(data.has_more || false)
      })
      .catch(() => { if (!stale) setReviews([]) })
      .finally(() => { if (!stale) setReviewsLoading(false) })

    return () => { stale = true }
  }, [username, currentUser])

  // Re-fetch reviews on sort change (skip the initial mount — first effect handles it)
  const reviewsInitRef = useRef(true)
  useEffect(() => {
    if (reviewsInitRef.current) { reviewsInitRef.current = false; return }
    let stale = false
    setReviewsLoading(true)
    api.getUserRatings(username, { sort_by: reviewSort, skip: 0, limit: REVIEW_PAGE_SIZE })
      .then(data => {
        if (stale) return
        setReviews(data.items || [])
        setReviewsTotal(data.total || 0)
        setReviewsHasMore(data.has_more || false)
      })
      .catch(() => { if (!stale) setReviews([]) })
      .finally(() => { if (!stale) setReviewsLoading(false) })
    return () => { stale = true }
  }, [username, reviewSort])

  async function loadMoreReviews() {
    setReviewsLoadingMore(true)
    try {
      const data = await api.getUserRatings(username, {
        sort_by: reviewSort,
        skip: reviews.length,
        limit: REVIEW_PAGE_SIZE,
      })
      setReviews(prev => [...prev, ...(data.items || [])])
      setReviewsHasMore(data.has_more || false)
    } catch { /* silent */ }
    finally { setReviewsLoadingMore(false) }
  }

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

  async function openList(type) {
    setListModal(type)
    setListLoading(true)
    try {
      const users = type === 'followers'
        ? await api.getFollowers(username)
        : await api.getFollowing(username)
      setListUsers(users)
    } catch {
      setListUsers([])
    } finally {
      setListLoading(false)
    }
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
            {profile.level && <UserLevel level={profile.level} />}
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
        <div className="stat-card stat-card--clickable" onClick={() => openList('followers')}>
          <span className="stat-value">{profile.follower_count}</span>
          <span className="stat-label">Followers</span>
        </div>
        <div className="stat-card stat-card--clickable" onClick={() => openList('following')}>
          <span className="stat-value">{profile.following_count}</span>
          <span className="stat-label">Following</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.avg_score != null ? Number(profile.avg_score).toFixed(1) : '\u2014'}</span>
          <span className="stat-label">Avg Score</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{profile.badges?.length || 0}</span>
          <span className="stat-label">Badges</span>
        </div>
      </div>

      {/* Reviews — Vivino style */}
      <section className="profile-section profile-reviews-section">
        <div className="profile-reviews-header">
          <h2>Reviews ({reviewsTotal})</h2>
          {reviewsTotal > 0 && (
            <div className="review-sort-bar">
              <label htmlFor="profile-review-sort">Sort by:</label>
              <select
                id="profile-review-sort"
                value={reviewSort}
                onChange={(e) => setReviewSort(e.target.value)}
                className="review-sort-select"
              >
                <option value="recent">Most Recent</option>
                <option value="helpful">Most Helpful</option>
                <option value="highest">Highest Rated</option>
                <option value="lowest">Lowest Rated</option>
              </select>
            </div>
          )}
        </div>

        {reviewsLoading ? (
          <p className="status">Loading reviews...</p>
        ) : reviews.length === 0 ? (
          <p className="profile-reviews-empty">No reviews yet.</p>
        ) : (
          <>
            <div className="profile-checkins">
              {reviews.map(item => (
                <CheckInCard key={item.rating.id} item={item} />
              ))}
            </div>
            {reviewsHasMore && (
              <button
                className="profile-load-more-btn"
                onClick={loadMoreReviews}
                disabled={reviewsLoadingMore}
              >
                {reviewsLoadingMore ? 'Loading...' : 'Load More Reviews'}
              </button>
            )}
          </>
        )}
      </section>

      {palateMatch && palateMatch.match_score != null && (
        <section className="profile-section palate-match-card">
          <h2>Palate Match</h2>
          <div className="palate-match-body">
            <div className="palate-match-score-ring">
              <svg viewBox="0 0 80 80" className="palate-match-svg">
                <circle cx="40" cy="40" r="34" fill="none" stroke="var(--border)" strokeWidth="6" />
                <circle
                  cx="40" cy="40" r="34" fill="none"
                  stroke={palateMatch.match_score >= 70 ? 'var(--amber)' : palateMatch.match_score >= 40 ? 'var(--amber-light)' : 'var(--text-muted)'}
                  strokeWidth="6"
                  strokeDasharray={`${(palateMatch.match_score / 100) * 213.6} 213.6`}
                  strokeLinecap="round"
                  transform="rotate(-90 40 40)"
                />
              </svg>
              <span className="palate-match-pct">{palateMatch.match_score}%</span>
            </div>
            <div className="palate-match-details">
              {palateMatch.message && <p className="palate-match-msg">{palateMatch.message}</p>}
              {palateMatch.shared_flavors?.length > 0 && (
                <div className="palate-match-shared">
                  <span className="palate-match-label">Shared flavors</span>
                  <div className="palate-match-tags">
                    {palateMatch.shared_flavors.map(f => (
                      <span key={f} className="palate-match-tag">{f}</span>
                    ))}
                  </div>
                </div>
              )}
              {palateMatch.agreements?.length > 0 && (
                <div className="palate-match-shared">
                  <span className="palate-match-label">You both love</span>
                  <div className="palate-match-tags">
                    {palateMatch.agreements.map(a => (
                      <span key={a.category} className="palate-match-tag palate-match-tag--agree">{a.category}</span>
                    ))}
                  </div>
                </div>
              )}
              {palateMatch.disagreements?.length > 0 && (
                <div className="palate-match-shared">
                  <span className="palate-match-label">Different tastes</span>
                  <div className="palate-match-tags">
                    {palateMatch.disagreements.map(d => (
                      <span key={d.category} className="palate-match-tag palate-match-tag--diff">{d.category}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

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

      {profile.user_lists?.length > 0 && (
        <section className="profile-section">
          <h2>Lists</h2>
          <div className="prof-lists-grid">
            {profile.user_lists.map(list => (
              <Link key={list.id} to={`/my-lists/${list.slug}`} className="prof-list-card">
                <h4>{list.title}</h4>
                <span className="prof-list-meta">{list.item_count} whiskeys</span>
              </Link>
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
                  <img src={mediaUrl(v.thumbnail_url)} alt={v.title || 'Video'} />
                ) : (
                  <div className="profile-video-placeholder">{'\u25b6'}</div>
                )}
                <span className="profile-video-views">{v.view_count} view{v.view_count !== 1 ? 's' : ''}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {listModal && (
        <div className="follow-modal-overlay" onClick={() => setListModal(null)}>
          <div className="follow-modal" onClick={e => e.stopPropagation()}>
            <div className="follow-modal-header">
              <h3>{listModal === 'followers' ? 'Followers' : 'Following'}</h3>
              <button className="follow-modal-close" onClick={() => setListModal(null)}>&times;</button>
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
