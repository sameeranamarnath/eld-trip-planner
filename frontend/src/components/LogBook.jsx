import Icon from './Icon.jsx'
import LogSheet from './LogSheet.jsx'
import { formatDateTime, formatMinutesShort } from '../format.js'

/** Every generated daily log sheet, plus a printable container. */
export default function LogBook({ plan }) {
  const logs = plan?.logs || []
  const summary = plan?.summary

  if (logs.length === 0) {
    return (
      <div className="alert alert--info">
        <Icon name="info" size={17} />
        <span>No log sheets were produced for this trip.</span>
      </div>
    )
  }

  return (
    <div className="logbook">
      <div className="logbook__toolbar no-print">
        <span className="chip">
          <b>{logs.length}</b> daily log sheet{logs.length === 1 ? '' : 's'}
        </span>
        <span className="chip">
          {summary?.total_miles?.toLocaleString()} mi · {formatMinutesShort(summary?.driving_hours * 60)}{' '}
          driving
        </span>
        <span className="chip">
          Arrives {formatDateTime(summary?.arrival)}
        </span>
        <button
          type="button"
          className="btn btn--ghost"
          style={{ marginLeft: 'auto' }}
          onClick={() => window.print()}
        >
          <Icon name="printer" size={15} />
          Print / save as PDF
        </button>
      </div>

      {logs.map((day) => (
        <div className="log-sheet" key={day.date}>
          <div className="log-sheet__frame">
            <LogSheet day={day} />
          </div>
          <div className="log-sheet__caption">
            <span>
              Day <b>{day.day_index}</b> · <b>{day.header.day_label}</b>
            </span>
            <span>·</span>
            <span>
              <b>{Math.round(day.miles_driving).toLocaleString()}</b> mi today
            </span>
            <span>·</span>
            <span>
              <b>{day.remarks.length}</b> remarks
            </span>
            <span>·</span>
            <span>
              Recap: <b>{day.recap?.total_hours_on_duty_hhmm}</b> of 70 h used,{' '}
              <b>{day.recap?.hours_available_tomorrow_hhmm}</b> available tomorrow
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
