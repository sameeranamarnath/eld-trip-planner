import Icon from './Icon.jsx'
import { formatMinutesShort } from '../format.js'

/** Turn-by-turn route instructions, one card per leg. */

const TYPE_ICON = {
  depart: 'depart',
  arrive: 'arrive',
  merge: 'merge',
  fork: 'merge',
  'on ramp': 'ramp',
  'off ramp': 'ramp',
  exit: 'ramp',
  roundabout: 'roundabout',
  rotary: 'roundabout',
  'roundabout turn': 'roundabout',
  'exit roundabout': 'roundabout',
  'exit rotary': 'roundabout',
}

function iconFor(step) {
  if (TYPE_ICON[step.maneuver_type]) return TYPE_ICON[step.maneuver_type]
  const modifier = step.modifier || ''
  if (modifier.includes('uturn')) return 'uturn'
  if (modifier.includes('left')) return 'turnLeft'
  if (modifier.includes('right')) return 'turnRight'
  return 'straight'
}

export default function Directions({ plan }) {
  const directions = plan?.directions
  const steps = directions?.steps || []
  const legs = directions?.legs || []

  if (steps.length === 0) {
    return (
      <div className="alert alert--info">
        <Icon name="info" size={17} />
        <span>The routing provider returned no turn-by-turn instructions for this trip.</span>
      </div>
    )
  }

  return (
    <div className="directions">
      <div className="directions__toolbar no-print">
        <span className="chip">
          <b>{legs.length}</b> leg{legs.length === 1 ? '' : 's'}
        </span>
        <span className="chip">
          <b>{steps.length}</b> turn-by-turn steps
        </span>
      </div>

      {legs.map((leg) => (
        <div className="card" key={leg.index}>
          <div className="card__head">
            <Icon name="route" size={17} />
            <div>
              <h3>
                {leg.from} <span className="directions__arrow">&rarr;</span> {leg.to}
              </h3>
              <p>
                {leg.distance_miles.toLocaleString()} mi &middot; {leg.step_count} step
                {leg.step_count === 1 ? '' : 's'}
              </p>
            </div>
          </div>
          <div className="card__body card__body--tight">
            <ol className="directions__list">
              {leg.steps.map((step) => (
                <li className="direction" key={step.index}>
                  <span className="direction__seq">{step.index + 1}</span>
                  <span className="direction__glyph">
                    <Icon name={iconFor(step)} size={17} />
                  </span>
                  <span className="direction__text">{step.instruction}</span>
                  <span className="direction__meta">
                    <span className="direction__dist">
                      {step.distance_miles.toFixed(1)} mi
                    </span>
                    <span>{formatMinutesShort(step.duration_minutes)}</span>
                    <span className="direction__mile">
                      mile {step.cumulative_miles.toFixed(1)}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      ))}
    </div>
  )
}
