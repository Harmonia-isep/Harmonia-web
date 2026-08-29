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
    // Pinned to 3000 because the backend's DEFAULT_CORS_ORIGINS allows
    // localhost:3000 (inherited from Create React App). Vite's own default is
    // 5173, which the migration silently broke the split-origin dev flow on.
    // strictPort makes a busy port fail loudly rather than sliding to 3001 and
    // getting blocked by CORS again for a non-obvious reason.
    port: 3000,
    strictPort: true,
  },
})
