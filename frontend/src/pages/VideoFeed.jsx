import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import VideoUpload from '../components/VideoUpload'
import VideoComments from '../components/VideoComments'
import './VideoFeed.css'

function VideoCard({ video, isActive, index, onToastToggle }) {
  const videoRef = useRef(null)
  const [paused, setPaused] = useState(false)
  const [muted, setMuted] = useState(true)
  const viewedRef = useRef(false)

  useEffect(() => {
    const el = videoRef.current
    if (!el) return

    if (isActive) {
      el.play().catch(() => {})
      setPaused(false)
      // Record view once
      if (!viewedRef.current) {
        api.recordVideoView(video.id).catch(() => {})
        viewedRef.current = true
      }
    } else {
      el.pause()
    }
  }, [isActive, video.id])

  // Cleanup: release video memory on unmount only
  useEffect(() => {
    const el = videoRef.current
    return () => {
      if (el) {
        el.pause()
        el.removeAttribute('src')
        el.load()
      }
    }
  }, [])

  function handleTap() {
    const el = videoRef.current
    if (!el) return
    if (el.paused) {
      el.play().catch(() => {})
      setPaused(false)
    } else {
      el.pause()
      setPaused(true)
    }
  }

  return (
    <div className={`video-card ${paused ? 'video-card--paused' : ''}`} data-index={index}>
      <video
        ref={videoRef}
        src={video.video_url}
        loop
        muted={muted}
        playsInline
        preload={isActive ? 'auto' : 'metadata'}
        poster={video.thumbnail_url || undefined}
      />

      {/* Tap to play/pause */}
      <div className="video-card-tap" onClick={handleTap} />
      <div className="video-play-icon">&#9654;</div>

      {/* Sponsored badge */}
      {video.is_sponsored && video.sponsor_label && (
        <div className="video-sponsored-badge">{video.sponsor_label}</div>
      )}

      {/* Info overlay */}
      <div className="video-info">
        <Link to={`/user/${video.user_id}`} className="video-username">
          @{video.user_id}
        </Link>
        {video.title && <p className="video-caption">{video.title}</p>}
        {video.description && !video.title && (
          <p className="video-caption">{video.description}</p>
        )}
        <div className="video-tags">
          {video.whiskey_name && (
            <Link to={`/whiskey/${video.whiskey_id}`} className="video-tag">
              🥃 {video.whiskey_name}
            </Link>
          )}
          {video.location_name && (
            <span className="video-tag">📍 {video.location_name}</span>
          )}
          {video.price_tag != null && (
            <span className="video-tag video-tag--price">
              ${Number(video.price_tag).toFixed(2)}
            </span>
          )}
        </div>
        {video.view_count > 0 && (
          <span className="video-views">
            {video.view_count.toLocaleString()} view{video.view_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Action buttons */}
      <div className="video-actions">
        <button
          className={`video-action-btn ${video.user_toasted ? 'video-action-btn--toasted' : ''}`}
          onClick={() => onToastToggle(video)}
        >
          <span className="video-action-icon">{video.user_toasted ? '❤️' : '🤍'}</span>
          <span className="video-action-count">{video.toast_count}</span>
        </button>
        <button
          className="video-action-btn"
          onClick={() => window.dispatchEvent(new CustomEvent('open-video-comments', { detail: video.id }))}
        >
          <span className="video-action-icon">💬</span>
          <span className="video-action-count">{video.comment_count}</span>
        </button>
        <button
          className="video-action-btn"
          onClick={() => setMuted(m => !m)}
        >
          <span className="video-action-icon">{muted ? '🔇' : '🔊'}</span>
        </button>
      </div>
    </div>
  )
}

export default function VideoFeed() {
  const navigate = useNavigate()
  const [videos, setVideos] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasMore, setHasMore] = useState(false)
  const [mode, setMode] = useState('foryou') // 'foryou' | 'following'
  const [activeIndex, setActiveIndex] = useState(0)
  const [showUpload, setShowUpload] = useState(false)
  const [commentVideoId, setCommentVideoId] = useState(null)
  const containerRef = useRef(null)
  const observerRef = useRef(null)
  const skipRef = useRef(0)

  const loadVideos = useCallback(async (reset = false) => {
    if (reset) {
      skipRef.current = 0
      setActiveIndex(0)
    }
    setLoading(true)
    try {
      const params = {
        skip: skipRef.current,
        limit: 10,
        following_only: mode === 'following' ? 'true' : '',
      }
      const data = await api.getVideoFeed(params)
      if (reset) {
        setVideos(data.items)
      } else {
        setVideos(prev => [...prev, ...data.items])
      }
      setHasMore(data.has_more)
      skipRef.current += data.items.length
    } catch (err) {
      console.error('Failed to load videos:', err)
    } finally {
      setLoading(false)
    }
  }, [mode])

  useEffect(() => {
    loadVideos(true)
  }, [loadVideos])

  // Keep refs for values the observer callback needs (avoids recreating observer)
  const videosLenRef = useRef(videos.length)
  const hasMoreRef = useRef(hasMore)
  const loadingRef = useRef(loading)
  const loadVideosRef = useRef(loadVideos)
  videosLenRef.current = videos.length
  hasMoreRef.current = hasMore
  loadingRef.current = loading
  loadVideosRef.current = loadVideos

  // IntersectionObserver to detect which card is in view
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const index = Number(entry.target.dataset.index)
            setActiveIndex(index)

            // Load more when near the end
            if (index >= videosLenRef.current - 3 && hasMoreRef.current && !loadingRef.current) {
              loadVideosRef.current()
            }
          }
        }
      },
      { root: container, threshold: 0.6 }
    )

    const cards = container.querySelectorAll('.video-card')
    cards.forEach(card => observerRef.current.observe(card))

    return () => observerRef.current?.disconnect()
  }, [videos.length])

  // Listen for comment panel open events
  useEffect(() => {
    const handler = (e) => setCommentVideoId(e.detail)
    window.addEventListener('open-video-comments', handler)
    return () => window.removeEventListener('open-video-comments', handler)
  }, [])

  async function handleToastToggle(video) {
    try {
      if (video.user_toasted) {
        await api.untoastVideo(video.id)
      } else {
        await api.toastVideo(video.id)
      }
      setVideos(prev =>
        prev.map(v =>
          v.id === video.id
            ? {
                ...v,
                user_toasted: !v.user_toasted,
                toast_count: v.toast_count + (v.user_toasted ? -1 : 1),
              }
            : v
        )
      )
    } catch (err) {
      console.error('Toast failed:', err)
    }
  }

  function handleUploadSuccess() {
    setShowUpload(false)
    loadVideos(true)
  }

  return (
    <>
      <div className="video-feed" ref={containerRef}>
        {/* Top bar */}
        <div className="video-feed-topbar">
          <button className="video-feed-back" onClick={() => navigate(-1)}>
            &#8592;
          </button>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span className="video-feed-title">SipSense</span>
            <div className="video-mode-toggle">
              <button
                className={`video-mode-btn ${mode === 'foryou' ? 'video-mode-btn--active' : ''}`}
                onClick={() => setMode('foryou')}
              >
                For You
              </button>
              <button
                className={`video-mode-btn ${mode === 'following' ? 'video-mode-btn--active' : ''}`}
                onClick={() => setMode('following')}
              >
                Following
              </button>
            </div>
          </div>
          <button className="video-feed-upload-btn" onClick={() => setShowUpload(true)} aria-label="Upload video">
            +
          </button>
        </div>

        {/* Video cards */}
        {loading && videos.length === 0 ? (
          <div className="video-feed-loading">
            <div className="video-feed-spinner" />
          </div>
        ) : !loading && videos.length === 0 ? (
          <div className="video-feed-empty">
            <h2>No videos yet</h2>
            <p>Be the first to share a whiskey moment!</p>
            <button className="video-upload-cta" onClick={() => setShowUpload(true)}>
              Upload a Video
            </button>
          </div>
        ) : (
          videos.map((video, i) => (
              <VideoCard
                key={video.id}
                video={video}
                index={i}
                isActive={i === activeIndex}
                onToastToggle={handleToastToggle}
              />
          ))
        )}

        {loading && videos.length > 0 && (
          <div className="video-feed-loading">
            <div className="video-feed-spinner" />
          </div>
        )}
      </div>

      {/* Upload modal */}
      {showUpload && (
        <VideoUpload
          onClose={() => setShowUpload(false)}
          onSuccess={handleUploadSuccess}
        />
      )}

      {/* Comments panel */}
      {commentVideoId && (
        <VideoComments
          videoId={commentVideoId}
          onClose={() => setCommentVideoId(null)}
          onCommentCountChange={(videoId, delta) => {
            setVideos(prev =>
              prev.map(v =>
                v.id === videoId
                  ? { ...v, comment_count: v.comment_count + delta }
                  : v
              )
            )
          }}
        />
      )}
    </>
  )
}
