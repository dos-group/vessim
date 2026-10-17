// Validate actual annual data, lazy recording loads, and full-resolution week zoom.
const { chromium, expect } = require('@playwright/test')
const fs = require('node:fs')
const path = require('node:path')

;(async () => {
  const out = path.resolve(__dirname, '../../results/viewer-proposal/screenshots-annual')
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome' })
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
    page.setDefaultTimeout(10000)
    const errors = [], csv = []
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('request', (request) => {
      if (request.url().endsWith('.csv')) csv.push(request.url())
    })
    const started = performance.now()
    await page.goto('http://127.0.0.1:8715/viewer/design/?study=infrastructure-year&v=analysis-10')
    await expect(page.locator('.results-table tbody tr')).toHaveCount(8)
    await expect(page.locator('#y option:checked')).toHaveText('Microgrid: site · grid emissions (tCO2e)')
    expect(csv).toHaveLength(0)
    const summaryMs = performance.now() - started
    await page.screenshot({ path: `${out}/annual-results.png`, fullPage: true })
    for (const name of ['grid-only', 'mixed', 'mixed-storage']) {
      await page.locator(`[data-select="${name}"]`).check()
    }
    const overlayStart = performance.now()
    await page.getByRole('button', { name: 'Time series' }).click()
    await expect(page.locator('.time-chart canvas')).toHaveCount(2)
    expect(csv).toHaveLength(3)
    const lengths = await page.evaluate(() =>
      window.echarts.getInstanceByDom(document.querySelector('.time-chart')).getOption().series.map(s => s.data.length)
    )
    expect(lengths).toEqual([8760, 8760, 8760])
    const overlayMs = performance.now() - overlayStart
    await expect(page.locator('#main')).toContainText('Signal missing in: grid-only, mixed')
    await page.getByLabel('Time alignment').selectOption('absolute')
    await page.evaluate(() => {
      const chart = window.echarts.getInstanceByDom(document.querySelector('.time-chart'))
      chart.dispatchAction({ type: 'dataZoom', start: 40, end: 42 })
    })
    await expect.poll(() => page.evaluate(() =>
      window.echarts.getInstanceByDom(document.querySelectorAll('.time-chart')[1]).getOption().dataZoom[0].start
    )).toBe(40)
    await page.screenshot({ path: `${out}/annual-week-overlay.png`, fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: `${out}/annual-mobile.png`, fullPage: true })
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.locator('#study').selectOption('infrastructure-search')
    await page.locator('#results-nav').click()
    await expect(page.locator('.results-table tbody tr')).toHaveCount(24)
    expect(csv).toHaveLength(3)
    await page.screenshot({ path: `${out}/annual-optuna.png`, fullPage: true })
    await page.goto('http://127.0.0.1:8090/')
    await page.getByRole('link', { name: 'infrastructure-emissions' }).click()
    await expect(page.getByText('Pareto Front', { exact: true })).toBeVisible()
    await page.screenshot({ path: `${out}/optuna-dashboard.png`, fullPage: true })
    expect(errors).toEqual([])
    const report = { summaryMs, overlayMs, pointsPerSeries: lengths, optunaUrl: page.url(), errors }
    fs.writeFileSync(`${out}/validation.json`, JSON.stringify(report, null, 2))
    console.log(JSON.stringify(report))
  } finally {
    await browser.close()
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
