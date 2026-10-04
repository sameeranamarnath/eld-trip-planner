import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev` the API calls are proxied to the local Django server so
// the browser never sees a cross-origin request.  In production the frontend
// talks to VITE_API_BASE_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Bind IPv4 explicitly. Vite's default `localhost` can resolve to IPv6 only,
    // which makes http://127.0.0.1:5173 (what verify_contract.py and the README
    // use) refuse connections for reasons that look nothing like a host issue.
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
