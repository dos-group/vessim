const { chromium, expect } = require('@playwright/test')
const fs = require('node:fs')
;(async () => {
  const out = require('node:path').resolve(
    __dirname,
    '../../results/viewer-proposal/screenshots-v2',
  )
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome' })
  try {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      }),
      errors = [],
      csv = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('request', (r) => {
      if (r.url().endsWith('.csv')) csv.push(r.url())
    })
    await page.goto(
      process.env.VIEWER_PROPOSAL_URL || 'http://127.0.0.1:8715/viewer/design/',
    )
    await expect(
      page.getByRole('heading', { name: 'Results', exact: true }),
    ).toBeVisible()
    await expect(page.locator('.results-table tbody tr')).toHaveCount(27)
    expect(csv).toHaveLength(0)
    await page
      .locator('#y')
      .selectOption({ label: 'Microgrid: campus · grid emissions (kgCO2e)' })
    await page.screenshot({ path: `${out}/results.png`, fullPage: true })
    const point = await page.evaluate(() => {
      const el = document.querySelector('#scatter'),
        c = window.echarts.getInstanceByDom(el),
        p = c.convertToPixel(
          { seriesIndex: 0 },
          c.getOption().series[0].data[0].value,
        ),
        r = el.getBoundingClientRect()
      return { x: r.left + p[0], y: r.top + p[1] }
    })
    await page.mouse.click(point.x, point.y)
    await expect(page.locator('.selection-toolbar > span')).toHaveText('1 runs selected')
    await expect(
      page.locator('.results-table tbody input:checked'),
    ).toHaveCount(1)
    await page.getByRole('button', { name: 'Clear', exact: true }).click()
    await page
      .getByRole('checkbox', {
        name: 'Select self_consumption-1000-s41',
        exact: true,
      })
      .check()
    await page
      .getByRole('checkbox', {
        name: 'Select peak_shaving-4000-s41',
        exact: true,
      })
      .check()
    await page
      .getByRole('checkbox', {
        name: 'Select carbon_aware-8000-s41',
        exact: true,
      })
      .check()
    const download = page.waitForEvent('download')
    await page
      .getByRole('button', { name: 'Export selected', exact: true })
      .click()
    expect((await download).suggestedFilename()).toBe('recorded-runs.csv')
    expect(csv).toHaveLength(0)
    await page.getByRole('button', { name: 'Time series', exact: true }).click()
    await expect(page.locator('.time-chart canvas')).toHaveCount(2)
    await expect(page.locator('[data-order-key]').first()).toBeVisible()
    await page.locator('[data-order-key="peak_shaving-4000-s41"]').hover()
    const { firstChip, peakChip } = await page.evaluate(() => ({
      firstChip: document.querySelector('[data-order-key]').getBoundingClientRect().toJSON(),
      peakChip: document.querySelector('[data-order-key="peak_shaving-4000-s41"]').getBoundingClientRect().toJSON(),
    }))
    await page.mouse.move(peakChip.x + 14, peakChip.y + peakChip.height / 2)
    await page.mouse.down()
    await page.mouse.move(firstChip.x + firstChip.width / 2, firstChip.y + firstChip.height / 2, { steps: 12 })
    await page.mouse.up()
    await expect(page.locator('[data-order-key]').first()).toHaveAttribute('data-order-key', 'peak_shaving-4000-s41')
    await page.screenshot({ path: `${out}/selected-runs.png`, fullPage: true })
    await expect(page.locator('.time-chart')).toHaveCount(2)
    await expect.poll(() => page.locator('.time-chart canvas').count()).toBe(2)
    expect(csv).toHaveLength(3)
    const chartState = await page.evaluate(() =>
      [...document.querySelectorAll('.time-chart')].map((el) =>
        window.echarts
          .getInstanceByDom(el)
          .getOption()
          .series.map((s) => ({
            name: s.name,
            color: s.lineStyle.color,
            points: s.data.length,
          })),
      ),
    )
    expect(chartState[0]).toHaveLength(3)
    expect(chartState[1]).toHaveLength(3)
    expect(chartState[0].map((s) => s.color)).toEqual(
      chartState[1].map((s) => s.color),
    )
    expect(new Set(chartState[0].map((s) => s.color)).size).toBe(3)
    await page.evaluate(() =>
      window.echarts
        .getInstanceByDom(document.querySelector('.time-chart'))
        .dispatchAction({ type: 'dataZoom', start: 20, end: 60 }),
    )
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            window.echarts
              .getInstanceByDom(document.querySelectorAll('.time-chart')[1])
              .getOption().dataZoom[0].start,
        ),
      )
      .toBe(20)
    await page.getByRole('button', { name: 'Reset zoom' }).click()
    await page.getByLabel('Time alignment').selectOption('absolute')
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            window.echarts
              .getInstanceByDom(document.querySelector('.time-chart'))
              .getOption().xAxis[0].type,
        ),
      )
      .toBe('time')
    await page.getByText('Signals (2)', { exact: true }).click()
    await page
      .getByRole('checkbox', {
        name: 'campus · servers / Power (W)',
        exact: true,
      })
      .check()
    await expect(page.locator('.time-chart')).toHaveCount(3)
    await page.locator('summary').filter({ hasText: 'Signals (3)' }).click()
    await page.screenshot({ path: `${out}/time-series.png`, fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: `${out}/time-mobile.png`, fullPage: true })
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true)
    await page.screenshot({ path: `${out}/time-mobile.png`, fullPage: true })
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.getByRole('link', { name: 'Back to results' }).click()
    await page
      .getByRole('button', { name: 'Configurations', exact: true })
      .click()
    await expect(page.locator('.results-table tbody tr')).toHaveCount(9)
    await page.getByLabel('Metric summary').selectOption('median')
    await page
      .getByRole('checkbox', {
        name: 'Select Self consumption / 1 kWh',
        exact: true,
      })
      .check()
    await page
      .getByRole('checkbox', {
        name: 'Select Peak shaving / 4 kWh',
        exact: true,
      })
      .check()
    await page.getByRole('button', { name: 'Inspect runs', exact: true }).click()
    await expect(page.locator('.results-table tbody tr')).toHaveCount(6)
    await page
      .getByRole('combobox', { name: 'Study', exact: true })
      .selectOption('optuna-recorded')
    await expect(page.locator('.results-table tbody tr')).toHaveCount(8)
    await page
      .getByRole('combobox', { name: 'Study', exact: true })
      .selectOption('recorded')
    await expect(page.locator('.results-table tbody tr')).toHaveCount(6)
    await expect(page.locator('#run-count')).toHaveText('3')
    await page
      .getByRole('combobox', { name: 'Study', exact: true })
      .selectOption('fixed')
    await expect(page.locator('.results-table tbody tr')).toHaveCount(22)
    await expect(page.locator('#status')).toHaveCount(0)
    await page.locator('[data-select="c01-r01"]').check()
    await page.getByRole('button', { name: 'Time series', exact: true }).click()
    await expect(
      page.getByText('c01-r01: no trajectory was recorded.', { exact: true }),
    ).toBeVisible()
    expect(errors).toEqual([])
    console.log(
      'PASS: custom axes, linked point selection, export, configurations/runs, selection order, lazy 3-run overlays, shared zoom, 3 signals, UTC alignment, mobile, study state, missing recordings.',
    )
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exitCode = 1
})
