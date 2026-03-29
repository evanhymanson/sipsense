import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

const CURRENT_YEAR = new Date().getFullYear()

export default function Awards() {
  const [categories, setCategories] = useState([])
  const [selectedCat, setSelectedCat] = useState(null)
  const [nominees, setNominees] = useState([])
  const [results, setResults] = useState([])
  const [myVotes, setMyVotes] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getAwardCategories(),
      api.getAwards(CURRENT_YEAR),
    ]).then(([cats, res]) => {
      setCategories(cats)
      setResults(res)
      if (cats.length > 0) setSelectedCat(cats[0].slug)
    }).catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedCat) return
    api.getAwardNominees(CURRENT_YEAR, selectedCat, 10)
      .then(setNominees)
      .catch(() => setNominees([]))
    if (isLoggedIn()) {
      api.getMyVote(CURRENT_YEAR, selectedCat)
        .then(v => setMyVotes(prev => ({ ...prev, [selectedCat]: v.whiskey_id })))
        .catch(() => {})
    }
  }, [selectedCat])

  const handleVote = async (whiskeyId) => {
    if (!isLoggedIn()) return
    try {
      await api.castVote(CURRENT_YEAR, selectedCat, whiskeyId)
      setMyVotes(prev => ({ ...prev, [selectedCat]: whiskeyId }))
    } catch { /* ignore */ }
  }

  if (loading) return <div className="page awards-page"><p className="status">Loading awards...</p></div>

  return (
    <div className="page awards-page">
      <Helmet>
        <title>Community Awards {CURRENT_YEAR} | SipSense</title>
        <meta name="description" content={`Vote for the best whiskeys of ${CURRENT_YEAR} in the SipSense Community Awards.`} />
        <link rel="canonical" href="https://sipsense.ai/awards" />
      </Helmet>
      <h1>Community Awards {CURRENT_YEAR}</h1>
      <p className="page-subtitle">Vote for the best whiskeys of the year across 8 categories.</p>

      <div className="awards-categories">
        {categories.map(cat => (
          <button
            key={cat.slug}
            className={`award-cat-btn ${selectedCat === cat.slug ? 'active' : ''}`}
            onClick={() => setSelectedCat(cat.slug)}
          >
            <span className="award-cat-emoji">{cat.emoji}</span>
            <span>{cat.title}</span>
          </button>
        ))}
      </div>

      {selectedCat && (
        <div className="awards-nominees">
          <h2>{categories.find(c => c.slug === selectedCat)?.title} Nominees</h2>
          <p className="awards-desc">{categories.find(c => c.slug === selectedCat)?.description}</p>
          {nominees.length === 0 ? (
            <p className="status">No nominees yet for this category.</p>
          ) : (
            <div className="nominees-list">
              {nominees.map(n => (
                <div key={n.whiskey.id} className={`nominee-card ${myVotes[selectedCat] === n.whiskey.id ? 'voted' : ''}`}>
                  <WhiskeyCard whiskey={n.whiskey} compact />
                  <div className="nominee-actions">
                    <span className="vote-count">{n.vote_count} votes</span>
                    {isLoggedIn() && (
                      <button
                        className={`btn-vote ${myVotes[selectedCat] === n.whiskey.id ? 'voted' : ''}`}
                        onClick={() => handleVote(n.whiskey.id)}
                      >
                        {myVotes[selectedCat] === n.whiskey.id ? 'Voted' : 'Vote'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {results.length > 0 && (
        <div className="awards-results">
          <h2>Results So Far</h2>
          {results.map(cat => (
            <div key={cat.slug} className="award-result-category">
              <h3>{cat.emoji} {cat.title}</h3>
              {cat.winners?.map(w => (
                <div key={w.rank} className="award-winner">
                  <span className="winner-rank">#{w.rank}</span>
                  <span className="winner-name">{w.whiskey.name}</span>
                  <span className="winner-votes">{w.vote_count} votes</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
