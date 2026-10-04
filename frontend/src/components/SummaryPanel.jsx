import Icon from './Icon.jsx'
import { formatDateTime, formatMinutesShort } from '../format.js'

function Stat({ label, value, sub, tone, icon }) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ''}`}>
      <span className="stat__label">
        <Icon name={icon} size={13} />
        {label}
      </span>
      <span className="stat__value">{value}</span>
      {sub ? <span className="stat__sub">{sub}</span> : null}
    </div>
  )
}

/** Headline numbers for the planned run. */
export default function SummaryPanel({ plan }) {
  const summary = plan.summary

  return (
    <div className="card">
      <div className="card__head">
        <Icon name="gauge" size={18} />
        <div>
          <h2>Trip summary</h2>
          <p>
            {plan.places.current.short_label} → {plan.places.pickup.short_label} →{' '}
            {plan.places.dropoff.short_label}
          </p>
        </div>
      </div>
      <div className="card__body">
        <div className="stats">
          <Stat
            label="Route distance"
            value={`${Math.round(summary.total_miles).toLocaleString()} mi`}
            sub={`${summary.driving_hours.toFixed(1)} h driving`}
            icon="route"
            tone="accent"
          />
          <Stat
            label="Elapsed"
            value={`${summary.wall_clock_days.toFixed(1)} days`}
            sub={`${summary.wall_clock_hours.toFixed(1)} h total`}
            icon="clock"
          />
          <Stat
            label="Log sheets"
            value={summary.log_sheets}
            icon="file"
          />
          <Stat
            label="Cycle used"
            value={`${summary.cycle_hours_after_trip.toFixed(1)} h`}
            sub={`${summary.cycle_hours_remaining.toFixed(1)} h left`}
            icon="shield"
            tone={summary.cycle_hours_remaining < 10 ? 'amber' : undefined}
          />
          <Stat
            label="Fuel stops"
            value={summary.fuel_stops}
            icon="fuel"
          />
          <Stat
            label="Breaks + resets"
            value={summary.breaks + summary.rests}
            sub={`${summary.breaks} breaks · ${summary.rests} resets${
              summary.restarts ? ` · ${summary.restarts} restarts` : ''
            }`}
            icon="coffee"
          />
        </div>

        <hr className="divider" />

        <div className="split-2">
          <div>
            <div className="section-title">Timings</div>
            <dl className="kv">
              <dt>Departure</dt>
              <dd>{formatDateTime(summary.departure)}</dd>
              <dt>Arrival</dt>
              <dd>{formatDateTime(summary.arrival)}</dd>
            </dl>
          </div>
          <div>
            <div className="section-title">Route legs</div>
            <dl className="kv">
              {plan.route.legs.map((leg) => (
                <div key={leg.index} style={{ display: 'contents' }}>
                  <dt>{leg.from}</dt>
                  <dd>
                    → {leg.to} · {Math.round(leg.distance_miles).toLocaleString()} mi ·{' '}
                    {formatMinutesShort(leg.duration_hours * 60)}
                  </dd>
                </div>
              ))}
              <dt>Stop time</dt>
              <dd>
                {formatMinutesShort(
                  plan.stops.reduce((total, stop) => total + stop.duration_min, 0),
                )}{' '}
                across {plan.stops.length} planned stops
              </dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
