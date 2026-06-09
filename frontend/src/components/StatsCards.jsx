import './StatsCards.css'

export default function StatsCards({ stats, loading }) {
  if (loading) {
    return (
      <div className="stats-strip">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="stats-item">
            <div className="skeleton" style={{ height: 28, width: 80, marginBottom: 6 }} />
            <div className="skeleton" style={{ height: 10, width: 55 }} />
          </div>
        ))}
      </div>
    )
  }

  const s = stats
  const items = [
    {
      label: 'Prix moyen',
      value: s?.avg_price != null ? `€${s.avg_price.toLocaleString()}` : '—',
      accent: 'indigo',
    },
    {
      label: 'Médiane',
      value: s?.median_price != null ? `€${s.median_price.toLocaleString()}` : '—',
    },
    {
      label: 'Fourchette',
      value: s?.min_price != null ? `€${s.min_price.toLocaleString()} – €${s.max_price.toLocaleString()}` : '—',
      small: true,
    },
    {
      label: 'Taux vendu',
      value: s?.sold_rate != null ? `${s.sold_rate}%` : '—',
      accent: s?.sold_rate > 60 ? 'green' : s?.sold_rate > 40 ? 'amber' : 'red',
    },
    {
      label: 'Résultats',
      value: s?.count != null ? s.count.toLocaleString() : '—',
    },
  ]

  return (
    <div className="stats-strip">
      {items.map((item, i) => (
        <div key={item.label} className="stats-item">
          <span className={`stats-val num${item.accent ? ` stats-val--${item.accent}` : ''}${item.small ? ' stats-val--sm' : ''}`}>
            {item.value}
          </span>
          <span className="stats-lbl">{item.label}</span>
        </div>
      ))}
    </div>
  )
}
