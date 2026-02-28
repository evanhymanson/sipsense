import { useState } from 'react'
import { api } from '../api/client'
import './StoreLocator.css'

export default function ReportModal({ store, whiskeyId, whiskeyName, onClose, onSubmitted }) {
  const [status, setStatus] = useState('in_stock')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.reportAvailability(store.osm_id, {
        whiskey_id: whiskeyId,
        status,
      })
      onSubmitted()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="report-modal-overlay" onClick={onClose}>
      <div className="report-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Report Availability</h3>
        <p className="report-modal__context">
          <strong>{whiskeyName}</strong> at <strong>{store.name}</strong>
        </p>
        <form onSubmit={handleSubmit}>
          <div className="report-modal__options">
            {[
              { value: 'in_stock', label: 'In Stock', icon: '+' },
              { value: 'out_of_stock', label: 'Out of Stock', icon: '-' },
              { value: 'unknown', label: 'Not Sure', icon: '?' },
            ].map((opt) => (
              <label
                key={opt.value}
                className={`report-option ${status === opt.value ? 'report-option--selected' : ''}`}
              >
                <input
                  type="radio"
                  name="status"
                  value={opt.value}
                  checked={status === opt.value}
                  onChange={() => setStatus(opt.value)}
                />
                <span>{opt.icon} {opt.label}</span>
              </label>
            ))}
          </div>
          {error && <p className="status error">{error}</p>}
          <div className="report-modal__actions">
            <button type="button" className="report-modal__cancel" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
