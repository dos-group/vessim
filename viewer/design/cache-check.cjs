// Reproduce an old cached script against the new HTML, then upgrade in the same browser.
const { chromium, expect } = require('@playwright/test')
const http = require('node:http')
const fs = require('node:fs/promises')
const path = require('node:path')
const root = path.resolve(__dirname, '../..')

async function check() {
  let upgraded = false
  let legacyRequests = 0
  let versionedRequests = 0
  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://localhost')
      let pathname = decodeURIComponent(url.pathname)
      if (pathname.endsWith('/')) pathname += 'index.html'
      const file = path.resolve(root, '.' + pathname)
      if (!file.startsWith(root + path.sep)) {
        response.writeHead(403).end()
        return
      }
      const type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream'
      response.setHeader('Content-Type', type)
      if (pathname.endsWith('/proposal.js') && !url.search) {
        legacyRequests++
        response.setHeader('Cache-Control', 'public, max-age=3600')
        // The old render() assumed #config-nav existed, and reported UI errors as load errors.
        response.end(`try { document.querySelector('#config-nav').classList.toggle('active', true) }
          catch (error) { document.querySelector('#main').innerHTML = '<h1>Could not load examples</h1><p>' + error.message + '</p>' }`)
        return
      }
      if (pathname.endsWith('/proposal.js')) versionedRequests++
      response.setHeader('Cache-Control', pathname.endsWith('.html') ? 'no-store' : 'public, max-age=3600')
      let body = await fs.readFile(file)
      if (pathname.endsWith('/design/index.html') && !upgraded) body = body.toString().replace('proposal.js?v=analysis-10', 'proposal.js')
      response.end(body)
    } catch {
      response.writeHead(404).end()
    }
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const browser = await chromium.launch({ channel: 'chrome' })
  try {
    const page = await browser.newPage()
    const url = `http://127.0.0.1:${server.address().port}/viewer/design/`
    await page.goto(url)
    await expect(page.getByRole('heading', { name: 'Could not load examples' })).toBeVisible()
    await expect(page.locator('#main')).toContainText('classList')
    upgraded = true
    // Ordinary reload: keep the same context and its cached old JavaScript.
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Results', exact: true })).toBeVisible()
    await expect(page.locator('.results-table tbody tr')).toHaveCount(27)
    expect(legacyRequests).toBe(1)
    expect(versionedRequests).toBe(1)
    // Confirm the actual shared preview as well, not only the reproduction server.
    await page.goto('http://127.0.0.1:8715/viewer/design/?v=analysis-10')
    await expect(page.locator('.results-table tbody tr')).toHaveCount(27)
    console.log('PASS: reproduced old-script classList failure; normal reload upgrades with cache intact; exact shared preview loads 27 runs.')
  } finally {
    await browser.close()
    await new Promise(resolve => server.close(resolve))
  }
}
check().catch(error => { console.error(error); process.exitCode = 1 })
