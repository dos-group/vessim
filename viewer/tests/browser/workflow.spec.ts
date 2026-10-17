import { expect, test } from '@playwright/test'
import fs from 'node:fs'

const small = process.env.VIEWER_TEST_URL || 'http://localhost:8711'
const large = process.env.VIEWER_LARGE_URL || 'http://localhost:8712'
const artifacts = '../results/viewer-validation'
fs.mkdirSync(artifacts, { recursive: true })

test('study selection, comparison, lazy recordings, export, and mobile layout', async ({
  page,
}) => {
  const errors: string[] = []
  const recordings: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => {
    if (r.url().includes('/data/')) recordings.push(r.url())
  })
  await page.goto(small)
  await expect(
    page.getByRole('heading', { name: 'Explore the possibilities.' }),
  ).toBeVisible()
  await expect(page.locator('.run-table tbody tr')).toHaveCount(12)
  expect(recordings).toHaveLength(0)
  await page.screenshot({
    path: `${artifacts}/study-desktop.png`,
    fullPage: true,
  })
  await page
    .getByRole('checkbox', {
      name: 'Select self_consumption-1000',
      exact: true,
    })
    .check()
  await page
    .getByRole('checkbox', {
      name: 'Select self_consumption-5000',
      exact: true,
    })
    .check()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export selected' }).click()
  expect((await download).suggestedFilename()).toContain('selected.csv')
  await page.getByRole('button', { name: 'Compare (2)' }).click()
  await expect(
    page.getByRole('heading', { name: 'Understand the difference.' }),
  ).toBeVisible()
  await page
    .getByLabel('Baseline', { exact: true })
    .selectOption({ label: 'self_consumption-5000' })
  expect(recordings).toHaveLength(0)
  await page.screenshot({
    path: `${artifacts}/comparison.png`,
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Load trajectory comparison' }).click()
  await expect(page.getByLabel('Shared signal')).toBeVisible()
  expect(recordings).toHaveLength(2)
  await page.getByLabel('Align by').selectOption('absolute')
  await page.screenshot({ path: `${artifacts}/overlay.png`, fullPage: true })
  await page
    .locator('.comparison-card')
    .filter({ hasText: 'self_consumption-1000' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Outcomes & assumptions' }),
  ).toBeVisible()
  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(
    page.getByRole('heading', { name: 'Power balance' }),
  ).toBeVisible()
  await page.screenshot({ path: `${artifacts}/inspector.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true)
  await page.screenshot({
    path: `${artifacts}/inspector-mobile.png`,
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Back to study' }).click()
  await page.screenshot({
    path: `${artifacts}/study-mobile.png`,
    fullPage: true,
  })
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true)
  expect(errors).toEqual([])
})

test('10,000 summaries: bounded DOM, search, range filtering, sorting, paging', async ({
  page,
}) => {
  const requests: string[] = []
  const errors: string[] = []
  page.on('request', (r) => requests.push(r.url()))
  page.on('pageerror', (e) => errors.push(e.message))
  const started = Date.now()
  await page.goto(large)
  await expect(page.locator('.run-table tbody tr')).toHaveCount(50)
  const readyMs = Date.now() - started
  await expect(page.getByText('10,000', { exact: true }).first()).toBeVisible()
  const searchStarted = Date.now()
  await page
    .getByRole('textbox', { name: 'Search runs' })
    .fill('scenario-09999')
  await expect(page.locator('.run-table tbody tr')).toHaveCount(1)
  const searchMs = Date.now() - searchStarted
  await page.getByRole('button', { name: 'Reset filters' }).click()
  await expect(page.locator('.run-table tbody tr')).toHaveCount(50)
  await page.getByRole('button', { name: 'Run ↑', exact: true }).click()
  await expect(page.locator('.run-table tbody tr').first()).toContainText(
    'scenario-09999',
  )
  await page.getByRole('button', { name: 'Run ↓', exact: true }).click()
  await page
    .getByLabel('Numeric filter field')
    .selectOption({ label: 'Parameter · capacity wh' })
  await page.getByLabel('Minimum value').fill('9900')
  await expect(page.locator('.run-table tbody tr')).toHaveCount(50)
  const filteredText = await page.locator('.pagination').innerText()
  await page.getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Next page' }).click()
  await expect(page.locator('.pagination')).toContainText('Page 2 / 200')
  expect(requests.filter((url) => url.includes('/trajectory'))).toHaveLength(0)
  await page.screenshot({
    path: `${artifacts}/large-study.png`,
    fullPage: true,
  })
  const metrics = await page.evaluate(() => ({
    catalogMs: performance.getEntriesByName('vessim-catalog-ready').at(-1)
      ?.duration,
    domNodes: document.querySelectorAll('*').length,
    tableRows: document.querySelectorAll('.run-table tbody tr').length,
    heapBytes: (
      performance as Performance & { memory?: { usedJSHeapSize: number } }
    ).memory?.usedJSHeapSize,
  }))
  fs.writeFileSync(
    `${artifacts}/performance.json`,
    JSON.stringify({ readyMs, searchMs, filteredText, ...metrics }, null, 2),
  )
  expect(errors).toEqual([])
  await page
    .getByRole('button', { name: 'scenario-00050', exact: false })
    .click()
  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(
    page.getByRole('heading', { name: 'A compact result, ready to compare' }),
  ).toBeVisible()
})

test('single experiment: CSV recording, missing artifact, and partial catalog', async ({
  page,
  request,
}) => {
  const catalog = await (await request.get(`${small}/catalog.json`)).json()
  const run = catalog.runs[0]
  run.trajectory = { url: 'data/csv/trajectory' }
  const payload = {
    name: 'CSV recording',
    runs: [run],
    errors: ['Another experiment has an unsupported version.'],
  }
  await page.route('**/catalog.json', (route) =>
    route.fulfill({ json: payload }),
  )
  await page.route('**/data/csv/trajectory', (route) =>
    route.fulfill({
      contentType: 'text/csv',
      body: 'microgrid,time,p_grid,actor_states.custom.temperature\ncampus,2026-01-01T00:00:00Z,-100,42\ncampus,2026-01-01T00:01:00Z,-120,43\n',
    }),
  )
  await page.goto(small)
  await expect(
    page.getByRole('heading', { name: 'Outcomes & assumptions' }),
  ).toBeVisible()
  await expect(
    page.getByText('1 records or artifacts need attention'),
  ).toBeVisible()
  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(
    page.getByRole('heading', { name: 'Power balance' }),
  ).toBeVisible()
  await expect(
    page.getByText('Unit not recorded', { exact: true }),
  ).toBeVisible()
  await page.unroute('**/data/csv/trajectory')
  await page.route('**/data/csv/trajectory', (route) =>
    route.fulfill({ status: 404, body: 'Missing' }),
  )
  await page.reload()
  await page.getByRole('tab', { name: 'Time series' }).click()
  await expect(
    page.getByText('The recorded trajectory could not be loaded.', {
      exact: false,
    }),
  ).toBeVisible()
  await page.getByRole('tab', { name: 'Metrics', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Outcomes & assumptions' }),
  ).toBeVisible()
})

test('dark theme, tablet, and static subdirectory export', async ({ page }) => {
  await page.goto(small)
  await page
    .getByRole('heading', { name: 'Explore the possibilities.' })
    .waitFor()
  await page.getByRole('button', { name: 'Toggle color theme' }).click()
  await expect(page.locator('html')).toHaveClass('dark')
  await page.screenshot({
    path: `${artifacts}/study-dark.png`,
    fullPage: true,
    animations: 'disabled',
  })
  await page.setViewportSize({ width: 900, height: 1000 })
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true)
  await page.screenshot({
    path: `${artifacts}/study-tablet.png`,
    fullPage: true,
  })
  if (process.env.VIEWER_STATIC_URL) {
    await page.goto(process.env.VIEWER_STATIC_URL)
    await expect(page.locator('.run-table tbody tr')).toHaveCount(12)
    await page
      .getByRole('button', { name: 'self_consumption-1000', exact: false })
      .click()
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(
      page.getByRole('heading', { name: 'Power balance' }),
    ).toBeVisible()
  }
})

test('comparison shows metadata differences without hiding same-unit deltas', async ({
  page,
  request,
}) => {
  const catalog = await (await request.get(`${small}/catalog.json`)).json()
  catalog.runs = catalog.runs.slice(0, 2)
  catalog.runs[1].record.metric_definitions.run.battery_capex.description =
    'Revised description'
  catalog.runs[1].record.metric_definitions.run.battery_capex.assumptions = {
    source: 'Other quote',
  }
  await page.route('**/catalog.json', (route) =>
    route.fulfill({ json: catalog }),
  )
  await page.goto(small)
  for (const run of catalog.runs) {
    await page
      .getByRole('checkbox', {
        name: `Select ${run.record.run_id}`,
        exact: true,
      })
      .check()
  }
  await page.getByRole('button', { name: 'Compare (2)' }).click()
  const row = page
    .locator('.comparison-table tr')
    .filter({ hasText: 'battery capex' })
  await expect(
    row.getByText('Description differs', { exact: true }),
  ).toBeVisible()
  await expect(
    row.getByText('Assumptions differ', { exact: true }),
  ).toBeVisible()
  await expect(row.locator('.delta')).toContainText('+')
  await expect(row.locator('.delta')).not.toContainText('no delta')
})
