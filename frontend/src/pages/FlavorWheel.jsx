import { useNavigate } from 'react-router-dom'
import { FLAVOR_TAXONOMY } from '../data/flavorTaxonomy'
import './FlavorWheel.css'

export default function FlavorWheel() {
  const navigate = useNavigate()

  function browse(id) {
    navigate(`/?flavor=${encodeURIComponent(id)}`)
  }

  return (
    <div className="page fb-page">
      <h1>Explore by Flavor</h1>
      <p className="page-subtitle">Click any flavor to browse matching whiskeys.</p>

      <div className="fb-families">
        {FLAVOR_TAXONOMY.map(family => (
          <div key={family.id} className="fb-family">
            <button
              className="fb-family-header"
              style={{ '--family-color': family.color }}
              onClick={() => browse(family.id)}
            >
              {family.label}
            </button>

            <div className="fb-subs">
              {family.children.map(sub => (
                <div key={sub.id} className="fb-sub">
                  <button
                    className="fb-sub-label"
                    style={{ '--family-color': family.color }}
                    onClick={() => browse(sub.id)}
                  >
                    {sub.label}
                  </button>
                  <div className="fb-chips">
                    {sub.children.map(leaf => (
                      <button
                        key={leaf.id}
                        className="fb-chip"
                        style={{ '--family-color': family.color }}
                        onClick={() => browse(leaf.id)}
                      >
                        {leaf.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
