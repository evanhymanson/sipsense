import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api, getUsername } from '../api/client'

function ListIndex() {
  const [lists, setLists] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const navigate = useNavigate()

  const loadLists = useCallback(() => {
    api.getUserListsByUser(getUsername())
      .then(setLists)
      .catch(() => setLists([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadLists() }, [loadLists])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    try {
      const list = await api.createUserList({
        title: title.trim(),
        description: description.trim() || null,
        is_public: isPublic,
        whiskey_ids: [],
      })
      setShowCreate(false)
      setTitle('')
      setDescription('')
      navigate(`/my-lists/${list.slug}`)
    } catch {
      // handled by global error
    }
  }

  if (loading) return <div className="page-loading">Loading lists...</div>

  return (
    <div className="userlists-index">
      <div className="userlists-header">
        <h2>My Lists</h2>
        <button
          className="btn-primary"
          onClick={() => setShowCreate(!showCreate)}
        >
          {showCreate ? 'Cancel' : '+ New List'}
        </button>
      </div>

      {showCreate && (
        <form className="userlists-create-form" onSubmit={handleCreate}>
          <input
            type="text"
            placeholder="List title (e.g. My Top 10 Bourbons)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            required
          />
          <textarea
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
          <label className="userlists-public-toggle">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
            />
            Public list
          </label>
          <button type="submit" className="btn-primary">
            Create List
          </button>
        </form>
      )}

      {lists.length === 0 && !showCreate ? (
        <p className="userlists-empty">
          You haven't created any lists yet. Click "+ New List" to get started!
        </p>
      ) : (
        <div className="userlists-grid">
          {lists.map((list) => (
            <Link
              key={list.id}
              to={`/my-lists/${list.slug}`}
              className="userlists-card"
            >
              <h3>{list.title}</h3>
              {list.description && (
                <p className="userlists-card-desc">{list.description}</p>
              )}
              <div className="userlists-card-meta">
                <span>{list.item_count} whiskeys</span>
                {!list.is_public && <span className="userlists-private">Private</span>}
              </div>
              {list.preview_whiskeys && list.preview_whiskeys.length > 0 && (
                <div className="userlists-preview">
                  {list.preview_whiskeys.map((w) => (
                    <span key={w.id} className="userlists-preview-name">
                      {w.name}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function ListDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [list, setList] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const currentUser = getUsername()

  const loadList = useCallback(() => {
    api.getUserList(slug)
      .then((data) => {
        setList(data)
        setEditTitle(data.title)
        setEditDesc(data.description || '')
      })
      .catch(() => navigate('/my-lists'))
      .finally(() => setLoading(false))
  }, [slug, navigate])

  useEffect(() => { loadList() }, [loadList])

  const isOwner = list && list.username === currentUser

  const handleUpdate = async (e) => {
    e.preventDefault()
    await api.updateUserList(slug, {
      title: editTitle.trim(),
      description: editDesc.trim() || null,
    })
    setEditing(false)
    loadList()
  }

  const handleDelete = async () => {
    if (!window.confirm('Delete this list? This cannot be undone.')) return
    await api.deleteUserList(slug)
    navigate('/my-lists')
  }

  const handleRemoveItem = async (whiskeyId) => {
    await api.removeFromUserList(slug, whiskeyId)
    loadList()
  }

  const handleSearch = async (q) => {
    setSearchQuery(q)
    if (q.length < 2) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const results = await api.searchWhiskeys(q)
      setSearchResults(results.slice(0, 5))
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleAddWhiskey = async (whiskeyId) => {
    try {
      await api.addToUserList(slug, { whiskey_id: whiskeyId })
      setSearchQuery('')
      setSearchResults([])
      loadList()
    } catch {
      // duplicate or error
    }
  }

  if (loading) return <div className="page-loading">Loading list...</div>
  if (!list) return null

  return (
    <div className="userlists-detail">
      <Link to="/my-lists" className="back-link">Back to My Lists</Link>

      {editing ? (
        <form className="userlists-edit-form" onSubmit={handleUpdate}>
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            maxLength={200}
            required
          />
          <textarea
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
            rows={2}
            placeholder="Description (optional)"
          />
          <div className="userlists-edit-actions">
            <button type="submit" className="btn-primary">Save</button>
            <button type="button" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="userlists-detail-header">
          <h2>{list.title}</h2>
          {list.description && <p>{list.description}</p>}
          <span className="userlists-detail-meta">
            {list.item_count} whiskeys
            {!list.is_public && ' \u00B7 Private'}
            {' \u00B7 by '}
            <Link to={`/user/${list.username}`}>{list.username}</Link>
          </span>
          {isOwner && (
            <div className="userlists-owner-actions">
              <button onClick={() => setEditing(true)}>Edit</button>
              <button className="btn-danger" onClick={handleDelete}>Delete</button>
            </div>
          )}
        </div>
      )}

      {isOwner && (
        <div className="userlists-add-whiskey">
          <input
            type="text"
            placeholder="Search whiskeys to add..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
          />
          {searching && <p className="userlists-searching">Searching...</p>}
          {searchResults.length > 0 && (
            <div className="userlists-search-results">
              {searchResults.map((w) => (
                <button
                  key={w.id}
                  className="userlists-search-item"
                  onClick={() => handleAddWhiskey(w.id)}
                >
                  <span>{w.name}</span>
                  <span className="userlists-add-btn">+ Add</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {list.items && list.items.length > 0 ? (
        <div className="userlists-items">
          {list.items.map((item, idx) => (
            <div key={item.whiskey.id} className="userlists-item">
              <span className="userlists-item-rank">{idx + 1}</span>
              <div className="userlists-item-info">
                <Link to={`/whiskey/${item.whiskey.id}`}>
                  {item.whiskey.name}
                </Link>
                <span className="userlists-item-meta">
                  {item.whiskey.distillery} &middot; {item.whiskey.category}
                </span>
                {item.note && (
                  <p className="userlists-item-note">{item.note}</p>
                )}
              </div>
              {isOwner && (
                <button
                  className="userlists-item-remove"
                  onClick={() => handleRemoveItem(item.whiskey.id)}
                  title="Remove"
                >
                  &times;
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="userlists-empty">
          This list is empty. {isOwner ? 'Search above to add whiskeys!' : ''}
        </p>
      )}
    </div>
  )
}

export default function UserLists() {
  const { slug } = useParams()
  return slug ? <ListDetail /> : <ListIndex />
}
