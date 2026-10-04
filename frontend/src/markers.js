/**
 * The pin model shared by the route map and the itinerary list.
 *
 * This lives outside the components so that neither has to import from the
 * other: the map draws these pins, the itinerary lists them.
 */

export const STOP_COLORS = {
  origin: '#0b1220',
  pickup: '#059669',
  dropoff: '#db2777',
  fuel: '#f59e0b',
  break: '#7c3aed',
  rest: '#475569',
  restart: '#dc2626',
  inspection: '#2563eb',
}

const clockOf = (iso) => (iso ? iso.slice(11, 16) : '')

/** Build the ordered pin list: origin, then every planned stop. */
export function buildMarkers(plan) {
  const pins = []
  const origin = plan?.places?.current
  if (origin) {
    pins.push({
      type: 'origin',
      title: `Start · ${origin.short_label}`,
      label: 'S',
      colour: STOP_COLORS.origin,
      lat: origin.lat,
      lng: origin.lng,
      location: origin.short_label,
      time: clockOf(plan.summary?.departure),
      date: (plan.summary?.departure || '').slice(0, 10),
      durationMin: null,
      note: 'Trip begins here.',
      stopIndex: null,
      miles: 0,
    })
  }

  ;(plan?.stops || []).forEach((stop, index) => {
    const type = stop.type || 'inspection'
    // Inspections happen where the truck already is - don't stack a second pin.
    if (type === 'inspection') {
      const previous = pins[pins.length - 1]
      if (
        previous &&
        Math.abs(previous.lat - stop.lat) < 0.002 &&
        Math.abs(previous.lng - stop.lng) < 0.002
      ) {
        return
      }
    }
    pins.push({
      type,
      title: stop.title,
      label: String(pins.length),
      colour: STOP_COLORS[type] || '#2563eb',
      lat: stop.lat,
      lng: stop.lng,
      location: stop.location || stop.city || '',
      time: clockOf(stop.arrive),
      date: stop.date,
      durationMin: stop.duration_min,
      note: stop.note,
      stopIndex: index,
      miles: stop.miles_from_start,
      dayLabel: stop.arrive_time?.split(' ')[0] || '',
    })
  })

  return pins
}
