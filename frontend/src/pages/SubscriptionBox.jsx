import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'
import WhiskeyCard from '../components/WhiskeyCard'

export default function SubscriptionBox() {
  const [tiers, setTiers] = useState({})
  const [_Prefs, setPrefs] = useState(null)
  const [preview, setPreview] = useState(null)
  const [selectedTier, setSelectedTier] = useState('explorer')
  const [frequency, setFrequency] = useState('monthly')
  const [categories, setCategories] = useState([])
  const [priceMin, setPriceMin] = useState('')
  const [priceMax, setPriceMax] = useState('')
  const [avoidFlavors, setAvoidFlavors] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api.getBoxTiers().then(setTiers).catch(() => {})
    if (isLoggedIn()) {
      api.getBoxPreferences().then(p => {
        setPrefs(p)
        if (p.tier) setSelectedTier(p.tier)
        if (p.frequency) setFrequency(p.frequency)
        if (p.preferences?.categories) setCategories(p.preferences.categories)
        if (p.preferences?.price_min) setPriceMin(p.preferences.price_min)
        if (p.preferences?.price_max) setPriceMax(p.preferences.price_max)
        if (p.preferences?.avoid_flavors) setAvoidFlavors(p.preferences.avoid_flavors.join(', '))
      }).catch(() => {})
      api.previewBox().then(setPreview).catch(() => {})
    }
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    try {
      const result = await api.updateBoxPreferences({
        tier: selectedTier,
        frequency,
        categories,
        price_min: priceMin ? Number(priceMin) : null,
        price_max: priceMax ? Number(priceMax) : null,
        avoid_flavors: avoidFlavors ? avoidFlavors.split(',').map(s => s.trim()).filter(Boolean) : [],
      })
      setMessage(result.message)
      api.previewBox().then(setPreview).catch(() => {})
    } catch {
      setMessage('Failed to save preferences.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page subscription-box-page">
      <Helmet>
        <title>Subscription Box | SipSense</title>
        <meta name="description" content="Get curated whiskey bottles delivered to your door, matched to your palate." />
      </Helmet>
      <h1>Whiskey Subscription Box</h1>

      <div className="coming-soon-banner">
        <h2>Launching Soon</h2>
        <p>Curated whiskey boxes matched to your palate profile. Set your preferences now and join the waitlist.</p>
      </div>

      <div className="box-tiers">
        <h2>Choose Your Tier</h2>
        <div className="tiers-grid">
          {Object.entries(tiers).map(([key, tier]) => (
            <div
              key={key}
              className={`tier-card ${selectedTier === key ? 'selected' : ''}`}
              onClick={() => setSelectedTier(key)}
            >
              <h3>{tier.name}</h3>
              <div className="tier-bottles">{tier.bottles} bottles</div>
              <div className="tier-price">{tier.price_range}</div>
              <p>{tier.description}</p>
            </div>
          ))}
        </div>
      </div>

      {isLoggedIn() && (
        <div className="box-preferences">
          <h2>Your Preferences</h2>
          <div className="pref-form">
            <label>
              Delivery Frequency
              <select value={frequency} onChange={e => setFrequency(e.target.value)}>
                <option value="monthly">Monthly</option>
                <option value="bimonthly">Every 2 Months</option>
                <option value="quarterly">Quarterly</option>
              </select>
            </label>

            <label>
              Preferred Categories (comma-separated)
              <input
                type="text"
                value={categories.join(', ')}
                onChange={e => setCategories(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                placeholder="bourbon, scotch, irish..."
              />
            </label>

            <div className="pref-row">
              <label>
                Min Price ($)
                <input type="number" value={priceMin} onChange={e => setPriceMin(e.target.value)} placeholder="30" />
              </label>
              <label>
                Max Price ($)
                <input type="number" value={priceMax} onChange={e => setPriceMax(e.target.value)} placeholder="100" />
              </label>
            </div>

            <label>
              Flavors to Avoid (comma-separated)
              <input
                type="text"
                value={avoidFlavors}
                onChange={e => setAvoidFlavors(e.target.value)}
                placeholder="smoky, peaty..."
              />
            </label>

            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save & Join Waitlist'}
            </button>
            {message && <p className="pref-message">{message}</p>}
          </div>
        </div>
      )}

      {preview && preview.preview_bottles?.length > 0 && (
        <div className="box-preview">
          <h2>Preview: What Your Next Box Might Include</h2>
          <p className="preview-note">{preview.message}</p>
          <div className="whiskey-grid">
            {preview.preview_bottles.map(w => (
              <WhiskeyCard key={w.id} whiskey={w} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
