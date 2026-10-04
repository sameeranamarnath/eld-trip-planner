import { useEffect, useRef, useState } from 'react'
import { searchPlaces } from '../api.js'
import Icon from './Icon.jsx'

/**
 * Location input with debounced autocomplete against the backend's
 * `/places/` proxy (Photon, falling back to Nominatim).
 */
export default function LocationField({
  id,
  label,
  hint,
  icon,
  accent,
  value,
  placeholder,
  onChange,
}) {
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [loading, setLoading] = useState(false)
  const skipRef = useRef(false)
  const focusedRef = useRef(false)

  useEffect(() => {
    if (skipRef.current) {
      skipRef.current = false
      return undefined
    }
    const query = (value || '').trim()
    if (query.length < 3) {
      setSuggestions([])
      setOpen(false)
      return undefined
    }

    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const payload = await searchPlaces(query, controller.signal)
        const results = (payload?.results || []).slice(0, 6)
        setSuggestions(results)
        // Never pop the list open unless the driver is actually in the field.
        setOpen(results.length > 0 && focusedRef.current)
        setActive(-1)
      } catch (error) {
        if (error.name !== 'AbortError') setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 280)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value])

  function choose(place) {
    skipRef.current = true
    onChange(place.short_label || place.label)
    setSuggestions([])
    setOpen(false)
  }

  function handleKeyDown(event) {
    if (!open || suggestions.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((prev) => (prev + 1) % suggestions.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      choose(suggestions[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        <span
          className="field__dot"
          style={{ background: accent, boxShadow: `0 0 0 3px ${accent}22` }}
        />
        {label}
        {hint ? <span className="field__hint">{hint}</span> : null}
      </label>
      <div className="input-wrap">
        <span className="input-icon">
          <Icon name={icon} size={16} />
        </span>
        <input
          id={id}
          className="input"
          type="text"
          autoComplete="off"
          spellCheck="false"
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            focusedRef.current = true
            setOpen(suggestions.length > 0)
          }}
          onBlur={() => {
            focusedRef.current = false
            window.setTimeout(() => setOpen(false), 140)
          }}
        />
      </div>
      {open ? (
        <div className="suggestions" role="listbox">
          {suggestions.map((place, index) => (
            <button
              key={`${place.lat}-${place.lng}-${index}`}
              type="button"
              className={`suggestion${index === active ? ' suggestion--active' : ''}`}
              onMouseEnter={() => setActive(index)}
              onMouseDown={(event) => {
                event.preventDefault()
                choose(place)
              }}
            >
              <Icon name="pin" size={14} />
              <span>{place.short_label || place.label}</span>
              <span className="suggestion__muted">{place.state || place.country}</span>
            </button>
          ))}
        </div>
      ) : null}
      {loading && !open ? <span className="field__hint">Searching…</span> : null}
    </div>
  )
}
