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
    const axisGroups = await page
      .locator('#x optgroup')
      .evaluateAll((groups) =>
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
      page
        .locator('[data-signal-panel]')
        .filter({
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
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    await page.goto(`${base}?study=sampling`)
    await page.locator('[data-plot-view="scatter"]').click()
    await page.locator('#stat').selectOption('mean')
    await page.locator('[data-select="config-1"]').check()
    await page.getByRole('button', { name: 'Copy link', exact: true }).click()
    await expect(page.getByRole('status')).toHaveText('Link copied')
    const link = await page.evaluate(() => navigator.clipboard.readText())
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
    await other.getByRole('button', { name: 'Copy link', exact: true }).click()
    await expect(other.getByRole('status')).toHaveText('Link copied')
    const trajectoryLink = await other.evaluate(() =>
      navigator.clipboard.readText(),
    )
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
}
