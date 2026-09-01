import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite replaces Create React App (react-scripts), which cannot build against the
// React 19 in package.json. Build output stays in `build/` so the FastAPI
// server's DEFAULT_FRONTEND_DIR and the Playwright e2e fixture are unchanged.
// Client env vars are import.meta.env.VITE_* (see .env.example).
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'build' },
  server: {
    // Pinned to 3000, and strictPort so a busy port fails loudly rather than
    // sliding to 3001 and behaving differently for a non-obvious reason.
    port: 3000,
    strictPort: true,
    // The dev server proxies /api to the backend, so the browser only ever
    // talks to one origin, exactly like the single-process build. Development
    // therefore needs no VITE_API_URL and involves no CORS.
    //
    // Before this, dev worked only because api.js defaulted to an absolute
    // http://localhost:8000 and the backend allowlisted localhost:3000. That
    // default is what made the launcher path unusable, so it is gone, and dev
    // gets a proxy instead of a hardcoded host.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
