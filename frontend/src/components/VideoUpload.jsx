import { useState, useRef, useEffect } from 'react'
import { api } from '../api/client'

const MAX_SIZE = 100 * 1024 * 1024 // 100 MB

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0, 0, 0, 0.85)',
    zIndex: 30,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem',
  },
  modal: {
    background: 'var(--surface)',
    borderRadius: 'var(--radius)',
    width: '100%',
    maxWidth: '480px',
    maxHeight: '90vh',
    overflowY: 'auto',
    padding: '1.5rem',
    position: 'relative',
  },
  close: {
    position: 'absolute',
    top: '0.75rem',
    right: '0.75rem',
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '1.5rem',
    cursor: 'pointer',
    lineHeight: 1,
  },
  title: {
    fontSize: '1.2rem',
    fontWeight: 700,
    marginBottom: '1rem',
    color: 'var(--text)',
  },
  dropzone: {
    border: '2px dashed var(--border-2)',
    borderRadius: 'var(--radius-sm)',
    padding: '2rem 1rem',
    textAlign: 'center',
    cursor: 'pointer',
    color: 'var(--text-muted)',
    fontSize: '0.9rem',
    transition: 'border-color 0.15s',
    marginBottom: '1rem',
  },
  preview: {
    width: '100%',
    maxHeight: '250px',
    borderRadius: 'var(--radius-sm)',
    objectFit: 'cover',
    marginBottom: '1rem',
    background: '#000',
  },
  label: {
    display: 'block',
    fontSize: '0.8rem',
    color: 'var(--text-muted)',
    marginBottom: '0.3rem',
    fontWeight: 600,
  },
  input: {
    width: '100%',
    padding: '0.5rem 0.65rem',
    background: 'var(--bg)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text)',
    fontFamily: 'inherit',
    fontSize: '0.85rem',
    marginBottom: '0.75rem',
  },
  row: {
    display: 'flex',
    gap: '0.75rem',
  },
  half: {
    flex: 1,
  },
  searchResults: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    maxHeight: '150px',
    overflowY: 'auto',
    marginTop: '-0.5rem',
    marginBottom: '0.75rem',
  },
  searchItem: {
    padding: '0.5rem 0.65rem',
    cursor: 'pointer',
    fontSize: '0.85rem',
    borderBottom: '1px solid var(--border)',
    color: 'var(--text)',
  },
  selected: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    background: 'var(--amber-dim)',
    border: '1px solid var(--amber)',
    borderRadius: 'var(--radius-sm)',
    padding: '0.4rem 0.65rem',
    marginBottom: '0.75rem',
    fontSize: '0.85rem',
    color: 'var(--amber-light)',
  },
  clearBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    fontSize: '1rem',
    marginLeft: 'auto',
  },
  submit: {
    width: '100%',
    padding: '0.65rem',
    background: 'var(--amber)',
    color: '#1a1a1a',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    fontWeight: 700,
    fontSize: '0.95rem',
    cursor: 'pointer',
    fontFamily: 'inherit',
    marginTop: '0.5rem',
    transition: 'background 0.15s',
  },
  error: {
    color: 'var(--red-light)',
    fontSize: '0.85rem',
    marginBottom: '0.75rem',
  },
  progress: {
    fontSize: '0.85rem',
    color: 'var(--text-muted)',
    textAlign: 'center',
    padding: '1rem 0',
  },
}

export default function VideoUpload({ onClose, onSuccess }) {
  const fileInputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [caption, setCaption] = useState('')
  const [locationName, setLocationName] = useState('')
  const [priceTag, setPriceTag] = useState('')
  const [whiskeySearch, setWhiskeySearch] = useState('')
  const [whiskeyResults, setWhiskeyResults] = useState([])
  const [selectedWhiskey, setSelectedWhiskey] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  // Clean up object URL on unmount or when file changes
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  // Whiskey autocomplete
  useEffect(() => {
    if (whiskeySearch.length < 2 || selectedWhiskey) {
      setWhiskeyResults([])
      return
    }
    const timer = setTimeout(async () => {
      try {
        const data = await api.listWhiskeys({ q: whiskeySearch, limit: 6 })
        setWhiskeyResults(data.items || data)
      } catch {
        setWhiskeyResults([])
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [whiskeySearch, selectedWhiskey])

  function handleFileSelect(e) {
    const f = e.target.files?.[0]
    if (!f) return
    if (f.size > MAX_SIZE) {
      setError('Video too large (max 100 MB)')
      return
    }
    setError('')
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!file) {
      setError('Please select a video')
      return
    }
    setUploading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)
    if (caption.trim()) formData.append('title', caption.trim())
    if (selectedWhiskey) formData.append('whiskey_id', selectedWhiskey.id)
    if (locationName.trim()) formData.append('location_name', locationName.trim())
    if (priceTag) formData.append('price_tag', priceTag)

    try {
      await api.uploadVideo(formData)
      onSuccess()
    } catch (err) {
      setError(err.message || 'Upload failed')
      setUploading(false)
    }
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <button style={styles.close} onClick={onClose}>&times;</button>
        <h2 style={styles.title}>Upload Video</h2>

        <form onSubmit={handleSubmit}>
          {/* File picker */}
          {!previewUrl ? (
            <div
              style={styles.dropzone}
              onClick={() => fileInputRef.current?.click()}
            >
              <p>Tap to select a video</p>
              <p style={{ fontSize: '0.75rem', marginTop: '0.3rem' }}>MP4, MOV, WebM &middot; Max 100 MB</p>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/quicktime,video/webm"
                capture="environment"
                style={{ display: 'none' }}
                onChange={handleFileSelect}
              />
            </div>
          ) : (
            <video
              src={previewUrl}
              style={styles.preview}
              controls
              playsInline
            />
          )}

          {error && <p style={styles.error}>{error}</p>}

          {/* Caption */}
          <label style={styles.label}>Caption</label>
          <input
            style={styles.input}
            placeholder="What's this about?"
            value={caption}
            onChange={e => setCaption(e.target.value)}
            maxLength={200}
          />

          {/* Tag whiskey */}
          <label style={styles.label}>Tag a Whiskey</label>
          {selectedWhiskey ? (
            <div style={styles.selected}>
              <span>🥃 {selectedWhiskey.name}</span>
              <button
                type="button"
                style={styles.clearBtn}
                onClick={() => { setSelectedWhiskey(null); setWhiskeySearch('') }}
              >
                &times;
              </button>
            </div>
          ) : (
            <>
              <input
                style={styles.input}
                placeholder="Search whiskeys..."
                value={whiskeySearch}
                onChange={e => setWhiskeySearch(e.target.value)}
              />
              {whiskeyResults.length > 0 && (
                <div style={styles.searchResults}>
                  {whiskeyResults.map(w => (
                    <div
                      key={w.id}
                      style={styles.searchItem}
                      onClick={() => {
                        setSelectedWhiskey(w)
                        setWhiskeySearch('')
                        setWhiskeyResults([])
                      }}
                      onMouseEnter={e => e.target.style.background = 'var(--border)'}
                      onMouseLeave={e => e.target.style.background = ''}
                    >
                      {w.name} — <span style={{ color: 'var(--text-muted)' }}>{w.distillery}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Location + Price */}
          <div style={styles.row}>
            <div style={styles.half}>
              <label style={styles.label}>Location</label>
              <input
                style={styles.input}
                placeholder="Bar, store, home..."
                value={locationName}
                onChange={e => setLocationName(e.target.value)}
                maxLength={100}
              />
            </div>
            <div style={styles.half}>
              <label style={styles.label}>Price</label>
              <input
                style={styles.input}
                type="number"
                step="0.01"
                min="0"
                placeholder="$0.00"
                value={priceTag}
                onChange={e => setPriceTag(e.target.value)}
              />
            </div>
          </div>

          {uploading ? (
            <p style={styles.progress}>Uploading...</p>
          ) : (
            <button
              type="submit"
              style={{
                ...styles.submit,
                opacity: file ? 1 : 0.5,
                cursor: file ? 'pointer' : 'not-allowed',
              }}
              disabled={!file}
            >
              Share Video
            </button>
          )}
        </form>
      </div>
    </div>
  )
}
