import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development, /api is forwarded to the team's FastAPI backend (backend/, port 8000),
// so VITE_DATA_SOURCE=http works without CORS settings. Override with VITE_BACKEND_ORIGIN.
const backend = process.env.VITE_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': backend } },
  preview: { proxy: { '/api': backend } },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
