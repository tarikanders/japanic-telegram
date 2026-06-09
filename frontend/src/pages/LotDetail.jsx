import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchLot } from '../api'
import './LotDetail.css'

const STATUS_BADGE = {
  sold: { label: 'Sold', cls: 'badge-green' },
  not_sold: { label: 'Not Sold', cls: 'badge-red' },
  canceled: { label: 'Canceled', cls: 'badge-yellow' },
}

export default function LotDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lot, setLot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchLot(id)
      .then(setLot)
      .catch(e => setError(e.response?.data?.detail || 'Failed to load lot'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="lot-page">
      <div className="skeleton" style={{ height: 40, width: 200, marginBottom: 20 }} />
      <div className="lot-grid">
        <div className="skeleton" style={{ height: 280 }} />
        <div className="skeleton" style={{ height: 280 }} />
      </div>
    </div>
  )

  if (error) return (
    <div className="lot-page">
      <div className="error-state">
        <p>{error}</p>
        <button className="btn-back" onClick={() => navigate(-1)}>← Back</button>
      </div>
    </div>
  )

  if (!lot) return null

  const badge = STATUS_BADGE[lot.status] || { label: lot.status, cls: '' }

  return (
    <div className="lot-page">
      <button className="btn-back" onClick={() => navigate(-1)}>← Back to Search</button>

      <div className="lot-header">
        <div>
          <h1 className="lot-model">{lot.model}</h1>
          <div className="lot-meta">
            Lot #{lot.lot_number} · {lot.auction_date}
          </div>
        </div>
        <span className={`badge badge-lg ${badge.cls}`}>{badge.label}</span>
      </div>

      <div className="lot-grid">
        <div className="lot-card">
          <h2 className="section-title">Vehicle Details</h2>
          <div className="detail-rows">
            <div className="detail-row">
              <span>Model (raw)</span>
              <strong>{lot.model_raw || '—'}</strong>
            </div>
            <div className="detail-row">
              <span>Year</span>
              <strong>{lot.year || '—'}</strong>
            </div>
            <div className="detail-row">
              <span>Mileage</span>
              <strong>{lot.mileage_km ? `${lot.mileage_km.toLocaleString()} km` : '—'}</strong>
            </div>
            <div className="detail-row">
              <span>Start Price</span>
              <strong>{lot.start_price_eur ? `€${lot.start_price_eur.toLocaleString()}` : '—'}</strong>
            </div>
            {lot.variant && (
              <div className="detail-row">
                <span>Finition</span>
                <strong><span className="variant-badge">{lot.variant}</span></strong>
              </div>
            )}
            {lot.phase && (
              <div className="detail-row">
                <span>Phase</span>
                <strong className="phase-label">
                  {lot.phase.phase}
                  {lot.phase.generation_code && ` — ${lot.phase.generation_code}`}
                  {` (${lot.phase.year_from}–${lot.phase.year_to})`}
                </strong>
              </div>
            )}
            <div className="detail-row">
              <span>Note d'état</span>
              <strong title="Note OCR de la fiche-rapport japonaise (1–5, S, R, RA…)">
                {lot.condition_score || '—'}
              </strong>
            </div>
            <div className="detail-row highlight">
              <span>Final Price</span>
              <strong className="price-big">{lot.final_price_eur ? `€${lot.final_price_eur.toLocaleString()}` : '—'}</strong>
            </div>
            <div className="detail-row">
              <span>Status</span>
              <strong><span className={`badge ${badge.cls}`}>{badge.label}</span></strong>
            </div>
          </div>
        </div>

        {lot.telegram_message_id && (
          <div className="lot-card">
            <h2 className="section-title">Photos de l'annonce</h2>
            <p className="tg-photo-hint">
              Les photos de l'annonce originale (fiches japonaises, extérieur, intérieur)
              sont disponibles sur le canal Telegram.
            </p>
            <a
              className="tg-photo-link"
              href={`https://t.me/japanauctionjp/${lot.telegram_message_id}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Voir l'annonce Telegram →
            </a>
          </div>
        )}
      </div>

      {lot.similar?.length > 0 && (
        <div className="similar-section">
          <h2 className="section-title">Similar Sales ({lot.model} ±20k km)</h2>
          <div className="similar-grid">
            {lot.similar.map(s => {
              const sb = STATUS_BADGE[s.status] || { label: s.status, cls: '' }
              return (
                <div key={s.id} className="similar-card" onClick={() => navigate(`/lot/${s.id}`)}>
                  <div className="similar-price">
                    {s.final_price_eur ? `€${s.final_price_eur.toLocaleString()}` : '—'}
                  </div>
                  <div className="similar-meta">
                    {s.year || '?'} · {s.mileage_km ? `${(s.mileage_km/1000).toFixed(0)}k km` : '—'}
                  </div>
                  <div className="similar-date">{s.auction_date}</div>
                  <span className={`badge ${sb.cls}`}>{sb.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
