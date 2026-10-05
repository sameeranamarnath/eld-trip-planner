# ELD Trip Planner

Give it where the truck is now, a pickup, a drop-off and how many hours are already used on the
70-hour cycle, and it returns:

- a legal **truck route** on a map, with every required stop pinned at the mile it happens,
- a filled-out **FMCSA daily log sheet for every calendar day** of the trip,
- a **turn-by-turn instruction list** for the whole route - maneuver, distance, duration and
  running mileage per step,
- a printable **PDF of the sheets**, one landscape page per day.

Stack: **Django 5.2 + DRF** behind **Vite + React 18 + Leaflet**. The backend is stateless -
every plan is computed per request - so it deploys to serverless or to a container with no
database. The frontend ships light and dark themes; the log sheet stays white in both, because
it is a paper form.

## How it works

1. **Geocode** - the three locations resolve through Nominatim, with live type-ahead in the form
   (`GET /api/v1/places/?q=`).
2. **Route** - OSRM returns the road route. The polyline is interpolated by distance, so any mile
   marker maps back to a real coordinate for stop placement.
3. **Simulate hours of service** - `HosSimulator` walks the route leg by leg. Before each driving
   chunk it asks what the law requires next, then drives only as far as the tightest of the five
   caps allows.
4. **Build the logs** - a second pass slices the simulated duty segments into 24-hour grids,
   clipping each day at midnight, and renders one log sheet per day with brackets, numbered
   remark flags, per-line totals and the seven-day recap.

Every external dependency is keyless and free: OSRM (routing), Nominatim (geocoding), Photon
(reverse geocoding), OpenStreetMap tiles (map).

## Hours-of-service rules modelled

Property carrier, 70 hours / 8 days, no adverse driving conditions:

| Rule | Value |
| --- | --- |
| Driving limit | 11 hours per shift |
| On-duty window | 14 hours per shift |
| Break | 30 min after 8 hours of cumulative driving |
| Reset | 10 consecutive hours off duty |
| Cycle | 70 hours / 8 days, 34-hour restart to clear it |
| Fuel | at least every 1,000 miles |

Fixed duty events: 30-min pre-trip, 60-min pickup, 60-min drop-off, 30-min post-trip, 30-min
fuel stop. A break and an imminent fuel stop are merged into a single stop when the remaining
fuel distance falls inside the break window.

The drawn sheet carries all eleven elements 49 CFR 395.8(d) requires, and its header states
which time base the grid is on. Times are naive local time at the home terminal.

## Running it locally

### Backend

```bash
python -m venv .venv
source .venv/bin/activate                    # macOS / Linux
.venv/Scripts/activate                       # Windows
pip install -r backend/requirements.txt
cd backend
python manage.py runserver 8090
```

The API is then on `http://127.0.0.1:8090`; `GET /` lists the endpoints.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health/` | liveness probe |
| `GET /api/v1/places/?q=Chicago,IL` | place search for the form |
| `POST /api/v1/plan/` | the whole plan: route, stops, summary, log sheets |

### Frontend

```bash
cd frontend
npm install
npm run dev                                  # http://127.0.0.1:5173
```

The dev server proxies `/api/*` to `127.0.0.1:8090` (see `vite.config.js`), so nothing needs
configuring locally. For any other setup, copy `frontend/.env.example` to `.env` and set
`VITE_API_BASE_URL` to the backend's origin.

## Tests

```bash
cd backend
python manage.py test                        # offline suite: no network, no fixtures
```

`backend/eld/tests/` covers the HOS simulator, the log builder, the geocoder ranking and the API
contract. Two further checks talk to the live OSM services:

```bash
cd backend
python scripts/smoke_plan.py "Green Bay, WI" "Chicago, IL" "Nashville, TN" 0
python scripts/verify_contract.py http://127.0.0.1:8090/api/v1
```

The first prints a full plan - summary, legs, stops and every sheet; the second posts
`scripts/sample_request.json` and asserts that every field the UI reads is present, plus the HOS
invariants that hold for any plan.

Frontend: `npm run lint`, and `npm run build` writes `dist/`.

## Deployment

Two pieces, deployed separately.

**Backend** - either route:

- **Serverless (Vercel)** - push `backend/`. Vercel's Django preset resolves the app from
  `WSGI_APPLICATION`, so no `rewrites` are needed; `backend/vercel.json` only raises the function
  timeout to 60 s, and `backend/api/index.py` exposes the same WSGI callable as `app` for
  runtimes that look for that name.
- **Docker** - `docker build -t eld-trip-planner . && docker run -p 8000:8000 spotter-eld`. Works
  anywhere that runs containers (Fly.io, Railway, Cloud Run); the image serves the API through
  gunicorn.

**Frontend** - deploy `frontend/` to Vercel; `frontend/vercel.json` is already set up for Vite
with an SPA rewrite. Point `VITE_API_BASE_URL` at the backend's `/api/v1` origin and make sure
the backend's CORS setting covers it.

Environment variables, all optional and defaulted in `backend/config/settings.py`:
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOW_ALL_ORIGINS`,
`DJANGO_LOG_LEVEL`, plus the `SPOTTER_*` overrides for service URLs, timeouts and cache sizes.

## Layout

```
backend/               Django project
  config/              settings, urls, wsgi/asgi
  eld/                 the app
    services/          http, geocoding, routing, hos (the simulator), logs, planner
    tests/             offline unit suite
  scripts/             smoke_plan.py, verify_contract.py, sample_request.json
  api/index.py         WSGI shim for serverless Python runtimes
frontend/              Vite + React app
  src/components/      one component per panel
  src/*.js             api, format, markers, logHeader, useTheme
Dockerfile             container image for the backend
```

Naming: Python modules and functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`;
React components `PascalCase.jsx`, hooks `useX.js`, other modules camelCase `.js`; Markdown and
asset filenames kebab-case. Everything is UTF-8.
