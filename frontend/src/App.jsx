import { useCallback, useState } from 'react'
import Icon from './components/Icon.jsx'
import TripForm from './components/TripForm.jsx'
import RouteMap from './components/RouteMap.jsx'
import Itinerary from './components/Itinerary.jsx'
import SummaryPanel from './components/SummaryPanel.jsx'
import LogBook from './components/LogBook.jsx'
import Directions from './components/Directions.jsx'
import { planTrip } from './api.js'
import { toDateTimeInputValue } from './format.js'
import { DEFAULT_HEADER } from './logHeader.js'
import { useTheme } from './useTheme.js'

const TABS = [
  { id: 'route', label: 'Route & stops', icon: 'route' },
  { id: 'directions', label: 'Route instructions', icon: 'list' },
  { id: 'logs', label: 'Daily log sheets', icon: 'file' },
]

function initialForm() {
  return {
    current_location: '',
    pickup_location: '',
    dropoff_location: '',
    cycle_used_hours: 0,
    departure_time: toDateTimeInputValue(new Date()),
    start_odometer: '',
    header: { ...DEFAULT_HEADER },
  }
}

export default function App() {
  const [form, setForm] = useState(initialForm)
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('route')
  const [activePin, setActivePin] = useState(null)
  const [theme, setTheme] = useTheme()

  const handleSubmit = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await planTrip({
        current_location: form.current_location.trim(),
        pickup_location: form.pickup_location.trim(),
        dropoff_location: form.dropoff_location.trim(),
        cycle_used_hours: Number(form.cycle_used_hours) || 0,
        departure_time: form.departure_time || null,
        start_odometer: Number(form.start_odometer) || 0,
        header: form.header,
      })
      setPlan(result)
      setActivePin(null)
    } catch (requestError) {
      setError(requestError.message || 'Something went wrong while planning this trip.')
      setPlan(null)
    } finally {
      setLoading(false)
    }
  }, [form])

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="brand">
            <span className="brand__mark">
              <Icon name="truck" size={21} strokeWidth={2.1} />
            </span>
            <div className="brand__text">
              <h1>Spotter ELD</h1>
              <span>Trip planner &amp; automatic driver&apos;s daily log sheets</span>
            </div>
          </div>
          <div className="topbar__facts">
            <button
              type="button"
              className="fact-chip fact-chip--action"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={14} />
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        <div className="layout">
          <div className="column no-print">
            <TripForm
              value={form}
              onChange={setForm}
              onSubmit={handleSubmit}
              loading={loading}
              error={error}
            />
          </div>

          <div className="column" aria-live="polite" aria-busy={loading}>
            {!plan && !loading ? <EmptyState /> : null}
            {loading ? <LoadingState /> : null}

            {plan && !loading ? (
              <>
                <div className="no-print">
                  <SummaryPanel plan={plan} />
                </div>

                <div className="tabs no-print">
                  {TABS.map((entry) => (
                    <button
                      key={entry.id}
                      type="button"
                      className={`tab${tab === entry.id ? ' tab--active' : ''}`}
                      onClick={() => setTab(entry.id)}
                    >
                      <Icon name={entry.icon} size={15} />
                      {entry.label}
                      {entry.id === 'logs' ? (
                        <span className="tab__count">{plan.logs.length}</span>
                      ) : null}
                      {entry.id === 'directions' ? (
                        <span className="tab__count">{plan.directions?.step_count ?? 0}</span>
                      ) : null}
                    </button>
                  ))}
                </div>

                {tab === 'route' ? (
                  <div className="result-grid">
                    <RouteMap plan={plan} activePin={activePin} onActivate={setActivePin} />
                    <div className="card">
                      <div className="card__head">
                        <Icon name="list" size={17} />
                        <div>
                          <h3>Stops, rests &amp; fuel</h3>
                          <p>{plan.stops.length} stops</p>
                        </div>
                      </div>
                      <div className="card__body card__body--tight">
                        <Itinerary plan={plan} activePin={activePin} onActivate={setActivePin} />
                      </div>
                    </div>
                  </div>
                ) : tab === 'directions' ? (
                  <Directions plan={plan} />
                ) : (
                  <LogBook plan={plan} />
                )}
              </>
            ) : null}
          </div>
        </div>
      </main>

    </div>
  )
}

function EmptyState() {
  return (
    <div className="empty">
      <div className="empty__icon">
        <Icon name="file" size={28} />
      </div>
      <h2>No trip planned yet</h2>
      <p>
        Enter the current location, the pickup, the drop-off and the cycle hours already used to
        generate the route, the stops and the daily log sheets.
      </p>
    </div>
  )
}

function LoadingState() {
  return (
    <>
      <div className="card">
        <div className="card__body">
          <div className="stats">
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <div className="skeleton" style={{ height: 76 }} key={index} />
            ))}
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card__body">
          <div className="skeleton" style={{ height: 420 }} />
        </div>
      </div>
    </>
  )
}
