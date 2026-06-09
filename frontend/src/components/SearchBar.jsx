import { useState, useEffect, useRef } from 'react'
import './SearchBar.css'

/**
 * Barre de recherche avec autocomplete.
 * Props :
 *   value         — valeur actuelle (texte saisi)
 *   onChange      — callback(string) — appelé à chaque frappe, met à jour le texte
 *   onSelect      — callback(string) — appelé uniquement sur sélection d'une suggestion
 *   suggestions   — liste de suggestions filtrables
 *   popularModels — liste affichée quand input vide + focus
 *   size          — "compact" (défaut) | "hero" (grand, landing)
 *   placeholder   — override le placeholder
 */
export default function SearchBar({
  value, onChange, onSelect,
  suggestions = [], popularModels = [],
  size = 'compact', placeholder,
}) {
  const [open, setOpen] = useState(false)
  const [displayItems, setDisplayItems] = useState([])
  const ref = useRef(null)
  const isFocused = useRef(false)

  const handleSelect = onSelect || onChange

  const ph = placeholder || (size === 'hero'
    ? 'Rechercher un modèle… BMW M3, Porsche Cayman…'
    : 'Rechercher un modèle…')

  useEffect(() => {
    if (value.length >= 1) {
      const q = value.toLowerCase()
      setDisplayItems(suggestions.filter(s => s.toLowerCase().includes(q)).slice(0, 8))
      setOpen(true)
    } else {
      setDisplayItems([])
      setOpen(false)
    }
  }, [value, suggestions])

  useEffect(() => {
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleFocus = () => {
    isFocused.current = true
    if (value.length === 0 && popularModels.length > 0) {
      setDisplayItems(popularModels)
      setOpen(true)
    } else if (displayItems.length > 0) {
      setOpen(true)
    }
  }

  const isShowingPopular = value.length === 0

  return (
    <div className={`search-bar-wrap ${size === 'hero' ? 'hero' : ''}`} ref={ref}>
      <div className="search-input-wrap">
        <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
        </svg>
        <input
          className="search-input"
          type="text"
          placeholder={ph}
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={handleFocus}
          autoComplete="off"
        />
        {value && (
          <button className="search-clear" onClick={() => { onChange(''); setOpen(false) }}>×</button>
        )}
      </div>
      {open && displayItems.length > 0 && (
        <ul className="suggestions">
          {isShowingPopular && <li className="suggestions-header">Modèles populaires</li>}
          {displayItems.map(s => (
            <li key={s} className="suggestion-item" onMouseDown={() => { handleSelect(s); setOpen(false) }}>
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
