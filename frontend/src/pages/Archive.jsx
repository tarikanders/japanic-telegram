import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchArchive, addToArchive, updateArchiveEntry, deleteArchiveEntry } from '../api'
import './Archive.css'

const STATUS_LABELS = { bought: 'Acheté', passed: 'Passé', reference: 'Référence' }
const STATUS_FILTERS = [
  { key: 'all', label: 'Tous' },
  { key: 'bought', label: 'Achetés' },
  { key: 'passed', label: 'Passés' },
  { key: 'reference', label: 'Référence' },
]

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function ArchiveCard({ entry, onDelete, onUpdate }) {
  const [editingNotes, setEditingNotes] = useState(false)
  const [notes, setNotes] = useState(entry.notes || '')
  const [saving, setSaving] = useState(false)
  const textareaRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (editingNotes && textareaRef.current) textareaRef.current.focus()
  }, [editingNotes])

  const saveNotes = async () => {
    setSaving(true)
    try {
      const updated = await updateArchiveEntry(entry.id, { notes })
      onUpdate(updated)
    } finally {
      setSaving(false)
      setEditingNotes(false)
    }
  }

  const changeStatus = async (status) => {
    const updated = await updateArchiveEntry(entry.id, { archive_status: status })
    onUpdate(updated)
  }

  return (
    <div className={`arc-card arc-status-${entry.archive_status}`}>
      <div className="arc-card-header">
        <div className="arc-card-title">
          <span className="arc-model">{entry.model_name}</span>
          {entry.generation_code && <span className="arc-gen">{entry.generation_code}</span>}
          {(entry.year_start || entry.year_end) && (
            <span className="arc-years">{entry.year_start}–{entry.year_end}</span>
          )}
        </div>
        <div className="arc-card-meta">
          <span className={`arc-badge arc-badge-${entry.archive_status}`}>
            {STATUS_LABELS[entry.archive_status] || entry.archive_status}
          </span>
          <button className="arc-delete" onClick={() => onDelete(entry.id)} title="Supprimer de l'archive">✕</button>
        </div>
      </div>

      {(entry.bid_price_eur || entry.bid_price_yen || entry.lbc_price_eur) && (
        <div className="arc-prices">
          {entry.bid_price_eur && (
            <div className="arc-price-row">
              <span className="arc-price-label">Enchère</span>
              <span className="arc-price-val arc-price-bid">€{entry.bid_price_eur.toLocaleString()}</span>
            </div>
          )}
          {entry.bid_price_yen && !entry.bid_price_eur && (
            <div className="arc-price-row">
              <span className="arc-price-label">Enchère</span>
              <span className="arc-price-val arc-price-bid">¥{entry.bid_price_yen.toLocaleString()}</span>
            </div>
          )}
          {entry.lbc_price_eur && (
            <div className="arc-price-row">
              <span className="arc-price-label">Ref LBC</span>
              <span className="arc-price-val arc-price-lbc">€{entry.lbc_price_eur.toLocaleString()}</span>
            </div>
          )}
        </div>
      )}

      <div className="arc-notes-section">
        {editingNotes ? (
          <div className="arc-notes-edit">
            <textarea
              ref={textareaRef}
              className="arc-notes-input"
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Notes..."
              rows={3}
            />
            <div className="arc-notes-edit-actions">
              <button className="arc-btn arc-btn-save" onClick={saveNotes} disabled={saving}>
                {saving ? '...' : 'Sauvegarder'}
              </button>
              <button className="arc-btn arc-btn-cancel" onClick={() => { setNotes(entry.notes || ''); setEditingNotes(false) }}>
                Annuler
              </button>
            </div>
          </div>
        ) : (
          <div className="arc-notes-display" onClick={() => setEditingNotes(true)}>
            {notes
              ? <span className="arc-notes-text">{notes}</span>
              : <span className="arc-notes-empty">+ Ajouter une note...</span>
            }
          </div>
        )}
      </div>

      <div className="arc-footer">
        <span className="arc-date">{formatDate(entry.archived_at)}</span>
        <div className="arc-actions">
          <select
            className="arc-status-select"
            value={entry.archive_status}
            onChange={e => changeStatus(e.target.value)}
          >
            <option value="reference">Référence</option>
            <option value="bought">Acheté</option>
            <option value="passed">Passé</option>
          </select>
          {entry.auction_model_key && (
            <button
              className="arc-btn arc-btn-db"
              onClick={() => navigate(`/?model=${encodeURIComponent(entry.auction_model_key)}`)}
            >
              DB →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const EMPTY_FORM = {
  model_name: '',
  generation_code: '',
  year_start: '',
  year_end: '',
  notes: '',
  archive_status: 'reference',
  lbc_price_eur: '',
  bid_price_yen: '',
  bid_price_eur: '',
  auction_model_key: '',
}

function AddModal({ onClose, onAdd }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.model_name.trim()) return
    setSaving(true)
    try {
      const payload = {
        ...form,
        year_start: form.year_start ? parseInt(form.year_start) : null,
        year_end: form.year_end ? parseInt(form.year_end) : null,
        lbc_price_eur: form.lbc_price_eur ? parseInt(form.lbc_price_eur) : null,
        bid_price_yen: form.bid_price_yen ? parseInt(form.bid_price_yen) : null,
        bid_price_eur: form.bid_price_eur ? parseInt(form.bid_price_eur) : null,
        generation_code: form.generation_code || null,
        auction_model_key: form.auction_model_key || null,
        notes: form.notes || null,
        phases: [],
        variants: [],
      }
      const created = await addToArchive(payload)
      onAdd(created)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="arc-modal-overlay" onClick={onClose}>
      <div className="arc-modal" onClick={e => e.stopPropagation()}>
        <div className="arc-modal-header">
          <h2 className="arc-modal-title">Archiver un véhicule</h2>
          <button className="arc-modal-close" onClick={onClose}>✕</button>
        </div>
        <form className="arc-form" onSubmit={submit}>
          <div className="arc-form-row">
            <div className="arc-form-group arc-form-group-wide">
              <label>Modèle *</label>
              <input value={form.model_name} onChange={e => set('model_name', e.target.value)} placeholder="ex: BMW M3" required />
            </div>
            <div className="arc-form-group">
              <label>Génération</label>
              <input value={form.generation_code} onChange={e => set('generation_code', e.target.value)} placeholder="ex: E92" />
            </div>
          </div>
          <div className="arc-form-row">
            <div className="arc-form-group">
              <label>Année début</label>
              <input type="number" value={form.year_start} onChange={e => set('year_start', e.target.value)} placeholder="2007" min="1950" max="2030" />
            </div>
            <div className="arc-form-group">
              <label>Année fin</label>
              <input type="number" value={form.year_end} onChange={e => set('year_end', e.target.value)} placeholder="2012" min="1950" max="2030" />
            </div>
            <div className="arc-form-group">
              <label>Statut</label>
              <select value={form.archive_status} onChange={e => set('archive_status', e.target.value)}>
                <option value="reference">Référence</option>
                <option value="bought">Acheté</option>
                <option value="passed">Passé</option>
              </select>
            </div>
          </div>
          <div className="arc-form-row">
            <div className="arc-form-group">
              <label>Prix enchère (€)</label>
              <input type="number" value={form.bid_price_eur} onChange={e => set('bid_price_eur', e.target.value)} placeholder="18000" />
            </div>
            <div className="arc-form-group">
              <label>Prix enchère (¥)</label>
              <input type="number" value={form.bid_price_yen} onChange={e => set('bid_price_yen', e.target.value)} placeholder="2500000" />
            </div>
            <div className="arc-form-group">
              <label>Réf LBC (€)</label>
              <input type="number" value={form.lbc_price_eur} onChange={e => set('lbc_price_eur', e.target.value)} placeholder="31000" />
            </div>
          </div>
          <div className="arc-form-row">
            <div className="arc-form-group">
              <label>Clé DB (pour recherche)</label>
              <input value={form.auction_model_key} onChange={e => set('auction_model_key', e.target.value)} placeholder="ex: M3" />
            </div>
          </div>
          <div className="arc-form-group">
            <label>Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)} placeholder="Observations, raison du passage, prix final payé..." rows={3} />
          </div>
          <div className="arc-form-actions">
            <button type="button" className="arc-btn arc-btn-cancel" onClick={onClose}>Annuler</button>
            <button type="submit" className="arc-btn arc-btn-primary" disabled={saving || !form.model_name.trim()}>
              {saving ? '...' : 'Archiver'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Archive() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    fetchArchive()
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id) => {
    await deleteArchiveEntry(id)
    setEntries(es => es.filter(e => e.id !== id))
  }

  const handleUpdate = (updated) => {
    setEntries(es => es.map(e => e.id === updated.id ? updated : e))
  }

  const handleAdd = (created) => {
    setEntries(es => [created, ...es])
  }

  const visible = filter === 'all' ? entries : entries.filter(e => e.archive_status === filter)

  if (loading) {
    return (
      <div className="archive-page">
        {[...Array(3)].map((_, i) => <div key={i} className="skeleton arc-skeleton" />)}
      </div>
    )
  }

  return (
    <div className="archive-page">
      <div className="arc-header">
        <h1 className="arc-title">Archive</h1>
        <div className="arc-filters">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.key}
              className={`arc-filter-btn ${filter === f.key ? 'active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              {f.key === 'all' && entries.length > 0 && (
                <span className="arc-filter-count">{entries.length}</span>
              )}
              {f.key !== 'all' && entries.filter(e => e.archive_status === f.key).length > 0 && (
                <span className="arc-filter-count">{entries.filter(e => e.archive_status === f.key).length}</span>
              )}
            </button>
          ))}
        </div>
        <button className="arc-add-btn" onClick={() => setShowModal(true)}>+ Archiver</button>
      </div>

      {visible.length === 0 ? (
        <div className="arc-empty">
          <p>{entries.length === 0 ? 'Aucun véhicule archivé' : 'Aucun véhicule dans cette catégorie'}</p>
          {entries.length === 0 && (
            <button className="arc-btn arc-btn-primary" onClick={() => setShowModal(true)}>
              Archiver un premier véhicule
            </button>
          )}
        </div>
      ) : (
        <div className="arc-grid">
          {visible.map(e => (
            <ArchiveCard key={e.id} entry={e} onDelete={handleDelete} onUpdate={handleUpdate} />
          ))}
        </div>
      )}

      {showModal && <AddModal onClose={() => setShowModal(false)} onAdd={handleAdd} />}
    </div>
  )
}
