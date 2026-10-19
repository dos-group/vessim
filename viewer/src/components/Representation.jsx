import { Select, Checkbox, Segmented } from './controls.jsx'
import { useViewer } from '../context.jsx'
import { inSelectionOrder } from '../state.js'
import { human } from '../model.js'

export function Representation({ trajectory = false }) {
  const { study, view: s, patch } = useViewer()
  if (study.singleRun) return null
  const mode = trajectory ? 'timeMode' : 'mode',
    configKey = trajectory ? 'timeConfigs' : 'configs'
  const stat = trajectory ? 'timeStat' : 'stat',
    spread = trajectory ? 'timeSpread' : 'spread'
  const individuals = trajectory ? 'timeIndividuals' : 'plotIndividuals'
  const distribution = !trajectory && s.plot && s.plotType === 'ecdf'
  function changeMode(next) {
    patch((current) => ({
      [mode]: next,
      rowPage: 0,
      ...(next === 'runs'
        ? {
            runs: new Set(
              inSelectionOrder(
                study.configurations,
                current[configKey],
              ).flatMap((c) => c.runs.map((r) => r.key)),
            ),
          }
        : {
            [configKey]: new Set(
              inSelectionOrder(study.runs, current.runs).map(
                (r) => r.configuration.key,
              ),
            ),
          }),
    }))
  }
  return (
    <div
      className="representation"
      role="group"
      aria-label={`${trajectory ? 'Time series' : 'Results'} display`}
    >
      <span>Show</span>
      <Segmented
        label="Representation"
        value={s[mode]}
        onChange={changeMode}
        options={[
          { value: 'runs', label: 'Individual runs' },
          { value: 'configurations', label: 'Configuration summaries' },
        ]}
      />
      {s[mode] === 'configurations' && (
        <>
          <Select
            id={stat}
            label={distribution ? 'Table statistic' : 'Statistic'}
            value={s[stat]}
            onChange={(v) => patch({ [stat]: v })}
            options={['median', 'mean', 'min', 'max'].map((value) => ({
              value,
              label: human(value),
            }))}
          />
          {!distribution && (
            <>
              <Select
                id={spread}
                label="Spread"
                value={s[spread]}
                onChange={(v) => patch({ [spread]: v })}
                options={[
                  { value: 'range', label: 'Full range' },
                  { value: 'iqr', label: 'Middle 50%' },
                  { value: 'none', label: 'None' },
                ]}
              />
              <Checkbox
                id={individuals}
                label="Show individual runs"
                checked={s[individuals]}
                onChange={(v) => patch({ [individuals]: v })}
              />
            </>
          )}
        </>
      )}
    </div>
  )
}
