import { STATUS_META, STATUS_ORDER } from '../format.js'

/* ---------------------------------------------------------------- geometry -- */

const W = 1180
const H = 706
const PAD = 16
const LABEL_W = 142
const GRID_X = PAD + LABEL_W + 8
const REMARKS_W = 216
const GRID_W = W - PAD * 2 - LABEL_W - 8 - REMARKS_W - 14
const HOUR_W = GRID_W / 24

const HOUR_BAND_Y = 138
const GRID_Y = 166
const ROW_H = 58
const GRID_BOTTOM = GRID_Y + ROW_H * 4
const REMARKS_X = GRID_X + GRID_W + 14

const BAND_Y = GRID_BOTTOM + 18
const RECAP_Y = BAND_Y + 108

const INK = '#0b1220'
const LINE = '#c9d3e3'
const LINE_SOFT = '#e2e8f2'
const STATUS_COLOR = {
  off_duty: '#475569',
  sleeper_berth: '#7c3aed',
  driving: '#1d4ed8',
  on_duty_not_driving: '#b45309',
}

const x = (min) => GRID_X + (Math.max(0, Math.min(1440, min)) / 1440) * GRID_W
const y = (line) => GRID_Y + (line - 1) * ROW_H

const hourLabel = (hour) => {
  const twelve = hour % 12 === 0 ? 12 : hour % 12
  return String(twelve)
}

/* ------------------------------------------------------------------ pieces -- */

function SheetField({ x: fx, y: fy, width, label, value, strong }) {
  return (
    <g>
      <text x={fx} y={fy} fontSize="9.2" fill="#7a879c" fontWeight="700" letterSpacing="0.08em">
        {label.toUpperCase()}
      </text>
      <line
        x1={fx}
        y1={fy + 21}
        x2={fx + width}
        y2={fy + 21}
        stroke={LINE}
        strokeWidth="1"
      />
      <text
        x={fx}
        y={fy + 16}
        fontSize={strong ? '13' : '12.4'}
        fill={INK}
        fontWeight={strong ? '700' : '600'}
      >
        {value || '—'}
      </text>
    </g>
  )
}

function SheetHeader({ header }) {
  const colW = (W - PAD * 2) / 4
  const colX = (index) => PAD + index * colW
  const fieldWidth = colW - 22

  return (
    <g>
      <rect x={PAD} y={12} width={W - PAD * 2} height={112} rx="10" fill="#fbfcfe" stroke={LINE} />

      <text x={PAD + 16} y={38} fontSize="17" fontWeight="800" fill={INK} letterSpacing="-0.01em">
        DRIVER&apos;S DAILY LOG
      </text>
      <text x={PAD + 16} y={52} fontSize="9.5" fill="#7a879c" fontWeight="600" letterSpacing="0.1em">
        {`24-HOUR PERIOD STARTING AT ${(
          header.period_start_time || 'MIDNIGHT'
        ).toUpperCase()} \u00B7 HOME TERMINAL TIME (${
          header.home_terminal || 'HOME TERMINAL'
        }) \u00B7 PROPERTY-CARRYING \u00B7 70 HRS / 8 DAYS`}
      </text>

      <rect x={W - PAD - 196} y={22} width="180" height="30" rx="8" fill="#0b1220" />
      <text
        x={W - PAD - 106}
        y={41}
        fontSize="12"
        fontWeight="800"
        fill="#fff"
        textAnchor="middle"
        letterSpacing="0.02em"
      >
        {header.day_label || header.date}
      </text>

      <SheetField x={colX(0)} y={70} width={fieldWidth} label="Date" value={header.date} strong />
      <SheetField
        x={colX(1)}
        y={70}
        width={fieldWidth}
        label="Driver name (print)"
        value={header.driver_name}
      />
      <SheetField
        x={colX(2)}
        y={70}
        width={fieldWidth}
        label="Driver number"
        value={header.driver_number}
      />
      <SheetField x={colX(3)} y={70} width={fieldWidth} label="Co-driver" value={header.co_driver} />

      <SheetField x={colX(0)} y={100} width={fieldWidth} label="Carrier" value={header.carrier} />
      <SheetField
        x={colX(1)}
        y={100}
        width={fieldWidth}
        label="Main office address"
        value={header.main_office_address || header.home_terminal}
      />
      <SheetField
        x={colX(2)}
        y={100}
        width={fieldWidth}
        label="Tractor number"
        value={header.tractor_number}
      />
      <SheetField
        x={colX(3)}
        y={100}
        width={fieldWidth}
        label="Trailer number"
        value={header.trailer_number}
      />
    </g>
  )
}

/* --------------------------------------------------------------- the grid -- */

function SheetGrid({ day }) {
  const entries = day.entries || []
  const hours = Array.from({ length: 24 }, (_, index) => index)

  return (
    <g>
      <rect
        x={GRID_X}
        y={GRID_Y}
        width={GRID_W}
        height={ROW_H * 4}
        fill="#ffffff"
        stroke={INK}
        strokeWidth="1.3"
      />

      <text x={GRID_X + 2} y={HOUR_BAND_Y - 2} fontSize="7.6" fill="#7a879c" fontWeight="700">
        MIDNIGHT
      </text>
      <text
        x={x(720)}
        y={HOUR_BAND_Y - 2}
        fontSize="7.6"
        fill="#7a879c"
        fontWeight="700"
        textAnchor="middle"
      >
        NOON
      </text>

      {hours.map((hour) => (
        <g key={`hour-${hour}`}>
          <text
            x={GRID_X + hour * HOUR_W + HOUR_W / 2}
            y={HOUR_BAND_Y + 12}
            fontSize="9.6"
            fill="#55637a"
            fontWeight="700"
            textAnchor="middle"
          >
            {hourLabel(hour)}
          </text>
          <line
            x1={GRID_X + hour * HOUR_W}
            y1={GRID_Y}
            x2={GRID_X + hour * HOUR_W}
            y2={GRID_BOTTOM}
            stroke={hour % 6 === 0 ? LINE : LINE_SOFT}
            strokeWidth="1"
          />
        </g>
      ))}
      <line
        x1={GRID_X + GRID_W}
        y1={GRID_Y}
        x2={GRID_X + GRID_W}
        y2={GRID_BOTTOM}
        stroke={LINE}
        strokeWidth="1"
      />

      {hours.map((hour) =>
        [15, 30, 45].map((minute) => {
          const tickX = GRID_X + (hour * 60 + minute) * (GRID_W / 1440)
          return (
            <line
              key={`tick-${hour}-${minute}`}
              x1={tickX}
              y1={GRID_Y}
              x2={tickX}
              y2={GRID_Y + (minute === 30 ? 11 : 6)}
              stroke="#aab6c9"
              strokeWidth="0.9"
            />
          )
        }),
      )}

      {[0, 1, 2, 3, 4].map((row) => (
        <line
          key={`row-${row}`}
          x1={GRID_X}
          y1={GRID_Y + row * ROW_H}
          x2={GRID_X + GRID_W}
          y2={GRID_Y + row * ROW_H}
          stroke={row === 4 ? INK : LINE}
          strokeWidth={row === 4 ? 1.3 : 1}
          strokeDasharray={row === 4 ? undefined : '2 3'}
        />
      ))}

      {STATUS_ORDER.map((status) => {
        const line = STATUS_META[status].line
        const top = GRID_Y + (line - 1) * ROW_H
        return (
          <g key={status}>
            <rect
              x={PAD}
              y={top}
              width={LABEL_W}
              height={ROW_H}
              fill={line % 2 === 0 ? '#f7f9fd' : '#fff'}
              stroke={LINE}
              strokeWidth="1"
            />
            <rect x={PAD} y={top + 12} width="4" height={ROW_H - 24} fill={STATUS_COLOR[status]} />
            <text x={PAD + 14} y={top + 22} fontSize="10.4" fontWeight="800" fill={INK}>
              {line}.
            </text>
            <text x={PAD + 24} y={top + 22} fontSize="10.4" fontWeight="700" fill={INK}>
              {STATUS_META[status].label.toUpperCase()}
            </text>
            <text x={PAD + 14} y={top + 38} fontSize="8.6" fill="#8494aa" fontWeight="600">
              {line === 1
                ? 'not driving / not working'
                : line === 2
                  ? 'in the sleeper berth'
                  : line === 3
                    ? 'at the controls, moving'
                    : 'working, not driving'}
            </text>
            <rect
              x={GRID_X + GRID_W - 56}
              y={top + 5}
              width="52"
              height="40"
              rx="6"
              fill="#ffffff"
              opacity="0.94"
            />
            <text x={GRID_X + GRID_W - 8} y={top + 22} fontSize="12" fontWeight="800"
              fill={STATUS_COLOR[status]} textAnchor="end">
              {day.totals[status]?.hhmm}
            </text>
            <text x={GRID_X + GRID_W - 8} y={top + 37} fontSize="8" fill="#8494aa"
              fontWeight="700" textAnchor="end">
              TOTAL HRS
            </text>
          </g>
        )
      })}

      {entries.map((entry, index) => {
        const next = entries[index + 1]
        if (!next || next.line === entry.line) return null
        return (
          <line
            key={`connector-${index}`}
            x1={x(next.start_min)}
            y1={y(entry.line)}
            x2={x(next.start_min)}
            y2={y(next.line)}
            stroke={STATUS_COLOR[entry.status] || '#334155'}
            strokeWidth="2.2"
          />
        )
      })}

      {/* Bracket: an on-duty window during which the truck never moved. */}
      {entries.map((entry, index) => {
        const isStationaryWork =
          entry.status === 'on_duty_not_driving' &&
          entry.stationary &&
          entry.duration_min >= 8 &&
          entry.kind !== 'prior_off'
        if (!isStationaryWork) return null
        const yb = y(4) + 13
        const x1 = x(entry.start_min)
        const x2 = x(entry.end_min)
        return (
          <g key={`bracket-${index}`} stroke="#93a2b8" strokeWidth="1.6" fill="none">
            <line x1={x1} y1={yb - 9} x2={x1} y2={yb} />
            <line x1={x1} y1={yb} x2={x2} y2={yb} />
            <line x1={x2} y1={yb} x2={x2} y2={yb - 9} />
          </g>
        )
      })}

      {/* The duty-status line itself. */}
      {entries.map((entry, index) => (
        <line
          key={`stroke-${index}`}
          x1={x(entry.start_min)}
          y1={y(entry.line)}
          x2={x(entry.end_min)}
          y2={y(entry.line)}
          stroke={STATUS_COLOR[entry.status] || '#334155'}
          strokeWidth={entry.status === 'driving' ? 3.1 : 2.4}
          strokeLinecap="round"
        />
      ))}

      {/* Numbered flag at every duty-status change. */}
      {(day.remarks || []).map((remark) => (
        <g key={`flag-${remark.index}`}>
          <circle
            cx={x(remark.at_min)}
            cy={y(remark.line)}
            r="8.6"
            fill={STATUS_COLOR[remark.status] || '#334155'}
            stroke="#ffffff"
            strokeWidth="2"
          />
          <text
            x={x(remark.at_min)}
            y={y(remark.line) + 3.2}
            fontSize="9"
            fontWeight="800"
            fill="#ffffff"
            textAnchor="middle"
          >
            {remark.index}
          </text>
        </g>
      ))}
    </g>
  )
}

/* ------------------------------------------------------------- remarks col -- */

function RemarksColumn({ day }) {
  const remarks = day.remarks || []
  const top = HOUR_BAND_Y - 12
  const available = BAND_Y - 10 - top - 22
  const rowH = Math.max(15, Math.min(25, available / Math.max(remarks.length, 1)))

  return (
    <g>
      <rect
        x={REMARKS_X}
        y={top}
        width={REMARKS_W}
        height={BAND_Y - 10 - top}
        fill="#fdfefe"
        stroke={LINE}
        rx="6"
      />
      <rect x={REMARKS_X} y={top} width={REMARKS_W} height="22" fill="#eef2f8" rx="6" />
      <text x={REMARKS_X + 10} y={top + 15} fontSize="9.6" fontWeight="800" fill="#3f4c63">
        REMARKS
      </text>
      <text
        x={REMARKS_X + REMARKS_W - 10}
        y={top + 15}
        fontSize="8.2"
        fontWeight="700"
        fill="#7a879c"
        textAnchor="end"
      >
        LOCATION / ACTIVITY
      </text>

      {remarks.map((remark, index) => {
        const ry = top + 22 + index * rowH + rowH * 0.72
        const clipped = ry > BAND_Y - 14
        if (clipped) return null
        return (
          <g key={`remark-${remark.index}`}>
            <circle
              cx={REMARKS_X + 13}
              cy={ry - 3.4}
              r="6.4"
              fill={STATUS_COLOR[remark.status] || '#334155'}
            />
            <text
              x={REMARKS_X + 13}
              y={ry - 1.2}
              fontSize="7.4"
              fontWeight="800"
              fill="#fff"
              textAnchor="middle"
            >
              {remark.index}
            </text>
            <text x={REMARKS_X + 25} y={ry} fontSize="8.6" fontWeight="800" fill={INK}>
              {remark.time}
            </text>
            <text x={REMARKS_X + 52} y={ry} fontSize="8.4" fill="#3f4c63" fontWeight="700">
              {truncate(remark.location || remark.city || '—', 30)}
            </text>
            <text x={REMARKS_X + 52} y={ry + 9.2} fontSize="7.7" fill="#7a879c">
              {truncate(remark.note + (remark.continued ? ' (cont.)' : ''), 34)}
            </text>
            {index < remarks.length - 1 ? (
              <line
                x1={REMARKS_X + 8}
                y1={ry + rowH - 6.6}
                x2={REMARKS_X + REMARKS_W - 8}
                y2={ry + rowH - 6.6}
                stroke="#eef2f8"
                strokeWidth="1"
              />
            ) : null}
          </g>
        )
      })}
    </g>
  )
}

function truncate(text, max) {
  const value = String(text || '')
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

/* -------------------------------------------------- mileage + totals strip -- */

function MileageAndTotals({ day }) {
  const boxW = (GRID_X + GRID_W - PAD) * 0.6
  const readings = day.mileage_entries || []
  const totalsX = PAD + boxW + 12
  const totalsW = GRID_X + GRID_W - totalsX

  return (
    <g>
      <rect x={PAD} y={BAND_Y} width={boxW} height="96" rx="8" fill="#fff" stroke={LINE} />
      <text x={PAD + 12} y={BAND_Y + 18} fontSize="9" fontWeight="800" fill="#7a879c" letterSpacing="0.07em">
        MILES DRIVEN TODAY
      </text>
      <text x={PAD + 12} y={BAND_Y + 46} fontSize="24" fontWeight="800" fill={INK}>
        {Math.round(day.miles_driving).toLocaleString()}
      </text>
      <text x={PAD + 12 + String(Math.round(day.miles_driving)).length * 15 + 8} y={BAND_Y + 46}
        fontSize="11" fontWeight="700" fill="#7a879c">
        mi
      </text>
      <text x={PAD + boxW - 12} y={BAND_Y + 18} fontSize="9" fontWeight="800" fill="#7a879c"
        textAnchor="end" letterSpacing="0.07em">
        ODOMETER READINGS (RECORD AT EACH STOP)
      </text>

      {readings.slice(0, 4).map((reading, index) => (
        <g key={`reading-${index}`}>
          <text x={PAD + 12} y={BAND_Y + 64 + index * 11} fontSize="8" fontWeight="800" fill="#55637a">
            {reading.time}
          </text>
          <text x={PAD + 44} y={BAND_Y + 64 + index * 11} fontSize="8" fill="#55637a">
            {truncate(reading.note, 12)} · {truncate(reading.location || '—', 22)}
          </text>
          <text x={PAD + boxW - 12} y={BAND_Y + 64 + index * 11} fontSize="8" fontWeight="700"
            fill="#3f4c63" textAnchor="end" fontFamily="ui-monospace, monospace">
            {reading.odometer ? reading.odometer.toLocaleString() : reading.trip_miles}
          </text>
        </g>
      ))}

      <rect x={totalsX} y={BAND_Y} width={totalsW} height="96" rx="8" fill="#fbfcfe" stroke={LINE} />
      <text x={totalsX + 12} y={BAND_Y + 18} fontSize="9" fontWeight="800" fill="#7a879c"
        letterSpacing="0.07em">
        TOTAL HOURS ON EACH LINE
      </text>
      {STATUS_ORDER.map((status, index) => {
        const col = index % 2
        const row = Math.floor(index / 2)
        const bx = totalsX + 12 + col * (totalsW / 2 - 6)
        const by = BAND_Y + 38 + row * 22
        return (
          <g key={`total-${status}`}>
            <rect x={bx} y={by - 11} width="4" height="14" fill={STATUS_COLOR[status]} />
            <text x={bx + 10} y={by} fontSize="9.4" fontWeight="700" fill="#3f4c63">
              {STATUS_META[status].line}. {STATUS_META[status].label}
            </text>
            <text x={bx + totalsW / 2 - 22} y={by} fontSize="11" fontWeight="800" fill={INK}
              textAnchor="end" fontFamily="ui-monospace, monospace">
              {day.totals[status]?.hhmm}
            </text>
          </g>
        )
      })}
      <line x1={totalsX + totalsW - 132} y1={BAND_Y + 66} x2={totalsX + totalsW - 12}
        y2={BAND_Y + 66} stroke={LINE} />
      <text x={totalsX + totalsW - 132} y={BAND_Y + 84} fontSize="10" fontWeight="800" fill={INK}>
        TOTAL HOURS
      </text>
      <text x={totalsX + totalsW - 12} y={BAND_Y + 84} fontSize="13" fontWeight="800" fill={INK}
        textAnchor="end" fontFamily="ui-monospace, monospace">
        {day.total_hours_hhmm}
      </text>
    </g>
  )
}

/* ------------------------------------------------------------------ recap -- */

function RecapBand({ day }) {
  const recap = day.recap || {}
  const header = day.header || {}
  const boxH = H - RECAP_Y - PAD
  const leftW = 560
  const rightX = PAD + leftW + 20

  const rows = [
    ['A. Hours on duty today', recap.hours_on_duty_today_hhmm],
    ['B. Hours on duty last 7 days', recap.hours_previous_seven_days_hhmm],
    ['C. Total hours on duty (A + B)', recap.total_hours_on_duty_hhmm],
    ['D. Hours available tomorrow (70 − C)', recap.hours_available_tomorrow_hhmm],
  ]

  return (
    <g>
      <rect x={PAD} y={RECAP_Y} width={leftW} height={boxH} rx="8" fill="#fbfcfe" stroke={LINE} />
      <text x={PAD + 12} y={RECAP_Y + 19} fontSize="9.4" fontWeight="800" fill="#7a879c"
        letterSpacing="0.07em">
        70-HOUR / 8-DAY RECAP
      </text>

      {rows.map(([label, value], index) => {
        const ry = RECAP_Y + 42 + index * 26
        const emphasised = index === 3
        return (
          <g key={label}>
            {emphasised ? (
              <rect x={PAD + 8} y={ry - 15} width={leftW - 16} height="21" rx="5"
                fill="#e6f7f1" stroke="#b9e6d8" />
            ) : null}
            <text x={PAD + 16} y={ry} fontSize="9.8" fontWeight="700"
              fill={emphasised ? '#0b6b4f' : '#3f4c63'}>
              {label}
            </text>
            <text x={PAD + leftW - 16} y={ry} fontSize="11.4" fontWeight="800"
              fill={emphasised ? '#0b6b4f' : INK} textAnchor="end"
              fontFamily="ui-monospace, monospace">
              {value || '—'}
            </text>
          </g>
        )
      })}

      {recap.hours_on_duty_today != null ? (
        <text x={PAD + 16} y={RECAP_Y + boxH - 12} fontSize="7.6" fill="#8494aa" fontWeight="600">
          Cycle starts at {recap.cycle_limit_hours ?? 70} h. Off-duty and sleeper-berth time do not
          count toward the 70-hour total.
        </text>
      ) : null}

      <rect x={rightX} y={RECAP_Y} width={W - PAD - rightX} height={boxH} rx="8" fill="#fff"
        stroke={LINE} />
      <text x={rightX + 12} y={RECAP_Y + 19} fontSize="9.4" fontWeight="800" fill="#7a879c"
        letterSpacing="0.07em">
        SHIPMENT &amp; CERTIFICATION
      </text>

      <SheetField x={rightX + 12} y={RECAP_Y + 30} width={(W - PAD - rightX) / 2 - 26}
        label="Shipper" value={header.shipper} />
      <SheetField x={rightX + 12 + (W - PAD - rightX) / 2} y={RECAP_Y + 30}
        width={(W - PAD - rightX) / 2 - 26} label="Commodity" value={header.commodity} />
      <SheetField x={rightX + 12} y={RECAP_Y + 62} width={(W - PAD - rightX) / 2 - 26}
        label="Load / pro number" value={header.load_id} />
      <SheetField x={rightX + 12 + (W - PAD - rightX) / 2} y={RECAP_Y + 62}
        width={(W - PAD - rightX) / 2 - 26} label="Co-driver" value={header.co_driver} />

      <text x={rightX + 12} y={RECAP_Y + 104} fontSize="8.4" fill="#55637a" fontWeight="600">
        I certify that these entries are true and correct.
      </text>
      <line x1={rightX + 12} y1={RECAP_Y + boxH - 20} x2={rightX + 300} y2={RECAP_Y + boxH - 20}
        stroke={INK} strokeWidth="0.9" />
      <text x={rightX + 12} y={RECAP_Y + boxH - 9} fontSize="7.6" fill="#8494aa" fontWeight="700">
        DRIVER&apos;S SIGNATURE
      </text>
      <line x1={rightX + 320} y1={RECAP_Y + boxH - 20} x2={W - PAD - 12}
        y2={RECAP_Y + boxH - 20} stroke={INK} strokeWidth="0.9" />
      <text x={rightX + 320} y={RECAP_Y + boxH - 9} fontSize="7.6" fill="#8494aa" fontWeight="700">
        DATE
      </text>
    </g>
  )
}

/* ----------------------------------------------------------------- sheet -- */

export default function LogSheet({ day }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Daily log sheet for ${day.date}`}
    >
      <rect x="0" y="0" width={W} height={H} fill="#ffffff" />
      <SheetHeader header={day.header} />
      <SheetGrid day={day} />
      <RemarksColumn day={day} />
      <MileageAndTotals day={day} />
      <RecapBand day={day} />
    </svg>
  )
}






