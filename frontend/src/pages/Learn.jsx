import { useState, useEffect } from 'react'
import { api } from '../api/client'
import './Learn.css'

// ─── Whiskey 101 Tab ────────────────────────────────────────────────────────

function CategoryCard({ category, onSelect, selected }) {
  return (
    <button
      className={`category-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect(category.slug)}
    >
      <span className="category-emoji">{category.emoji}</span>
      <div className="category-card-text">
        <span className="category-card-title">{category.title}</span>
        <span className="category-card-tagline">{category.tagline}</span>
      </div>
    </button>
  )
}

function CategoryDetail({ slug }) {
  const [guide, setGuide] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getCategory(slug)
      .then(setGuide)
      .finally(() => setLoading(false))
  }, [slug])

  if (loading) return <div className="learn-loading">Loading…</div>
  if (!guide) return null

  return (
    <div className="category-detail">
      <div className="category-detail-header">
        <span className="detail-emoji">{guide.emoji}</span>
        <div>
          <h2>{guide.title}</h2>
          <p className="detail-tagline">{guide.tagline}</p>
        </div>
      </div>

      <div className="quick-facts">
        {guide.quick_facts.map((fact, i) => (
          <div key={i} className="fact-chip">{fact}</div>
        ))}
      </div>

      <div className="flavor-tags">
        {guide.flavor_tags.map(tag => (
          <span key={tag} className="flavor-tag">{tag}</span>
        ))}
      </div>

      <div className="guide-body">
        {guide.body.map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>

      <div className="entry-bottles">
        <h3>Where to Start</h3>
        <div className="bottle-chips">
          {guide.entry_bottles.map(b => (
            <span key={b} className="bottle-chip">{b}</span>
          ))}
        </div>
      </div>

      {guide.next_explore && (
        <div className="next-explore">
          <h3>Next to Explore</h3>
          <div className="bottle-chips">
            <span className="bottle-chip next">{guide.next_explore}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function WhiskeyTab() {
  const [categories, setCategories] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    api.listCategories().then(data => {
      setCategories(data)
      if (data.length > 0) setSelected(data[0].slug)
    })
  }, [])

  return (
    <div className="whiskey-tab">
      <div className="category-sidebar">
        <p className="sidebar-label">Pick a style</p>
        {categories.map(c => (
          <CategoryCard
            key={c.slug}
            category={c}
            selected={selected === c.slug}
            onSelect={setSelected}
          />
        ))}
      </div>
      <div className="category-content">
        {selected && <CategoryDetail slug={selected} />}
      </div>
    </div>
  )
}

// ─── Distillery Stories Tab ──────────────────────────────────────────────────

function DistilleryCard({ distillery, expanded, onToggle }) {
  return (
    <div className={`distillery-card ${expanded ? 'expanded' : ''}`}>
      <button className="distillery-header" onClick={onToggle}>
        <div className="distillery-header-left">
          <span className="distillery-emoji">{distillery.emoji}</span>
          <div>
            <span className="distillery-title">{distillery.title}</span>
            <span className="distillery-meta">
              {distillery.location} · {distillery.category}
            </span>
          </div>
        </div>
        <span className="expand-arrow">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && <DistilleryBody slug={distillery.slug} tagline={distillery.tagline} />}
    </div>
  )
}

function DistilleryBody({ slug, tagline }) {
  const [story, setStory] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getDistillery(slug)
      .then(setStory)
      .finally(() => setLoading(false))
  }, [slug])

  if (loading) return <div className="learn-loading">Loading…</div>

  return (
    <div className="distillery-body">
      <p className="distillery-tagline">{tagline}</p>
      <div className="known-for">
        {story.known_for.map(k => (
          <span key={k} className="known-chip">{k}</span>
        ))}
      </div>
      {story.body.map((para, i) => (
        <p key={i}>{para}</p>
      ))}
    </div>
  )
}

function DistilleriesTab() {
  const [distilleries, setDistilleries] = useState([])
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    api.listDistilleries().then(setDistilleries)
  }, [])

  const toggle = (slug) => setExpanded(prev => prev === slug ? null : slug)

  return (
    <div className="distilleries-tab">
      <p className="tab-intro">
        Every great whiskey has a story behind it. Learn who's making the bottles
        you love — and why they taste the way they do.
      </p>
      <div className="distillery-list">
        {distilleries.map(d => (
          <DistilleryCard
            key={d.slug}
            distillery={d}
            expanded={expanded === d.slug}
            onToggle={() => toggle(d.slug)}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Glossary Tab ────────────────────────────────────────────────────────────

function GlossaryTab() {
  const [terms, setTerms] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.getGlossary().then(setTerms)
  }, [])

  const filtered = terms.filter(t =>
    t.term.toLowerCase().includes(search.toLowerCase()) ||
    t.definition.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="glossary-tab">
      <p className="tab-intro">
        Confused by tasting notes and label jargon? This glossary translates
        whiskey-speak into plain English.
      </p>
      <input
        className="glossary-search"
        type="text"
        placeholder="Search terms…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
      <div className="glossary-list">
        {filtered.map(t => (
          <div key={t.term} className="glossary-entry">
            <span className="glossary-term">{t.term}</span>
            <span className="glossary-definition">{t.definition}</span>
          </div>
        ))}
        {filtered.length === 0 && (
          <p className="no-results">No terms match "{search}"</p>
        )}
      </div>
    </div>
  )
}

// ─── Main Page ───────────────────────────────────────────────────────────────

const TABS = [
  { id: 'whiskey101', label: 'Whiskey 101' },
  { id: 'distilleries', label: 'Distillery Stories' },
  { id: 'glossary', label: 'Glossary' },
]

export default function Learn() {
  const [activeTab, setActiveTab] = useState('whiskey101')

  return (
    <div className="learn-page">
      <div className="learn-hero">
        <h1>Learn Whiskey</h1>
        <p>
          From your first dram to deep cuts — build real whiskey knowledge,
          one pour at a time.
        </p>
      </div>

      <div className="learn-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`learn-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="learn-body">
        {activeTab === 'whiskey101' && <WhiskeyTab />}
        {activeTab === 'distilleries' && <DistilleriesTab />}
        {activeTab === 'glossary' && <GlossaryTab />}
      </div>
    </div>
  )
}
