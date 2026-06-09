import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import './Charts.css'

const STATUS_COLOR = { sold: '#7c3aed', not_sold: '#ec4899', canceled: '#d97706' }

const PriceTip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="tip-model">{d.model}</div>
      <div className="tip-row"><span>Lot</span><strong>{d.lot}</strong></div>
      <div className="tip-row"><span>Mileage</span><strong>{(d.mileage / 1000).toFixed(0)}k km</strong></div>
      <div className="tip-row"><span>Price</span><strong>€{d.price?.toLocaleString()}</strong></div>
      <div className="tip-row"><span>Status</span><strong style={{ color: STATUS_COLOR[d.status] }}>{d.status}</strong></div>
    </div>
  )
}

const LineTip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="tip-model">{label}</div>
      {payload.map(p => (
        <div key={p.name} className="tip-row">
          <span>{p.name}</span>
          <strong style={{ color: p.color }}>€{p.value?.toLocaleString()}</strong>
        </div>
      ))}
    </div>
  )
}

export function PriceScatter({ data = [], loading }) {
  const navigate = useNavigate()

  const scatterData = data.map(d => ({
    mileage: d.mileage,
    price: d.price,
    model: d.model,
    lot: d.lot,
    status: d.status,
    id: d.id,
    fill: STATUS_COLOR[d.status] || '#3b82f6',
  }))

  if (loading) return <div className="skeleton chart-skeleton" />

  return (
    <div className="chart-card">
      <h3 className="chart-title">Price vs Mileage</h3>
      <div className="chart-legend">
        {Object.entries(STATUS_COLOR).map(([k, v]) => (
          <span key={k} className="legend-item">
            <span className="legend-dot" style={{ background: v }} />
            {k.replace('_', ' ')}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.08)" />
          <XAxis
            dataKey="mileage"
            type="number"
            name="Mileage"
            tickFormatter={v => `${(v/1000).toFixed(0)}k`}
            tick={{ fill: '#a89dc8', fontSize: 11 }}
            axisLine={false} tickLine={false}
            label={{ value: 'km', position: 'insideRight', offset: -4, fill: '#a89dc8', fontSize: 11 }}
          />
          <YAxis
            dataKey="price"
            type="number"
            name="Price"
            tickFormatter={v => `€${(v/1000).toFixed(0)}k`}
            tick={{ fill: '#a89dc8', fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <Tooltip content={<PriceTip />} cursor={{ strokeDasharray: '3 3', stroke: 'rgba(124,58,237,0.2)' }} />
          <Scatter
            data={scatterData}
            onClick={(d) => d.id && navigate(`/lot/${d.id}`)}
            style={{ cursor: 'pointer' }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

export function PriceTrend({ data = [], loading }) {
  if (loading) return <div className="skeleton chart-skeleton" />

  return (
    <div className="chart-card">
      <h3 className="chart-title">Price Trend Over Time</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(124,58,237,0.08)" />
          <XAxis dataKey="date" tick={{ fill: '#a89dc8', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis
            tickFormatter={v => `€${(v/1000).toFixed(0)}k`}
            tick={{ fill: '#a89dc8', fontSize: 11 }}
            axisLine={false} tickLine={false}
          />
          <Tooltip content={<LineTip />} />
          <Legend wrapperStyle={{ fontSize: 12, color: '#6b5fa0' }} />
          <Line
            type="monotone"
            dataKey="avg_price"
            name="Avg Price"
            stroke="#7c3aed"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: '#7c3aed', stroke: '#fff', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
