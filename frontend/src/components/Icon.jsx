/**
 * Inline SVG icon set.  Keeps the bundle free of an icon dependency and lets
 * every glyph inherit `currentColor`.
 */

const PATHS = {
  truck: 'M3 7h11v8H3zM14 10h4l3 3v2h-7zM6.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM17.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z',
  pin: 'M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z',
  route: 'M6 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm12 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM8 6h6a3 3 0 0 1 0 6h-4a3 3 0 0 0 0 6h6',
  package: 'M12 3 3 7.5v9L12 21l9-4.5v-9L12 3Zm0 0v18M3 7.5 12 12l9-4.5',
  flag: 'M5 21V4m0 0h11l-1.5 4L16 12H5',
  fuel: 'M14 21V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v16M4 11h10M9 3v3m8 0 3 3v8a2 2 0 0 1-4 0v-3h1',
  coffee: 'M4 8h12v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8Zm12 1h2a2.5 2.5 0 0 1 0 5h-2M4 21h12',
  bed: 'M3 18V7m0 8h18v3M7 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm4 0h8a2 2 0 0 1 2 2v0',
  refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6',
  check: 'm5 13 4 4L19 7',
  clock: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6M9 17h4',
  printer: 'M7 9V4h10v5M7 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 14h10v7H7z',
  alert: 'M12 8v5m0 3h.01M10.3 3.9 2.5 17a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  gauge: 'M12 14 15 9M21 16a9 9 0 1 0-18 0',
  layers: 'm12 3 9 5-9 5-9-5 9-5Zm9 9-9 5-9-5',
  list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
  calendar: 'M7 3v4M17 3v4M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z',
  shield: 'M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z',
  arrowRight: 'M5 12h14m-6-6 6 6-6 6',
  info: 'M12 16v-5m0-3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  x: 'M6 6l12 12M18 6 6 18',
  sun: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z',
  // Turn-by-turn maneuver glyphs.
  straight: 'M12 21V5M12 5l-4.5 4.5M12 5l4.5 4.5',
  turnRight: 'M7 21v-6a4 4 0 0 1 4-4h7M18 11l-4-4M18 11l-4 4',
  turnLeft: 'M17 21v-6a4 4 0 0 0-4-4H6M6 11l4-4M6 11l4 4',
  merge: 'M6 21l6-9 6 9M12 12V4M12 4l-3.5 3.5M12 4l3.5 3.5',
  ramp: 'M4 20 20 4M20 4h-7M20 4v7',
  roundabout: 'M20 12a8 8 0 1 1-2.3-5.7M20 6v6h-6',
  uturn: 'M8 21V11a4 4 0 0 1 8 0v10M16 21l-3-3M16 21l3-3',
  depart: 'M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18ZM12 16V8m-3 3 3-3 3 3',
  arrive: 'M5 21V4m0 0h11l-1.5 4L16 12H5',
}

export default function Icon({ name, size = 18, strokeWidth = 1.9, ...rest }) {
  const path = PATHS[name] || PATHS.info
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <path d={path} />
    </svg>
  )
}
