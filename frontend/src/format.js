/** Small formatting helpers shared by every panel. */

export const STATUS_META = {
  off_duty: { label: 'Off Duty', short: 'OFF', line: 1, color: '#64748b' },
  sleeper_berth: { label: 'Sleeper Berth', short: 'SB', line: 2, color: '#8b5cf6' },
  driving: { label: 'Driving', short: 'DRV', line: 3, color: '#2563eb' },
  on_duty_not_driving: { label: 'On Duty (Not Driving)', short: 'ON', line: 4, color: '#f59e0b' },
}

export const STATUS_ORDER = ['off_duty', 'sleeper_berth', 'driving', 'on_duty_not_driving']

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/** `615` -> `"10:15"` */
export function minutesToClock(minutes) {
  const total = ((Math.round(minutes) % 1440) + 1440) % 1440
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

/** `"2026-10-01T06:30:00"` -> `"Thu, Oct 01 · 06:30"` */
export function formatDateTime(iso) {
  if (!iso) return '—'
  const parsed = parseLocal(iso)
  if (!parsed) return iso
  return `${DAY_NAMES[parsed.getDay()]}, ${MONTH_NAMES[parsed.getMonth()]} ${String(
    parsed.getDate(),
  ).padStart(2, '0')} · ${minutesToClock(parsed.getHours() * 60 + parsed.getMinutes())}`
}

/** `"2026-10-01"` -> `"Thu, Oct 01, 2026"` */
export function formatDateLong(value) {
  const parsed = parseLocal(value)
  if (!parsed) return value
  return `${DAY_NAMES[parsed.getDay()]}, ${MONTH_NAMES[parsed.getMonth()]} ${String(
    parsed.getDate(),
  ).padStart(2, '0')}, ${parsed.getFullYear()}`
}

/**
 * Parse the backend's naive ISO strings as LOCAL time.
 * `new Date("2026-10-01T06:30:00")` is already local, but adding a `Z` would
 * silently shift the whole log grid - so never let that happen.
 */
export function parseLocal(value) {
  if (!value) return null
  const match = String(value).match(
    /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/,
  )
  if (!match) return null
  const [, y, mo, d, h = '0', mi = '0', s = '0'] = match
  return new Date(
    Number(y),
    Number(mo) - 1,
    Number(d),
    Number(h),
    Number(mi),
    Number(s),
  )
}

/** `"2026-10-01T06:30:00"` -> `"2026-10-01T06:30"` for `<input type="datetime-local">`. */
export function toDateTimeInputValue(value) {
  const parsed = parseLocal(value) || new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(
    parsed.getHours(),
  )}:${pad(parsed.getMinutes())}`
}

export function formatMinutesShort(minutes) {
  if (!minutes) return '—'
  const rounded = Math.round(minutes)
  if (rounded < 60) return `${rounded} min`
  const hours = Math.floor(rounded / 60)
  const rest = rounded % 60
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}
