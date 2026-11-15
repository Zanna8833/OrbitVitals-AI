import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development, /api is forwarded to the team's FastAPI backend (backend/, port 8000),
// so the app works without CORS settings. Override with VITE_BACKEND_ORIGIN.
const backend = process.env.VITE_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'
// The team's assistant service (ai_agent/, port 8100).
const agent = process.env.VITE_AGENT_ORIGIN ?? 'http://127.0.0.1:8100'

export default defineConfig({
  plugins: [react()],
  // The cognition battery (../cognition-frontend) is bundled in: one React for both.
  resolve: { dedupe: ['react', 'react-dom'] },
  build: { chunkSizeWarningLimit: 800 },
  server: { proxy: { '/api': backend, '/agent': agent } },
  preview: { proxy: { '/api': backend, '/agent': agent } },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    // Unit tests run on the offline sample data.
    env: { VITE_DATA_SOURCE: 'mock' },
  },
})
