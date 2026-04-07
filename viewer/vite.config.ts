import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'node:fs'
import path from 'node:path'

function parseYamlStatus(filePath: string): string | null {
  try {
    const text = fs.readFileSync(filePath, 'utf-8')
    const match = text.match(/^\s*status:\s*(\S+)/m)
    return match ? match[1] : null
  } catch {
    return null
  }
}

function resultsPlugin(resultsDir: string): Plugin {
  const absDir = path.resolve(resultsDir)

  return {
    name: 'vessim-results',
    configureServer(server) {
      // /experiments — return JSON list of discovered experiments
      server.middlewares.use('/experiments', (_req, res) => {
        const rootConfig = path.join(absDir, 'experiment.yaml')
        let response: { mode: string; experiments: { name: string; status: string | null }[] }

        if (fs.existsSync(rootConfig)) {
          response = {
            mode: 'single',
            experiments: [{ name: '', status: parseYamlStatus(rootConfig) }],
          }
        } else {
          const experiments: { name: string; status: string | null }[] = []
          for (const entry of fs.readdirSync(absDir).sort()) {
            const subdir = path.join(absDir, entry)
            const configFile = path.join(subdir, 'experiment.yaml')
            if (fs.statSync(subdir).isDirectory() && fs.existsSync(configFile)) {
              experiments.push({ name: entry, status: parseYamlStatus(configFile) })
            }
          }
          response = { mode: 'multi', experiments }
        }

        const body = JSON.stringify(response)
        res.writeHead(200, {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
        })
        res.end(body)
      })

      // /results/* — serve files from resultsDir
      server.middlewares.use('/results', (req, res, next) => {
        const filePath = path.join(absDir, req.url || '/')
        if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
          next()
          return
        }
        const ext = path.extname(filePath).toLowerCase()
        const contentType =
          ext === '.yaml' || ext === '.yml'
            ? 'text/yaml'
            : ext === '.csv'
              ? 'text/csv'
              : 'application/octet-stream'
        res.writeHead(200, { 'Content-Type': contentType })
        fs.createReadStream(filePath).pipe(res)
      })
    },
  }
}

const resultsDir = process.env.VITE_RESULTS_DIR

export default defineConfig({
  plugins: [react(), tailwindcss(), ...(resultsDir ? [resultsPlugin(resultsDir)] : [])],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BROKER_URL ?? 'http://localhost:8700',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
