import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// One data implementation: run `python -m vessim view PATH --no-browser`
// alongside Vite. Production and static exports use relative URLs.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: { outDir: '../vessim/_viewer_dist', emptyOutDir: true },
  server: {
    proxy: Object.fromEntries(
      ['/catalog.json', '/data'].map((path) => [
        path,
        { target: process.env.VITE_RESULTS_URL ?? 'http://localhost:8710' },
      ]),
    ),
  },
})
