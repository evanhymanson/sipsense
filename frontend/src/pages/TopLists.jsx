import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function TopLists() {
  const { slug } = useParams()

  if (slug) return <TopListDetail slug={slug} />
  return <TopListIndex />
}

function TopListIndex() {
  const [lists, setLists] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getTopLists()
      .then(setLists)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page"><p className="status">Loading...</p></div>

  return (
    <div className="page">
      <h1>Top Lists</h1>
      <p className="page-subtitle">Curated and community-driven whiskey rankings</p>
      <div className="toplists-grid">
        {lists.map(tl => (
          <Link key={tl.slug} to={`/lists/${tl.slug}`} className="toplist-card">
            <span className="toplist-emoji">{tl.image_emoji}</span>
            <div className="toplist-info">
              <h3>{tl.title}</h3>
              <p>{tl.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

function TopListDetail({ slug }) {
  const [list, setList] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getTopList(slug)
      .then(setList)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [slug])

  if (loading) return <div className="page"><p className="status">Loading...</p></div>
  if (!list) return <div className="page"><p className="status">List not found</p></div>

  return (
    <div className="page">
      <Link to="/lists" className="back-link">&larr; All Lists</Link>
      <h1>{list.image_emoji} {list.title}</h1>
      {list.description && <p className="page-subtitle">{list.description}</p>}
      <div className="toplist-items">
        {list.items.map(item => (
          <div key={item.whiskey.id} className="toplist-item">
            <span className="toplist-rank">#{item.rank}</span>
            <div className="toplist-item-card">
              <WhiskeyCard whiskey={item.whiskey} />
            </div>
            {item.note && <p className="toplist-note">{item.note}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
