import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useToast } from './Toast'

export default function UserSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const addToast = useToast()

  useEffect(() => {
    const t = setTimeout(() => {
      if (query.trim().length >= 1) {
        api.searchUsers(query.trim())
          .then(r => { setResults(r); setOpen(true) })
          .catch(() => addToast('Search failed — please try again', 'error'))
      } else {
        setResults([])
        setOpen(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query, addToast])

  // Close on outside click
  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="user-search" ref={ref}>
      <input
        className="user-search-input"
        placeholder="Find people\u2026"
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="user-search-dropdown">
          {results.map(u => (
            <Link
              key={u.username}
              to={`/user/${u.username}`}
              className="user-search-result"
              onClick={() => { setQuery(''); setOpen(false) }}
            >
              <span className="usr-name">{u.username}</span>
              <span className="usr-meta">{u.total_checkins} check-ins · {u.follower_count} followers</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
