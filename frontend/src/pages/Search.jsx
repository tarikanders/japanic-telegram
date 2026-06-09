import { useState, useEffect, useCallback, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { fetchModels, fetchSearch, fetchStats, fetchExchangeRate, fetchModelOptions } from '../api'
import StatsCards from '../components/StatsCards'
import ResultsTable from '../components/ResultsTable'
import './Search.css'

const ANNOUNCE_FLOOR = '2025-01-01'
const LS_KEY = 'jpn_search'

const MULTI_WORD_BRANDS = ['Mercedes-Benz', 'Alfa Romeo', 'Rolls-Royce', 'Aston Martin', 'Land Rover', 'De Tomaso']
const BRAND_ORDER = ['Porsche', 'BMW', 'Mercedes-Benz', 'Maserati', 'Ferrari', 'Lamborghini', 'Audi', 'McLaren', 'Bentley', 'Rolls-Royce', 'Jaguar', 'Honda', 'Nissan', 'Toyota', 'Lexus']

function getBrandOf(model) {
  const multi = MULTI_WORD_BRANDS.find(b => model.startsWith(b + ' ') || model === b)
  return multi || model.split(' ')[0]
}

function extractBrands(models) {
  const counts = {}
  models.forEach(m => { const b = getBrandOf(m); counts[b] = (counts[b] || 0) + 1 })
  return Object.keys(counts).sort((a, b) => {
    const ia = BRAND_ORDER.indexOf(a), ib = BRAND_ORDER.indexOf(b)
    if (ia !== -1 && ib !== -1) return ia - ib
    if (ia !== -1) return -1
    if (ib !== -1) return 1
    return counts[b] - counts[a]
  })
}

function modelsForBrand(models, brand) {
  return models
    .filter(m => getBrandOf(m) === brand)
    .map(m => m.slice(brand.length + 1))
    .sort()
}

const S = { BRAND: 0, MODEL: 1, FINITION: 2, YEAR: 3, KM: 4, RESULTS: 5 }

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || 'null') } catch { return null }
}

export default function Search() {
  const saved = loadSaved()
  const currentYear = new Date().getFullYear()
  const location = useLocation()
  const isFirstMount = useRef(true)

  const [models, setModels] = useState([])
  const [eurJpy, setEurJpy] = useState(null)
  const [brand, setBrand] = useState(saved?.brand || '')
  const [model, setModel] = useState(saved?.model || '')
  const [variant, setVariant] = useState(saved?.variant || null)
  const [yearRange, setYearRange] = useState(saved?.yearRange || [1990, currentYear])
  const [mileageRange, setMileageRange] = useState(saved?.mileageRange || [0, 300000])
  const [step, setStep] = useState(saved?.step ?? S.BRAND)
  const [opts, setOpts] = useState(null)
  const optCache = useRef({})
  const [sort, setSort] = useState({ by: 'date', order: 'desc' })
  const [page, setPage] = useState(1)
  const [stats, setStats] = useState(null)
  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [loadingStats, setLoadingStats] = useState(false)
  const [loadingResults, setLoadingResults] = useState(false)

  useEffect(() => {
    fetchModels().then(setModels).catch(() => {})
    fetchExchangeRate().then(d => setEurJpy(d.EUR_JPY)).catch(() => {})
  }, [])

  // Logo click → reset
  useEffect(() => {
    if (isFirstMount.current) { isFirstMount.current = false; return }
    resetSearch()
  }, [location.key])

  // Prefetch toutes les options des modèles d'une marque dès que le step MODEL s'affiche
  useEffect(() => {
    if (step !== S.MODEL || !brand || !models.length) return
    modelsForBrand(models, brand).forEach(label => {
      const full = brand + ' ' + label
      if (optCache.current[full]) return
      optCache.current[full] = 'loading'
      fetchModelOptions(full)
        .then(data => { optCache.current[full] = data })
        .catch(() => { delete optCache.current[full] })
    })
  }, [step, brand, models])

  useEffect(() => {
    if (!model) { setOpts(null); return }
    const cached = optCache.current[model]
    if (cached && cached !== 'loading') { setOpts(cached); return }
    fetchModelOptions(model)
      .then(data => { optCache.current[model] = data; setOpts(data) })
      .catch(() => setOpts({ variants: [], years: {}, phases: [] }))
  }, [model])

  // Auto-skip finition si aucune variante
  useEffect(() => {
    if (step === S.FINITION && opts !== null && opts.variants.length === 0) {
      setStep(S.YEAR)
    }
  }, [step, opts])

  // Persist
  useEffect(() => {
    if (!model) { localStorage.removeItem(LS_KEY); return }
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ brand, model, variant, yearRange, mileageRange, step }))
    } catch {}
  }, [brand, model, variant, yearRange, mileageRange, step])

  const params = {
    model: model || undefined,
    variant: variant || undefined,
    mileage_min: mileageRange[0] > 0 ? mileageRange[0] : undefined,
    mileage_max: mileageRange[1] < 300000 ? mileageRange[1] : undefined,
    date_from: ANNOUNCE_FLOOR,
    year_min: yearRange[0] > 1990 ? yearRange[0] : undefined,
    year_max: yearRange[1] < currentYear ? yearRange[1] : undefined,
  }

  const doSearch = useCallback((p = 1, s = sort) => {
    if (!model) return
    setLoadingResults(true)
    fetchSearch({ ...params, page: p, per_page: 50, sort_by: s.by, sort_order: s.order })
      .then(data => { setResults(data.results); setTotal(data.total) })
      .catch(() => {})
      .finally(() => setLoadingResults(false))
  }, [model, variant, mileageRange, yearRange, sort])

  const doStats = useCallback(() => {
    if (!model) return
    setLoadingStats(true)
    fetchStats(params).then(setStats).catch(() => {}).finally(() => setLoadingStats(false))
  }, [model, variant, mileageRange, yearRange])

  // Pas de debounce — le wizard change les filtres d'un coup, pas en continu
  useEffect(() => {
    if (step !== S.RESULTS) return
    doSearch(1, sort); setPage(1); doStats()
  }, [model, variant, mileageRange, yearRange, step])

  const resetSearch = () => {
    setBrand(''); setModel(''); setVariant(null); setStep(S.BRAND)
    setYearRange([1990, currentYear]); setMileageRange([0, 300000])
    setOpts(null); setResults([]); setStats(null)
    localStorage.removeItem(LS_KEY)
  }

  const handleBrandSelect = (b) => {
    setBrand(b); setModel(''); setVariant(null)
    setYearRange([1990, currentYear]); setMileageRange([0, 300000])
    setOpts(null); setStep(S.MODEL)
  }

  const handleModelChip = (label) => {
    const fullModel = brand + ' ' + label
    const cached = optCache.current[fullModel]
    setModel(fullModel)
    setVariant(null)
    setOpts(cached && cached !== 'loading' ? cached : null)
    setStep(S.FINITION)
  }

  const handlePage = (p) => { setPage(p); doSearch(p, sort) }
  const handleSort = (by, order) => {
    const s = { by, order }; setSort(s); setPage(1); doSearch(1, s)
  }

  const filterChips = [
    variant ? { label: variant, step: S.FINITION } : null,
    (yearRange[0] > 1990 || yearRange[1] < currentYear)
      ? { label: `${yearRange[0]}–${yearRange[1]}`, step: S.YEAR } : null,
    mileageRange[1] < 300000
      ? { label: `≤ ${(mileageRange[1] / 1000).toFixed(0)}k km`, step: S.KM } : null,
  ].filter(Boolean)

  const brands = extractBrands(models)
  const brandModels = brand ? modelsForBrand(models, brand) : []

  // ── STEP 0 : Marque ──────────────────────────────────────────────────────
  if (step === S.BRAND) {
    return (
      <div className="search-hero">
        <p className="hero-title">Enchères japonaises — Données 2025</p>
        <WizardCard question="Quelle marque ?">
          {models.length === 0
            ? <div className="wiz-pulse" />
            : <div className="wiz-brand-grid">
                {brands.map(b => (
                  <button key={b} className="wiz-brand-chip" onClick={() => handleBrandSelect(b)}>{b}</button>
                ))}
              </div>
          }
        </WizardCard>
      </div>
    )
  }

  // ── STEP 1 : Modèle ──────────────────────────────────────────────────────
  if (step === S.MODEL) {
    return (
      <div className="search-hero">
        <WizardCard tag={brand} question="Quel modèle ?" onBack={() => setStep(S.BRAND)}>
          {brandModels.length === 0
            ? <div className="wiz-pulse" />
            : <div className="wiz-model-grid">
                {brandModels.map(label => (
                  <button key={label} className="wiz-model-chip" onClick={() => handleModelChip(label)}>
                    {label}
                  </button>
                ))}
              </div>
          }
        </WizardCard>
      </div>
    )
  }

  // ── STEP 2 : Finition ────────────────────────────────────────────────────
  if (step === S.FINITION) {
    if (!opts) return (
      <div className="search-hero">
        <div className="wiz-loading">
          <p className="wiz-model-tag">{model}</p>
          <div className="wiz-pulse" />
        </div>
      </div>
    )
    return (
      <div className="search-hero">
        <WizardCard
          tag={model} question="Quelle finition ?"
          onBack={() => setStep(S.MODEL)}
          onSkip={() => { setVariant(null); setStep(S.YEAR) }}
        >
          <div className="wiz-chips">
            {opts.variants.map(v => (
              <button key={v}
                className={`wiz-chip${variant === v ? ' active' : ''}`}
                onClick={() => setVariant(variant === v ? null : v)}
              >{v}</button>
            ))}
          </div>
          <button className="wiz-next" onClick={() => setStep(S.YEAR)}>Suivant →</button>
        </WizardCard>
      </div>
    )
  }

  // ── STEP 3 : Année ───────────────────────────────────────────────────────
  if (step === S.YEAR) {
    const yMin = opts?.years?.min || 1990
    const yMax = opts?.years?.max || currentYear
    const prevStep = opts?.variants?.length > 0 ? S.FINITION : S.MODEL
    return (
      <div className="search-hero">
        <WizardCard
          tag={model + (variant ? ` · ${variant}` : '')}
          question="Quelle année ?"
          onBack={() => setStep(prevStep)}
          onSkip={() => { setYearRange([1990, currentYear]); setStep(S.KM) }}
        >
          <div className="wiz-range">
            <input type="number" className="wiz-input"
              value={yearRange[0]} min={yMin} max={yearRange[1]}
              onChange={e => setYearRange([+e.target.value, yearRange[1]])} />
            <span className="wiz-dash">–</span>
            <input type="number" className="wiz-input"
              value={yearRange[1]} min={yearRange[0]} max={yMax}
              onChange={e => setYearRange([yearRange[0], +e.target.value])} />
          </div>
          <p className="wiz-hint">Disponible : {yMin} – {yMax}</p>
          <button className="wiz-next" onClick={() => setStep(S.KM)}>Suivant →</button>
        </WizardCard>
      </div>
    )
  }

  // ── STEP 4 : Kilométrage ─────────────────────────────────────────────────
  if (step === S.KM) {
    const KM_PRESETS = [50000, 80000, 100000, 150000, 200000]
    return (
      <div className="search-hero">
        <WizardCard
          tag={model + (variant ? ` · ${variant}` : '')}
          question="Kilométrage max ?"
          onBack={() => setStep(S.YEAR)}
          onSkip={() => { setMileageRange([0, 300000]); setStep(S.RESULTS) }}
        >
          <div className="wiz-chips">
            {KM_PRESETS.map(km => (
              <button key={km}
                className={`wiz-chip${mileageRange[1] === km ? ' active' : ''}`}
                onClick={() => setMileageRange([0, km])}
              >{km / 1000}k</button>
            ))}
            <button
              className={`wiz-chip${mileageRange[1] >= 300000 ? ' active' : ''}`}
              onClick={() => setMileageRange([0, 300000])}
            >Tous</button>
          </div>
          <button className="wiz-next" onClick={() => setStep(S.RESULTS)}>
            Voir les résultats →
          </button>
        </WizardCard>
      </div>
    )
  }

  // ── STEP 5 : Résultats ───────────────────────────────────────────────────
  return (
    <div className="search-results">
      <div className="results-topbar">
        <button className="results-clear" onClick={resetSearch}>← Nouvelle recherche</button>
        <span className="results-model-name">{model}</span>
        <div className="results-filter-row">
          {filterChips.map(c => (
            <button key={c.label} className="rf-chip" onClick={() => setStep(c.step)}>{c.label} ×</button>
          ))}
          <button className="rf-edit" onClick={() => setStep(S.FINITION)}>Modifier les filtres</button>
        </div>
      </div>

      <StatsCards stats={stats} loading={loadingStats} />

      <ResultsTable
        results={results} total={total} page={page} perPage={50}
        onPageChange={handlePage} loading={loadingResults}
        sort={sort} onSort={handleSort} eurJpy={eurJpy}
      />
    </div>
  )
}

function WizardCard({ tag, question, onBack, onSkip, children }) {
  return (
    <div className="wiz-card">
      {tag && <p className="wiz-model-tag">{tag}</p>}
      <h2 className="wiz-question">{question}</h2>
      {children}
      {(onBack || onSkip) && (
        <div className="wiz-actions">
          {onBack && <button className="wiz-back" onClick={onBack}>← Retour</button>}
          {onSkip && <button className="wiz-skip" onClick={onSkip}>Passer</button>}
        </div>
      )}
    </div>
  )
}
