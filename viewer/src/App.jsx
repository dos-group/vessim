import { useCallback, useEffect, useMemo, useState } from 'react'
import { ViewerContext } from './context.jsx'
import { presentation } from './presentation.js'
import { RecordingStore } from './recordings.js'
import { Results } from './components/Results.jsx'
import { TimeSeries } from './components/TimeSeries.jsx'
import { RunDetails } from './components/RunDetails.jsx'
import { Issues, NavLink, Select } from './components/controls.jsx'
import logo from './logo.svg'
import { navigate, useNavigation, useViewState } from './navigation.js'
import { json, useStudy } from './study.js'

export default function App() {
  const route = useNavigation(),
    { url } = route
  const [catalog, setCatalog] = useState(null),
    [catalogError, setCatalogError] = useState('')
  const [recordings] = useState(() => new RecordingStore())
  const active =
    url.searchParams.get('study') || catalog?.studies[0]?.study_id || ''
  const page = url.hash.slice(1) || 'results'
  const { study, error } = useStudy(catalog, active)
  const [view, patch] = useViewState(study, route)
  useEffect(() => {
    const abort = new AbortController()
    json(new URL('catalog.json', location.href), abort.signal)
      .then((value) => {
        if (!Array.isArray(value.studies))
          throw new Error('Invalid viewer catalog')
        setCatalog(value)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setCatalogError(e.message)
      })
    return () => abort.abort()
  }, [])
  useEffect(() => () => recordings.dispose(), [recordings])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [active, page])
  const openTimeSeries = useCallback(() => {
    patch((s) =>
      s.mode === 'configurations' && s.configs.size
        ? { timeConfigs: new Set(s.configs), timeMode: 'configurations' }
        : s.mode === 'runs' && s.runs.size
          ? { timeMode: 'runs' }
          : {},
    )
    navigate('timeseries')
  }, [patch])
  const context = useMemo(
    () =>
      study && view
        ? {
            study,
            view,
            patch,
            presentation: presentation(study, view),
            recordings,
            navigate,
            openTimeSeries,
          }
        : null,
    [study, view, patch, recordings, openTimeSeries],
  )
  const visibleError = catalogError || error
  const count =
    view?.timeMode === 'configurations'
      ? study.configurations
          .filter((c) => view.timeConfigs.has(c.key))
          .reduce((n, c) => n + c.runs.length, 0)
      : view?.runs.size || 0
  let runId = ''
  try {
    runId = decodeURIComponent(page.slice(4))
  } catch {
    /* Malformed links return to results. */
  }
  return (
    <div className="shell">
      <aside>
        <NavLink className="brand" href="#results">
          <img src={logo} alt="" />
          Vessim
        </NavLink>
        <Select
          id="study"
          label="Study"
          value={active}
          onChange={(id) => navigate('results', id)}
          disabled={!catalog?.studies.length}
          options={
            catalog?.studies.map((entry) => ({
              value: entry.study_id,
              label: entry.name,
            })) || [{ value: '', label: 'Loading studies…' }]
          }
        />
        <nav aria-label="Study">
          <NavLink
            id="results-nav"
            href="#results"
            className={page !== 'timeseries' ? 'active' : ''}
          >
            Results
          </NavLink>
          <a
            id="timeseries-nav"
            href="#timeseries"
            className={page === 'timeseries' ? 'active' : ''}
            onClick={(e) => {
              e.preventDefault()
              if (page === 'results') openTimeSeries()
              else navigate('timeseries')
            }}
          >
            Time series <span id="run-count">{count}</span>
          </a>
        </nav>
      </aside>
      <div className="main-area">
        <div id="catalog-notice">
          <Issues errors={catalog?.errors} />
        </div>
        <main id="main" aria-live="polite">
          {visibleError ? (
            <>
              <h1>Could not open results</h1>
              <p>{visibleError}</p>
            </>
          ) : catalog?.studies.length === 0 ? (
            <>
              <h1>No studies available</h1>
              <p>
                Open an experiment, a study.json file, or a directory of
                recorded experiments with vessim view.
              </p>
            </>
          ) : !context ? (
            <p role="status">Loading recorded summaries…</p>
          ) : (
            <ViewerContext.Provider value={context}>
              <div key={active}>
                {page === 'timeseries' ? (
                  <TimeSeries />
                ) : page.startsWith('run/') && runId ? (
                  <RunDetails runId={runId} />
                ) : (
                  <Results />
                )}
              </div>
            </ViewerContext.Provider>
          )}
        </main>
      </div>
    </div>
  )
}
