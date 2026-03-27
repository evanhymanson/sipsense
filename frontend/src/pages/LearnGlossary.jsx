import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { api } from '../api/client'

export default function LearnGlossary() {
  const [terms, setTerms] = useState([])

  useEffect(() => {
    api.getGlossary().then(setTerms).catch(() => {})
  }, [])

  const letters = [...new Set(terms.map(t => t.term[0].toUpperCase()))].sort()

  return (
    <div className="page learn-page">
      <Helmet>
        <title>Whiskey Glossary | SipSense</title>
        <meta name="description" content="A complete whiskey glossary — 30+ terms from ABV to Single Malt, explained simply." />
        <meta property="og:title" content="Whiskey Glossary | SipSense" />
        <meta property="og:description" content="A complete whiskey glossary — 30+ terms explained simply." />
        <link rel="canonical" href="https://sipsense.ai/learn/glossary" />
      </Helmet>
      <Link to="/learn" className="learn-back">&larr; All Guides</Link>
      <h1>Whiskey Glossary</h1>
      <p className="page-subtitle">Every term you need to know, explained simply.</p>
      {letters.length > 0 && (
        <div className="glossary-letters">
          {letters.map(l => (
            <a key={l} href={`#letter-${l}`} className="glossary-letter">{l}</a>
          ))}
        </div>
      )}
      <div className="glossary-list">
        {letters.map(letter => (
          <div key={letter} id={`letter-${letter}`} className="glossary-group">
            <h2 className="glossary-group-letter">{letter}</h2>
            {terms
              .filter(t => t.term[0].toUpperCase() === letter)
              .map(t => (
                <div key={t.term} className="glossary-item">
                  <dt className="glossary-term">{t.term}</dt>
                  <dd className="glossary-def">{t.definition}</dd>
                </div>
              ))
            }
          </div>
        ))}
      </div>
    </div>
  )
}
