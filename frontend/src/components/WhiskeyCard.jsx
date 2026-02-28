import { Link } from 'react-router-dom'

const CATEGORY_EMOJI = {
  bourbon: '🥃',
  scotch: '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
  irish: '☘️',
  japanese: '🗾',
  rye: '🌾',
  canadian: '🍁',
  'single malt': '🏰',
  blended: '🥃',
  default: '🥃',
}

export default function WhiskeyCard({ whiskey, score }) {
  const emoji = CATEGORY_EMOJI[whiskey.category?.toLowerCase()] ?? CATEGORY_EMOJI.default
  const stars = '★'.repeat(Math.round(whiskey.rating_avg)) + '☆'.repeat(5 - Math.round(whiskey.rating_avg))

  return (
    <Link to={`/whiskey/${whiskey.id}`} className="card">
      <div className="card-header">
        <span className="card-emoji">{emoji}</span>
        <span className="card-category">{whiskey.category}</span>
      </div>
      <h3 className="card-name">{whiskey.name}</h3>
      <p className="card-distillery">{whiskey.distillery}</p>
      <div className="card-meta">
        <span>{whiskey.abv}% ABV</span>
        {whiskey.age && <span>{whiskey.age}yr</span>}
        {whiskey.region && <span>{whiskey.region}</span>}
        {whiskey.price_usd && <span>${whiskey.price_usd}</span>}
      </div>
      <div className="card-rating">
        <span className="stars">{stars}</span>
        <span className="rating-count">({whiskey.rating_count})</span>
      </div>
      {score != null && (
        <div className="card-score">Match: {Math.round(score * 100)}%</div>
      )}
    </Link>
  )
}
