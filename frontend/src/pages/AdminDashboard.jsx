import { useState, useEffect } from 'react'
import { api } from '../api/client'

function MetricCard({ label, value, sub }) {
  return (
    <div className="admin-metric-card">
      <div className="admin-metric-value">{value}</div>
      <div className="admin-metric-label">{label}</div>
      {sub && <div className="admin-metric-sub">{sub}</div>}
    </div>
  )
}

function BarChart({ data, labelKey, valueKey, maxValue }) {
  if (!data || !data.length) return <p style={{ color: 'var(--text-muted)' }}>No data yet</p>
  const max = maxValue || Math.max(...data.map(d => d[valueKey]))
  return (
    <div className="admin-bar-chart">
      {data.map((d, i) => (
        <div key={i} className="admin-bar-row">
          <span className="admin-bar-label">{d[labelKey]}</span>
          <div className="admin-bar-track">
            <div
              className="admin-bar-fill"
              style={{ width: max > 0 ? `${(d[valueKey] / max) * 100}%` : '0%' }}
            />
          </div>
          <span className="admin-bar-value">{d[valueKey]}</span>
        </div>
      ))}
    </div>
  )
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [funnel, setFunnel] = useState(null)
  const [topWhiskeys, setTopWhiskeys] = useState(null)
  const [adoption, setAdoption] = useState(null)
  const [performance, setPerformance] = useState(null)
  const [dataAsset, setDataAsset] = useState(null)
  const [recFunnel, setRecFunnel] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getAnalyticsOverview(),
      api.getAnalyticsFunnel(),
      api.getAnalyticsTopWhiskeys(),
      api.getAnalyticsFeatureAdoption(),
      api.getAnalyticsPerformance(),
      api.getDataAsset(),
      api.getRecommendationFunnel(),
    ])
      .then(([ov, fn, tw, ad, pf, da, rf]) => {
        setOverview(ov)
        setFunnel(fn)
        setTopWhiskeys(tw)
        setAdoption(ad)
        setPerformance(pf)
        setDataAsset(da)
        setRecFunnel(rf)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page" style={{ textAlign: 'center', padding: '4rem' }}>Loading analytics...</div>
  if (error) return (
    <div className="page" style={{ textAlign: 'center', padding: '4rem' }}>
      <h2>Access Denied</h2>
      <p style={{ color: 'var(--text-muted)' }}>{error}</p>
    </div>
  )

  const funnelData = funnel ? [
    { label: 'Registered', value: funnel.registered },
    { label: 'Quiz Done', value: funnel.quiz_completed },
    { label: 'First Rating', value: funnel.first_rating },
    { label: 'First Favorite', value: funnel.first_favorite },
    { label: 'Return Login', value: funnel.return_login },
    { label: 'Premium', value: funnel.premium },
  ] : []

  return (
    <div className="page admin-dashboard">
      <h1>Analytics Dashboard</h1>

      {/* Key Metrics */}
      {overview && (
        <section className="admin-section">
          <h2>Key Metrics</h2>
          <div className="admin-metrics-grid">
            <MetricCard label="DAU" value={overview.dau} sub="Daily Active Users" />
            <MetricCard label="WAU" value={overview.wau} sub="Weekly Active Users" />
            <MetricCard label="MAU" value={overview.mau} sub="Monthly Active Users" />
            <MetricCard label="Total Users" value={overview.total_users} />
            <MetricCard label="Total Ratings" value={overview.total_ratings} />
            <MetricCard label="Total Favorites" value={overview.total_favorites} />
            <MetricCard label="Requests Today" value={overview.requests_today} />
            <MetricCard label="Avg Response" value={`${overview.avg_response_time_ms}ms`} />
            <MetricCard label="Error Rate" value={`${overview.error_rate_pct}%`} />
          </div>
        </section>
      )}

      {/* Data Asset — the 4 numbers an acquirer cares about */}
      {dataAsset && (
        <section className="admin-section">
          <h2>Data Asset</h2>
          <div className="admin-metrics-grid">
            <MetricCard
              label="Taste Profiles"
              value={dataAsset.taste_profiles.total}
              sub={`${dataAsset.taste_profiles.pct_of_users}% of ${dataAsset.taste_profiles.total_users} users`}
            />
            <MetricCard
              label="Total Ratings"
              value={dataAsset.ratings.total}
              sub={`${dataAsset.ratings.avg_per_user} avg/user across ${dataAsset.ratings.users_with_ratings} users`}
            />
            <MetricCard
              label="Rec Accuracy Lift"
              value={dataAsset.recommendation_accuracy.lift != null
                ? `+${dataAsset.recommendation_accuracy.lift}`
                : 'N/A'}
              sub={dataAsset.recommendation_accuracy.avg_rating_ai_recommended != null
                ? `AI: ${dataAsset.recommendation_accuracy.avg_rating_ai_recommended}/5 vs All: ${dataAsset.recommendation_accuracy.avg_rating_all}/5`
                : 'Need more AI-driven ratings'}
            />
            <MetricCard
              label="AI Click Share"
              value={`${dataAsset.ai_conversion.ai_pct}%`}
              sub={`${dataAsset.ai_conversion.ai_clicks} AI / ${dataAsset.ai_conversion.non_ai_clicks} organic clicks`}
            />
          </div>
          {dataAsset.ratings.distribution?.length > 0 && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}>Ratings per User Distribution</h3>
              <BarChart
                data={dataAsset.ratings.distribution}
                labelKey="bucket"
                valueKey="count"
              />
            </>
          )}
        </section>
      )}

      {/* Recommendation Performance */}
      {recFunnel && (
        <section className="admin-section">
          <h2>Recommendation Performance (30d)</h2>
          <div className="admin-metrics-grid">
            <MetricCard label="Total Clicks" value={recFunnel.total_clicks} />
            <MetricCard label="AI-Driven" value={`${recFunnel.ai_pct}%`} sub={`${recFunnel.ai_clicks} clicks`} />
            <MetricCard label="Organic" value={recFunnel.non_ai_clicks} sub="detail + search + feed" />
          </div>
          {recFunnel.funnel?.length > 0 && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}>Click-Through by Source</h3>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr><th>Source</th><th>Impressions</th><th>Clicks</th><th>CTR</th></tr>
                  </thead>
                  <tbody>
                    {recFunnel.funnel.map((row, i) => (
                      <tr key={i}>
                        <td>{row.source}</td>
                        <td>{row.impressions}</td>
                        <td>{row.clicks}</td>
                        <td>{row.ctr_pct != null ? `${row.ctr_pct}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {recFunnel.top_converting_whiskeys?.length > 0 && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}>Top Converting Whiskeys</h3>
              <BarChart
                data={recFunnel.top_converting_whiskeys.slice(0, 10)}
                labelKey="name"
                valueKey="clicks"
              />
            </>
          )}
        </section>
      )}

      {/* Conversion Funnel */}
      {funnel && (
        <section className="admin-section">
          <h2>Conversion Funnel</h2>
          <BarChart data={funnelData} labelKey="label" valueKey="value" />
        </section>
      )}

      {/* Performance */}
      {performance && (
        <section className="admin-section">
          <h2>API Performance (7d)</h2>
          <div className="admin-metrics-grid">
            <MetricCard label="p50" value={`${performance.p50}ms`} />
            <MetricCard label="p95" value={`${performance.p95}ms`} />
            <MetricCard label="p99" value={`${performance.p99}ms`} />
            <MetricCard label="Avg" value={`${performance.avg_ms}ms`} />
          </div>
          {performance.slowest_endpoints?.length > 0 && (
            <>
              <h3 style={{ marginTop: '1.5rem' }}>Slowest Endpoints</h3>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr><th>Route</th><th>Avg (ms)</th><th>Calls</th></tr>
                  </thead>
                  <tbody>
                    {performance.slowest_endpoints.map((ep, i) => (
                      <tr key={i}>
                        <td><code>{ep.route}</code></td>
                        <td>{ep.avg_ms}</td>
                        <td>{ep.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {/* Feature Adoption */}
      {adoption && adoption.length > 0 && (
        <section className="admin-section">
          <h2>Feature Adoption (30d)</h2>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr><th>Action</th><th>Total Events</th><th>Unique Users</th></tr>
              </thead>
              <tbody>
                {adoption.map((row, i) => (
                  <tr key={i}>
                    <td>{row.action}</td>
                    <td>{row.total}</td>
                    <td>{row.unique_users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Top Whiskeys */}
      {topWhiskeys && (
        <section className="admin-section">
          {topWhiskeys.most_viewed?.length > 0 && (
            <>
              <h2>Most Viewed Whiskeys (30d)</h2>
              <BarChart
                data={topWhiskeys.most_viewed.slice(0, 10)}
                labelKey="name"
                valueKey="views"
              />
            </>
          )}
          {topWhiskeys.most_rated?.length > 0 && (
            <>
              <h2 style={{ marginTop: '2rem' }}>Most Rated Whiskeys (30d)</h2>
              <BarChart
                data={topWhiskeys.most_rated.slice(0, 10)}
                labelKey="name"
                valueKey="ratings"
              />
            </>
          )}
        </section>
      )}
    </div>
  )
}
