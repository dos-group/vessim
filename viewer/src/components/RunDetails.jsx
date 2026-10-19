import { useViewer } from '../context.jsx'
import { columnGroups } from '../model.js'
import { toggle } from '../state.js'
import { Heading, NavLink } from './controls.jsx'
export function RunDetails({ runId }) {
  const { study, patch, presentation: p, navigate } = useViewer()
  const run = study.runs.find((r) => r.key === runId)
  if (!run)
    return (
      <>
        <h1>Run unavailable</h1>
        <NavLink href="#results">Back to results</NavLink>
      </>
    )
  const single = run.configuration.runs.length === 1
  const groups = columnGroups(
    study.columns.filter((c) => c.id in run.values),
    study.singleMicrogrid,
  )
  return (
    <>
      <p className="breadcrumb">
        <NavLink href="#results">{study.name}</NavLink> /{' '}
        {single ? (
          run.configuration.name
        ) : (
          <>
            <button
              className="link"
              onClick={() => {
                patch({
                  mode: 'runs',
                  configFilter: [run.configuration.key],
                  query: '',
                  rowPage: 0,
                })
                navigate('results')
              }}
            >
              {run.configuration.name}
            </button>{' '}
            / {runId}
          </>
        )}
      </p>
      <Heading
        title={single ? run.configuration.name : runId}
        actions={
          <button
            onClick={() => {
              patch((s) => ({
                runs: toggle(s.runs, runId, true),
                timeMode: 'runs',
              }))
              navigate('timeseries')
            }}
          >
            {run.trajectoryUrl
              ? 'Add to time series'
              : 'Inspect recording availability'}
          </button>
        }
      >
        {single ? `Run ${runId}` : `Configuration: ${run.configuration.name}`}
        {run.realization?.id ? ` · ${run.realization.id}` : ''}
      </Heading>
      <section className="panel scroll">
        <table className="inspector-table">
          <thead>
            <tr>
              <th scope="col">Parameter / metric</th>
              <th scope="col">Recorded value</th>
              <th scope="col">Description & assumptions</th>
            </tr>
          </thead>
          {groups.map((group) => (
            <tbody key={group.label}>
              <tr className="inspector-group">
                <th colSpan={3}>{group.label}</th>
              </tr>
              {group.columns.map((c) => {
                const definition = run.definitions[c.id],
                  assumptions = definition?.assumptions
                return (
                  <tr key={c.id}>
                    <th scope="row">{c.label}</th>
                    <td className="number">
                      {p.metricText(c, run.values[c.id])}
                      {p.unit(c) && ` ${p.unit(c)}`}
                    </td>
                    <td>
                      {definition?.description || ''}
                      {assumptions && Object.keys(assumptions).length > 0 && (
                        <details>
                          <summary>Assumptions</summary>
                          <pre>{JSON.stringify(assumptions, null, 2)}</pre>
                        </details>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          ))}
        </table>
      </section>
      <details>
        <summary>Configuration and execution</summary>
        <pre>
          {JSON.stringify(
            {
              parameters: run.record.parameters,
              config: run.record.config,
              execution: run.record.execution,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </>
  )
}
