import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchWatchlist, fetchExchangeRate, fetchLbcSearch } from '../api'
import './Watchlist.css'

function lbcUrl(query) {
  return `https://www.leboncoin.fr/recherche?category=2&text=${encodeURIComponent(query)}`
}

function WatchlistCard({ entry, eurJpy }) {
  const [lbc, setLbc] = useState(null)
  const [lbcLoading, setLbcLoading] = useState(false)
  const navigate = useNavigate()

  const bidToEur = (yen) => eurJpy ? Math.round(yen / eurJpy) : null

  const loadLbc = async () => {
    if (!entry.lbc_query || lbcLoading) return
    setLbcLoading(true)
    try {
      const data = await fetchLbcSearch(entry.lbc_query, entry.lbc_filters || {})
      if (!data.stats?.total && !data.ads?.length) {
        setLbc({ blocked: true })
      } else {
        setLbc(data)
      }
    } catch {
      setLbc({ error: true })
    } finally {
      setLbcLoading(false)
    }
  }

  return (
    <div className="wl-card">
      <div className="wl-card-header">
        <div>
          <span className="wl-model">{entry.model_name}</span>
          {entry.generation_code && <span className="wl-gen">{entry.generation_code}</span>}
        </div>
        <span className="wl-years">{entry.year_start}–{entry.year_end}</span>
      </div>

      {entry.phases.length > 0 && (
        <div className="wl-phases">
          {entry.phases.map((p, i) => (
            <div key={i} className="wl-phase">
              <span className="phase-label">Phase {p.phase}</span>
              <span className="phase-years">{p.year_from}–{p.year_to}</span>
              {p.note && <span className="phase-note">{p.note}</span>}
            </div>
          ))}
        </div>
      )}

      {entry.variants.length > 0 && (
        <div className="wl-variants">
          {entry.variants.map((v, i) => (
            <span key={i} className="variant-chip">
              {v.name}{v.hp ? ` · ${v.hp}ch` : ''}{v.note ? ` · ${v.note}` : ''}
            </span>
          ))}
        </div>
      )}

      <div className="wl-prices">
        <div className="wl-price-block">
          <span className="wl-price-label">Ref LBC</span>
          <span className="wl-price-value lbc-price">
            {entry.lbc_price_eur ? `€${entry.lbc_price_eur.toLocaleString()}` : '—'}
            {entry.lbc_price_note && <span className="price-note"> ({entry.lbc_price_note})</span>}
          </span>
        </div>

        {lbc && !lbc.error && lbc.stats?.avg && (
          <div className="wl-price-block lbc-live-row">
            <span className="wl-price-label">LBC live <span className="live-dot">●</span></span>
            <span className="wl-price-value lbc-live">
              avg €{lbc.stats.avg.toLocaleString()}
              <span className="price-note"> ({lbc.stats.count} annonces / {lbc.stats.total} total)</span>
            </span>
          </div>
        )}
        {lbc && !lbc.error && lbc.stats?.min && (
          <div className="wl-price-block">
            <span className="wl-price-label">Fourchette LBC</span>
            <span className="wl-price-value" style={{ color: 'var(--text-secondary)' }}>
              €{lbc.stats.min.toLocaleString()} – €{lbc.stats.max.toLocaleString()}
            </span>
          </div>
        )}
        {(lbc?.error || lbc?.blocked) && (
          <div className="wl-lbc-error">
            {lbc?.blocked
              ? 'LBC bloque cette IP (cloud) — lance le service en local sur ton PC'
              : 'Erreur de connexion au service LBC'}
          </div>
        )}

        <div className="wl-price-block">
          <span className="wl-price-label">Bid max</span>
          <span className="wl-price-value bid-price">
            {entry.bid_max ? (
              <>
                ¥{entry.bid_min ? `${entry.bid_min.toLocaleString()}–` : ''}{entry.bid_max.toLocaleString()}
                {eurJpy && entry.bid_max && (
                  <span className="bid-eur"> ≈ €{bidToEur(entry.bid_max).toLocaleString()}</span>
                )}
              </>
            ) : '—'}
          </span>
        </div>

        {entry.auction_sold_count > 0 && (
          <div className="wl-price-block">
            <span className="wl-price-label">Moy enchère DB</span>
            <span className="wl-price-value auction-avg">
              {entry.auction_avg_eur ? `€${entry.auction_avg_eur.toLocaleString()}` : '—'}
              <span className="sold-count"> ({entry.auction_sold_count} ventes)</span>
            </span>
          </div>
        )}
      </div>

      <div className="wl-actions">
        {entry.lbc_query && (
          <button
            className={`wl-btn wl-btn-refresh ${lbcLoading ? 'loading' : ''}`}
            onClick={loadLbc}
            disabled={lbcLoading}
          >
            {lbcLoading ? '...' : lbc ? '↻ Refresh LBC' : 'Prix LBC live'}
          </button>
        )}
        {entry.lbc_query && (
          <a
            href={lbcUrl(entry.lbc_query)}
            target="_blank"
            rel="noopener noreferrer"
            className="wl-btn wl-btn-lbc"
            onClick={ev => ev.stopPropagation()}
          >
            LeBonCoin →
          </a>
        )}
        {entry.auction_model_key && (
          <button
            className="wl-btn wl-btn-search"
            onClick={() => navigate(`/?model=${encodeURIComponent(entry.auction_model_key)}`)}
          >
            DB →
          </button>
        )}
      </div>

      {lbc && !lbc.error && lbc.ads?.length > 0 && (
        <div className="lbc-ads-preview">
          {lbc.ads.slice(0, 4).map(ad => (
            <a key={ad.id} href={ad.url} target="_blank" rel="noopener noreferrer" className="lbc-ad-item">
              <span className="lbc-ad-title">{ad.title}</span>
              <span className="lbc-ad-meta">{ad.year} · {ad.mileage} · {ad.city}</span>
              <span className="lbc-ad-price">€{ad.price?.toLocaleString()}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Watchlist() {
  const [entries, setEntries] = useState([])
  const [eurJpy, setEurJpy] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([fetchWatchlist(), fetchExchangeRate()])
      .then(([w, r]) => { setEntries(w); setEurJpy(r.EUR_JPY) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="watchlist-page">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton wl-skeleton" />
        ))}
      </div>
    )
  }

  return (
    <div className="watchlist-page">
      <div className="wl-header">
        <h1 className="wl-title">Watchlist</h1>
        {eurJpy && <span className="wl-rate">1€ = ¥{eurJpy.toFixed(0)}</span>}
        <span className="wl-hint">Cliquez "Prix LBC live" pour récupérer les prix actuels</span>
      </div>
      <div className="wl-grid">
        {entries.map(e => (
          <WatchlistCard key={e.id} entry={e} eurJpy={eurJpy} />
        ))}
      </div>
    </div>
  )
}
