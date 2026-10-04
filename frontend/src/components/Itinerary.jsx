import Icon from './Icon.jsx'
import { buildMarkers } from '../markers.js'
import { formatDateLong, formatMinutesShort } from '../format.js'

const ICON_FOR_TYPE = {
  origin: 'truck',
  pickup: 'package',
  dropoff: 'flag',
  fuel: 'fuel',
  break: 'coffee',
  rest: 'bed',
  restart: 'refresh',
  inspection: 'check',
}

const LABEL_FOR_TYPE = {
  origin: 'Start',
  pickup: 'Pickup',
  dropoff: 'Drop-off',
  fuel: 'Fuel',
  break: 'Break',
  rest: 'Reset',
  restart: 'Restart',
  inspection: 'Inspection',
}

/** The timed plan: every pin, preceded by the drive that leads into it. */
export default function Itinerary({ plan, activePin, onActivate }) {
  const pins = buildMarkers(plan)

  return (
    <div className="stops">
      {pins.map((pin, index) => {
        const previous = index > 0 ? pins[index - 1] : null
        const driveMiles = previous ? Math.max(0, (pin.miles || 0) - (previous.miles || 0)) : 0
        const newDay = !previous || (previous.date && pin.date && previous.date !== pin.date)

        return (
          <div key={`${pin.type}-${index}-${pin.lat}-${pin.lng}`}>
            {newDay && pin.date ? (
              <div className="day-divider">
                <Icon name="calendar" size={13} />
                {formatDateLong(pin.date)}
              </div>
            ) : null}

            {index > 0 && driveMiles >= 1 ? (
              <div className="stop stop--drive">
                <span className="stop__time mono">{previous?.time}</span>
                <span className="stop__marker stop__marker--drive">
                  <Icon name="arrowRight" size={13} strokeWidth={2.4} />
                </span>
                <span className="stop__body">
                  <span className="stop__title">
                    Drive <b className="mono">{driveMiles.toFixed(0)} mi</b>
                  </span>
                  <span className="stop__meta">
                    {previous?.location} → {pin.location}
                  </span>
                </span>
                <span className="stop__right" />
              </div>
            ) : null}

            <button
              type="button"
              className={`stop stop--pin${index === activePin ? ' stop--active' : ''}`}
              onClick={() => onActivate?.(index)}
            >
              <span className="stop__time mono">{pin.time}</span>
              <span className="stop__marker" style={{ background: pin.colour }}>
                <Icon name={ICON_FOR_TYPE[pin.type] || 'pin'} size={13} strokeWidth={2.3} />
              </span>
              <span className="stop__body">
                <span className="stop__title">
                  {pin.title}
                  <span className={`badge badge--${pin.type}`}>{LABEL_FOR_TYPE[pin.type]}</span>
                </span>
                <span className="stop__meta">
                  {pin.location}
                  {pin.note ? ` · ${pin.note}` : ''}
                </span>
              </span>
              <span className="stop__right">
                {pin.durationMin ? formatMinutesShort(pin.durationMin) : 'on duty'}
                <br />
                <span className="muted mono">{Math.round(pin.miles || 0).toLocaleString()} mi</span>
              </span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
