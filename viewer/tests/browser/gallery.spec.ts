import { test, expect } from '@playwright/test'

// Optional validation of the real, generated annual/Optuna/Monte Carlo examples.
const base = process.env.VIEWER_GALLERY_URL
test('recorded gallery: annual overlays, Optuna outcomes and Monte Carlo distributions', async ({page}) => {
  test.skip(!base, 'Generate the documentation gallery and set VIEWER_GALLERY_URL')
  const errors: string[] = [], recordings: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', r => { if (r.url().includes('/trajectory')) recordings.push(r.url()) })
  await page.goto(`${base}?study=infrastructure-year`)
  const rows = page.locator('.results-table tbody > tr')
  await expect(rows).toHaveCount(8)
  expect(recordings).toHaveLength(0)
  for (const key of ['wind','mixed-storage']) await page.locator(`[data-select="${key}"]`).check()
  await page.getByRole('button',{name:'Time series',exact:true}).click()
  await expect(page.locator('.time-chart canvas')).toHaveCount(2)
  expect(await page.locator('.time-chart').first().evaluate(el =>
    (window as any).echarts.getInstanceByDom(el).getOption().series.map(s => s.data.length))).toEqual([8760,8760])
  await page.screenshot({path:'../results/viewer-release/annual-overlay.png',fullPage:true})
  await page.locator('#study').selectOption('optuna-search')
  await expect(rows).toHaveCount(50)
  await expect(page.locator('.table-footer')).toContainText('100 matching configurations')
  await page.locator('[data-plot-view="scatter"]').click()
  await page.locator('#pareto').check()
  // Emissions assumptions include differing battery rates in these recordings.
  // Keep that compatibility guard, then exercise a consistently defined pair.
  await expect(page.locator('#plot-note')).toContainText('Pareto front unavailable for incompatible results')
  await page.locator('#y').selectOption('m:["microgrids","Microgrid 1","grid_import","Wh"]')
  expect(await page.locator('#scatter').evaluate(el => (window as any).echarts.getInstanceByDom(el)
    .getOption().series.find(s=>s.name==='Pareto front').data.length)).toBeGreaterThan(0)
  await page.screenshot({path:'../results/viewer-release/optuna.png',fullPage:true})
  await page.locator('#study').selectOption('optuna-2')
  await expect(rows).toHaveCount(3)
  await expect(page.locator('.heading')).toContainText('3000 runs')
  await page.locator('[data-plot-view="ecdf"]').click()
  expect(await page.locator('#scatter').evaluate(el => (window as any).echarts.getInstanceByDom(el)
    .getOption().series[0].data.at(-1).value[1])).toBe(100)
  await page.getByRole('button',{name:'Individual runs',exact:true}).click()
  await expect(rows).toHaveCount(50)
  await expect(page.locator('.table-footer')).toContainText('3000 matching runs')
  expect(errors).toEqual([])
})
