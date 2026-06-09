import { useEffect, useState } from 'react'
import { fetchModelOptions } from '../api'
import './ProgressiveFilters.css'

/**
 * Divulgation progressive des filtres une fois un modèle choisi.
 * Chaque étape apparaît en cascade (fadeUp) dès que la précédente est sélectionnée.
 *
 * Flux : variant → année → km → note → phase (si curée)
 *
 * Props :
 *   model         — modèle normalisé sélectionné
 *   variant       — finition actuelle (ou null)
 *   onVariant     — callback(variant|null)
 *   yearRange     — [min, max]
 *   onYearRange   — callback([min, max])
 *   mileageRange  — [min, max]
 *   onMileageRange— callback([min, max])
 *   sort          — { by, order }
 *   onSort        — callback(by, order)
 *   reliableOnly  — bool
 *   onReliable    — callback(bool)
 *   status        — string
 *   onStatus      — callback(string)
 *   eurJpy        — number|null
 */
export default function ProgressiveFilters({
  model,
  variant, onVariant,
  yearRange, onYearRange,
  mileageRange, onMileageRange,
  sort, onSort,
  reliableOnly, onReliable,
  status, onStatus,
  eurJpy,
}) {
  const [opts, setOpts] = useState(null)  // { variants, years, phases, generation_code }
  const [visibleStep, setVisibleStep] = useState(0)

  useEffect(() => {
    if (!model) { setOpts(null); setVisibleStep(0); return }
    setOpts(null)
    setVisibleStep(0)
    fetchModelOptions(model)
      .then(data => {
        setOpts(data)
        // Révéler les étapes une par une avec délai
        setTimeout(() => setVisibleStep(1), 80)
      })
      .catch(() => setOpts({ variants: [], years: {}, phases: [] }))
  }, [model])

  // Révèle l'étape suivante après sélection dans l'étape courante
  function advance(step) {
    if (visibleStep < step) setVisibleStep(step)
  }

  if (!opts) return null

  const hasVariants = opts.variants?.length > 0
  const hasPhases = opts.phases?.length > 0

  // Étapes actives :
  // 1 : variant (si dispo)
  // 2 : année
  // 3 : km
  // 4 : status
  // 5 : phase (si curé)
  // 6 : fiable

  const currentYear = new Date().getFullYear()

  return (
    <div className="prog-filters">

      {/* ÉTAPE 1 — Variant */}
      {hasVariants && visibleStep >= 1 && (
        <div className="pf-step" style={{ animationDelay: '0ms' }}>
          <span className="pf-label">Finition</span>
          <div className="pf-chips">
            <button
              className={`pf-chip ${!variant ? 'active' : ''}`}
              onClick={() => { onVariant(null); advance(2) }}
            >
              Toutes
            </button>
            {opts.variants.map(v => (
              <button
                key={v}
                className={`pf-chip ${variant === v ? 'active' : ''}`}
                onClick={() => { onVariant(v); advance(2) }}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Si pas de variants, passer direct à l'étape 2 */}
      {!hasVariants && visibleStep >= 1 && visibleStep < 2 && (
        <RevealTrigger onReveal={() => setVisibleStep(2)} />
      )}

      {/* ÉTAPE 2 — Année */}
      {visibleStep >= 2 && (
        <div className="pf-step" style={{ animationDelay: '0ms' }}>
          <span className="pf-label">Année</span>
          <div className="pf-range">
            <input
              type="number"
              className="pf-input"
              value={yearRange[0]}
              min={opts.years?.min || 1990}
              max={yearRange[1]}
              onChange={e => { onYearRange([+e.target.value, yearRange[1]]); advance(3) }}
            />
            <span className="pf-dash">–</span>
            <input
              type="number"
              className="pf-input"
              value={yearRange[1]}
              min={yearRange[0]}
              max={currentYear}
              onChange={e => { onYearRange([yearRange[0], +e.target.value]); advance(3) }}
            />
          </div>
        </div>
      )}

      {/* ÉTAPE 3 — km */}
      {visibleStep >= 3 && (
        <div className="pf-step" style={{ animationDelay: '0ms' }}>
          <span className="pf-label">km</span>
          <div className="pf-range">
            <input
              type="number"
              className="pf-input pf-input-wide"
              value={mileageRange[0]}
              min={0}
              max={mileageRange[1]}
              onChange={e => { onMileageRange([+e.target.value, mileageRange[1]]); advance(4) }}
            />
            <span className="pf-dash">–</span>
            <input
              type="number"
              className="pf-input pf-input-wide"
              value={mileageRange[1]}
              min={mileageRange[0]}
              max={500000}
              onChange={e => { onMileageRange([mileageRange[0], +e.target.value]); advance(4) }}
            />
          </div>
        </div>
      )}

      {/* ÉTAPE 4 — Statut */}
      {visibleStep >= 4 && (
        <div className="pf-step" style={{ animationDelay: '0ms' }}>
          <div className="pf-chips">
            {['all', 'sold', 'not_sold', 'canceled'].map(s => (
              <button
                key={s}
                className={`pf-chip ${status === s ? 'active' : ''}`}
                onClick={() => { onStatus(s); advance(5) }}
              >
                {s === 'all' ? 'Tous' : s === 'not_sold' ? 'Non vendu' : s === 'sold' ? 'Vendu' : 'Annulé'}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ÉTAPE 5 — Phase (si curé) */}
      {hasPhases && visibleStep >= 5 && (
        <div className="pf-step" style={{ animationDelay: '0ms' }}>
          <span className="pf-label">
            Phase
            {opts.generation_code && <span className="pf-gen">{opts.generation_code}</span>}
          </span>
          <div className="pf-chips">
            <button
              className={`pf-chip ${yearRange[0] <= 1990 ? 'active' : ''}`}
              onClick={() => { onYearRange([1990, currentYear]); advance(6) }}
            >
              Toutes
            </button>
            {opts.phases.map((ph, i) => {
              const isActive = yearRange[0] === ph.year_from && yearRange[1] === ph.year_to
              return (
                <button
                  key={i}
                  className={`pf-chip ${isActive ? 'active' : ''}`}
                  title={ph.note || ''}
                  onClick={() => {
                    onYearRange([ph.year_from, ph.year_to])
                    advance(6)
                  }}
                >
                  Ph.{ph.phase} ({ph.year_from}–{ph.year_to})
                  {ph.note && <span className="pf-chip-note">{ph.note}</span>}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ÉTAPE 6 — Options (fiables + taux) */}
      {visibleStep >= Math.max(4, hasPhases ? 6 : 5) && (
        <div className="pf-step pf-step-misc" style={{ animationDelay: '0ms' }}>
          <button
            className={`pf-chip ${reliableOnly ? 'active pf-chip-reliable' : ''}`}
            onClick={() => onReliable(v => !v)}
            title="N'afficher que les résultats dont l'année et le km sont fiables"
          >
            {reliableOnly ? '✓ Fiables' : 'Fiables'}
          </button>
          {eurJpy && <span className="pf-rate">1€ = ¥{eurJpy.toFixed(0)}</span>}
          <div className="pf-sort">
            {[
              { by: 'date',    label: 'Date' },
              { by: 'price',   label: 'Prix' },
              { by: 'mileage', label: 'km' },
            ].map(({ by, label }) => {
              const active = sort?.by === by
              const nextOrder = active && sort?.order === 'desc' ? 'asc' : 'desc'
              return (
                <button
                  key={by}
                  className={`pf-chip pf-sort-chip ${active ? 'active' : ''}`}
                  onClick={() => onSort(by, nextOrder)}
                >
                  {label}{active ? (sort.order === 'desc' ? ' ↓' : ' ↑') : ''}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

/** Helper interne : auto-advance dès le montage */
function RevealTrigger({ onReveal }) {
  useEffect(() => { onReveal() }, [])
  return null
}
