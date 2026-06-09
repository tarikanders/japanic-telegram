import { useNavigate } from 'react-router-dom'
import './ResultsTable.css'

const STATUS_BADGE = {
  sold: { label: 'Sold', cls: 'badge-green' },
  not_sold: { label: 'Not Sold', cls: 'badge-red' },
  canceled: { label: 'Canceled', cls: 'badge-yellow' },
}

function SortHeader({ col, sort, onSort, children }) {
  const active = sort?.by === col
  const nextOrder = active && sort?.order === 'desc' ? 'asc' : 'desc'
  return (
    <th className={`sortable-th ${active ? 'sort-active' : ''}`} onClick={() => onSort(col, nextOrder)}>
      {children}
      <span className="sort-arrow">{active ? (sort.order === 'desc' ? ' ↓' : ' ↑') : ' ↕'}</span>
    </th>
  )
}

export default function ResultsTable({ results = [], total, page, perPage, onPageChange, loading, sort, onSort, eurJpy }) {
  const navigate = useNavigate()
  const totalPages = Math.ceil(total / perPage)

  if (loading) {
    return (
      <div className="table-wrap">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 44, marginBottom: 4 }} />
        ))}
      </div>
    )
  }

  if (!results.length) {
    return (
      <div className="table-empty">
        <div className="empty-icon">🔍</div>
        <p>No results found. Try adjusting your filters.</p>
      </div>
    )
  }

  return (
    <div className="table-section">
      <div className="table-header-row">
        <span className="table-count">{total.toLocaleString()} results</span>
        <span className="table-pagination">Page {page} of {totalPages}</span>
      </div>
      <div className="table-wrap">
        <table className="results-table">
          <thead>
            <tr>
              <th>Lot#</th>
              <SortHeader col="date" sort={sort} onSort={onSort}>Date</SortHeader>
              <th>Modèle</th>
              <th title="Finition / Variant (GTS, GT4, Turbo S…)">Finition</th>
              <th>Année</th>
              <th title="Note d'état OCR (fiche-rapport japonaise)">Note</th>
              <SortHeader col="mileage" sort={sort} onSort={onSort}>km</SortHeader>
              <th>Départ</th>
              <SortHeader col="price" sort={sort} onSort={onSort}>Final €</SortHeader>
              {eurJpy && <th className="yen-col">Final ¥</th>}
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {results.map(r => {
              const badge = STATUS_BADGE[r.status] || { label: r.status, cls: '' }
              const finalYen = eurJpy && r.final_price_eur ? Math.round(r.final_price_eur * eurJpy) : null
              const isHighConf = r.match_confidence === 'high'
              return (
                <tr key={r.id} className="result-row" onClick={() => navigate(`/lot/${r.id}`)}>
                  <td className="lot-num">{r.lot_number || '—'}</td>
                  <td>{r.auction_date || '—'}</td>
                  <td className="model-cell">{r.model || '—'}</td>
                  <td className="variant-cell">
                    {r.variant
                      ? <span className="variant-badge">{r.variant}</span>
                      : <span className="text-muted">—</span>}
                  </td>
                  <td className="year-cell">
                    {r.year || '—'}
                    {isHighConf && <span className="conf-dot" title="Année et km vérifiés" />}
                  </td>
                  <td className="score-cell" title="Note d'état OCR">
                    {r.condition_score || '—'}
                  </td>
                  <td>{r.mileage_km ? `${(r.mileage_km / 1000).toFixed(0)}k` : '—'}</td>
                  <td>{r.start_price_eur ? `€${r.start_price_eur.toLocaleString()}` : '—'}</td>
                  <td className="price-final">{r.final_price_eur ? `€${r.final_price_eur.toLocaleString()}` : '—'}</td>
                  {eurJpy && <td className="price-yen">{finalYen ? `¥${finalYen.toLocaleString()}` : '—'}</td>}
                  <td><span className={`badge ${badge.cls}`}>{badge.label}</span></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="page-btn">← Prev</button>
          <div className="page-numbers">
            {[...Array(Math.min(totalPages, 7))].map((_, i) => {
              const p = i + 1
              return (
                <button key={p} className={`page-btn ${p === page ? 'active' : ''}`} onClick={() => onPageChange(p)}>
                  {p}
                </button>
              )
            })}
          </div>
          <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} className="page-btn">Next →</button>
        </div>
      )}
    </div>
  )
}
