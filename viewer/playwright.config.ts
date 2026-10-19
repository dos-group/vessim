import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/browser', timeout: 30000, fullyParallel: false, workers: 1,
  use: { channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome', headless: true,
    viewport: { width: 1440, height: 1000 }, colorScheme: 'light' },
  reporter: 'list',
  webServer: [
    { command: '../.venv/bin/python -m vessim view ../results/viewer-release/input --port 8721 --no-browser',
      url: 'http://localhost:8721/catalog.json', reuseExistingServer: false, timeout: 30000 },
    { command: '../.venv/bin/python -m http.server 8722 --bind 127.0.0.1 --directory ../results/viewer-release',
      url: 'http://127.0.0.1:8722/report/catalog.json', reuseExistingServer: false, timeout: 30000 },
  ],
})
