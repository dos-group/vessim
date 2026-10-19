import { test, expect } from '@playwright/test'

for (const [kind, base] of [
  ['CLI', 'http://localhost:8721/'],
  ['export', 'http://127.0.0.1:8722/report/'],
]) {
  test(`${kind}: consistent field order, shared units, stable controls and charts`, async ({
    page,
  }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(`${base}?study=sampling`)
    await expect(page.locator('.results-table tbody > tr')).toHaveCount(3)
    await page.locator('[data-plot-view="scatter"]').click()
    const axisGroups = await page.locator('#x optgroup').evaluateAll((groups) =>
      groups.map((g) => ({
        name: g.label,
        ids: [...g.querySelectorAll('option')].map((o) => o.value),
      })),
    )
    await page.getByText('Columns', { exact: true }).click()
    const columnGroups = await page
      .locator('.column-picker fieldset')
      .evaluateAll((groups) =>
        groups.map((g) => ({
          name: g.querySelector('legend')?.textContent,
          ids: [...g.querySelectorAll('[data-visible]')].map((e) =>
            e.getAttribute('data-visible'),
          ),
        })),
      )
    const axisIds = new Set(axisGroups.flatMap((group) => group.ids))
    expect(axisGroups).toEqual(
      columnGroups
        .map((group) => ({
          ...group,
          ids: group.ids.filter((id) => axisIds.has(id)),
        }))
        .filter((group) => group.ids.length),
    )
    const energy = 'm:["microgrids","Microgrid 1","grid_import","Wh"]'
    await page.locator('#x').selectOption(energy)
    await page
      .getByRole('combobox', {
        name: 'Display unit for horizontal axis',
        exact: true,
      })
      .selectOption('MWh')
    const pickerUnit = page
      .locator('select[data-unit]')
      .filter({ has: page.locator('option[value="MWh"]') })
      .first()
    await expect(pickerUnit).toHaveValue('MWh')
    await pickerUnit.focus()
    await pickerUnit.selectOption('kWh')
    await expect(
      page.getByRole('combobox', {
        name: 'Display unit for horizontal axis',
        exact: true,
      }),
    ).toHaveValue('kWh')
    const axisValues = await page.locator('#scatter').evaluate((el) =>
      (window as any).echarts
        .getInstanceByDom(el)
        .getOption()
        .series[0].data.map((p) => p.value[0]),
    )
    expect(axisValues).toEqual([10, 20, 30])
    // Updating a picker no longer replaces its DOM or loses focus.
    await expect(pickerUnit).toBeFocused()
    await expect(page.locator('.column-picker').first()).toHaveAttribute(
      'open',
      '',
    )
    await page.getByText('Columns', { exact: true }).click()
    await page.locator('#scatter').evaluate((el) => {
      const chart = (window as any).echarts.getInstanceByDom(el)
      ;(window as any).__chart = chart
      chart.dispatchAction({
        type: 'dataZoom',
        dataZoomIndex: 0,
        start: 20,
        end: 80,
      })
    })
    await page.locator('[data-select="config-0"]').check()
    expect(
      await page
        .locator('#scatter')
        .evaluate(
          (el) =>
            (window as any).echarts.getInstanceByDom(el) ===
            (window as any).__chart,
        ),
    ).toBe(true)
    expect(
      await page
        .locator('#scatter')
        .evaluate(
          (el) =>
            (window as any).echarts.getInstanceByDom(el).getOption().dataZoom[0]
              .start,
        ),
    ).toBeCloseTo(20)
    await page.getByRole('button', { name: 'Time series', exact: true }).click()
    await expect(page.locator('.time-chart canvas')).toHaveCount(2)
    await page
      .getByRole('combobox', {
        name: 'Display unit for grid / Power',
        exact: true,
      })
      .selectOption('kW')
    await expect(
      page.locator('[data-signal-panel]').filter({
        has: page.getByRole('heading', { name: 'grid / Power', exact: true }),
      }),
    ).toContainText('kW')
    await page.screenshot({
      path: `../results/viewer-release/${kind}-react-desktop.png`,
      fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true)
    await page.screenshot({
      path: `../results/viewer-release/${kind}-react-mobile.png`,
      fullPage: true,
    })
    expect(errors).toEqual([])
  })
  test(`${kind}: shared results and trajectories reopen independently`, async ({
    page,
    context,
  }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(`${base}?study=sampling`)
    const initialHistory = await page.evaluate(() => history.length)
    await page.locator('[data-plot-view="scatter"]').click()
    await page.locator('#stat').selectOption('mean')
    await page.locator('[data-select="config-1"]').check()
    await expect(page).toHaveURL(/view=/)
    const link = page.url()
    expect(await page.evaluate(() => history.length)).toBe(initialHistory)
    expect(new URL(link).searchParams.get('study')).toBe('sampling')
    const other = await context.newPage()
    other.on('pageerror', (e) => errors.push(e.message))
    await other.goto(link)
    await expect(other.locator('#stat')).toHaveValue('mean')
    await expect(other.locator('[data-plot-view="scatter"]')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await expect(other.locator('[data-select="config-1"]')).toBeChecked()
    await other
      .getByRole('button', { name: 'Time series', exact: true })
      .click()
    await expect(other.locator('.time-chart canvas')).toHaveCount(2)
    await other
      .getByRole('combobox', { name: 'Time alignment', exact: true })
      .selectOption('absolute')
    await other
      .getByRole('button', {
        name: 'Remove battery / State of charge chart',
        exact: true,
      })
      .click()
    await expect
      .poll(
        () =>
          JSON.parse(new URL(other.url()).searchParams.get('view')!).signals
            ?.length,
      )
      .toBe(1)
    const trajectoryLink = other.url()
    await other.goBack()
    await expect(other.locator('#stat')).toHaveValue('mean')
    await expect(other.locator('[data-select="config-1"]')).toBeChecked()
    await other.goForward()
    await expect(other.locator('#alignment')).toHaveValue('absolute')
    await expect(other.locator('.time-chart canvas')).toHaveCount(1)
    await other.reload()
    await expect(other.locator('.time-chart canvas')).toHaveCount(1)
    await expect(other.locator('#alignment')).toHaveValue('absolute')
    await page.goto(trajectoryLink)
    await expect(page.locator('.time-chart canvas')).toHaveCount(1)
    await expect(page.locator('#alignment')).toHaveValue('absolute')
    await expect(page.locator('.selection-order')).toContainText('Setup 2')
    await page.locator('#study').selectOption('comparison')
    await expect(page.locator('.heading')).toContainText('Equipment comparison')
    await page.goBack()
    await expect(page.locator('.time-chart canvas')).toHaveCount(1)
    await expect(page.locator('#alignment')).toHaveValue('absolute')
    expect(errors).toEqual([])
  })
  test(`${kind}: late study responses do not replace the active view`, async ({
    page,
  }) => {
    let release!: () => void
    let requested!: () => void
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const started = new Promise<void>((resolve) => {
      requested = resolve
    })
    let requests = 0
    await page.route('**/data/0/study.json', async (route) => {
      requests++
      const response = await route.fetch()
      requested()
      await held
      await route.fulfill({ response })
    })
    await page.goto(`${base}?study=sampling`)
    await expect(page.locator('.results-table tbody > tr')).toHaveCount(3)
    await page.locator('#study').selectOption('comparison')
    await started
    await page.locator('#study').selectOption('multi')
    await expect(page.locator('.heading')).toContainText('Multiple microgrids')
    const completed = page.waitForResponse('**/data/0/study.json')
    release()
    await completed
    await expect(page.locator('#study')).toHaveValue('multi')
    await expect(page.locator('.heading')).toContainText('Multiple microgrids')
    await expect(page).toHaveURL(/study=multi/)
    await page.locator('#study').selectOption('comparison')
    await expect(page.locator('.heading')).toContainText('Equipment comparison')
    expect(requests).toBe(1)
  })
}
