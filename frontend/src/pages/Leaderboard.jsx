import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'

export default function Leaderboard() {
  const [data, setData] = useState(null)
  const [period, setPeriod] = useState('all_time')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getLeaderboard({ period, limit: 50 })
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [period])

  return (
    <div className="page leaderboard-page">
      <Helmet>
        <title>Leaderboard | SipSense</title>
        <meta name="description" content="See who's leading the SipSense community in check-ins, helpful reviews, and engagement." />
        <link rel="canonical" href="https://sipsense.ai/leaderboard" />
      </Helmet>
      <h1>Community Leaderboard</h1>
      <p className="page-subtitle">Top reviewers ranked by check-ins, helpful votes, and community engagement.</p>

      <div className="leaderboard-controls">
        {['all_time', 'monthly', 'weekly'].map(p => (
          <button
            key={p}
            className={`btn-pill ${period === p ? 'active' : ''}`}
            onClick={() => setPeriod(p)}
          >
            {p === 'all_time' ? 'All Time' : p === 'monthly' ? 'This Month' : 'This Week'}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="status">Loading leaderboard...</p>
      ) : data ? (
        <>
          {data.user_rank && (
            <div className="leaderboard-your-rank">
              Your rank: <strong>#{data.user_rank}</strong>
            </div>
          )}
          <table className="leaderboard-table">
            <thead>
              <tr>
                <th>#</th>
                <th>User</th>
                <th>Check-ins</th>
                <th>Helpful Votes</th>
                <th>Comments</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {data.entries?.map((entry) => (
                <tr key={entry.username} className={entry.username === data.entries?.find?.(e => e.rank === data.user_rank)?.username ? 'highlight' : ''}>
                  <td className="rank-cell">
                    {entry.rank <= 3 ? ['', '\u{1F947}', '\u{1F948}', '\u{1F949}'][entry.rank] : entry.rank}
                  </td>
                  <td>
                    {isLoggedIn() ? (
                      <Link to={`/user/${entry.username}`}>{entry.username}</Link>
                    ) : entry.username}
                  </td>
                  <td>{entry.total_checkins}</td>
                  <td>{entry.helpful_votes_received}</td>
                  <td>{entry.comments_given}</td>
                  <td className="score-cell">{entry.engagement_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <p className="status">Could not load leaderboard.</p>
      )}
    </div>
  )
}
