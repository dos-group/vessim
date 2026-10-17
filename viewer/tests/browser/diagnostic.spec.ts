import { expect, test } from '@playwright/test'
import fs from 'node:fs'

test('optional Optuna Dashboard: Pareto front, history, and trial attributes', async ({
  page,
}) => {
  test.skip(
    !process.env.OPTUNA_DASHBOARD_URL,
    'Set OPTUNA_DASHBOARD_URL to evaluate the optional integration',
  )
  await page.goto(process.env.OPTUNA_DASHBOARD_URL!)
  await page
    .getByText('battery-cost-emissions', { exact: false })
    .first()
    .click()
  await expect(page.getByText('Pareto Front', { exact: true })).toBeVisible()
  await expect(page.getByText('Best Trials', { exact: true })).toBeVisible()
  await page.screenshot({
    path: '../results/viewer-validation/optuna-dashboard.png',
    fullPage: true,
  })
  await page.getByText('Trial 0', { exact: true }).click()
  await expect(
    page.getByText('vessim_run_id trial-00000', { exact: false }),
  ).toBeVisible()
  fs.writeFileSync(
    '../results/viewer-validation/optuna-trial.txt',
    await page.locator('body').innerText(),
  )
  await page.screenshot({
    path: '../results/viewer-validation/optuna-trial.png',
    fullPage: true,
  })
  const viewerAttribute = await page
    .getByText('vessim_viewer http', { exact: false })
    .innerText()
  const recordedUrl = viewerAttribute.match(/https?:\/\/\S+/)?.[0]
  expect(recordedUrl).toBeTruthy()
  await page.goto(
    process.env.VIEWER_OPTUNA_URL
      ? `${process.env.VIEWER_OPTUNA_URL}/#run=trial-00000`
      : recordedUrl!,
  )
  await expect(
    page.getByRole('heading', { name: 'trial-00000', exact: true }),
  ).toBeVisible()
})
