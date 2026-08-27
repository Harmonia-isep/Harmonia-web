import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite replaces Create React App (react-scripts), which cannot build against the
// React 19 in package.json. Build output stays in `build/` so the FastAPI
// server's DEFAULT_FRONTEND_DIR and the Playwright e2e fixture are unchanged.
// Client env vars are import.meta.env.VITE_* (see .env.example).
export default defineConfig({
  plugins: [react()],
  build: { outDir: 'build' },
})
