import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import { ViewerContext } from './context.jsx'
import { completedStudy } from './model.js'
import { initState } from './state.js'
import { presentation } from './presentation.js'
import { RecordingStore } from './recordings.js'
import { Results } from './components/Results.jsx'
import { TimeSeries } from './components/TimeSeries.jsx'
import { RunDetails } from './components/RunDetails.jsx'
import { Issues, Select } from './components/controls.jsx'
import logo from './logo.svg'
import { readViewLink } from './view-link.js'
import { ShareLink } from './components/ShareLink.jsx'

function subscribeLocation(listener) {
  for (const event of ['hashchange', 'popstate', 'viewer:navigate'])
    window.addEventListener(event, listener)
  return () => {
    for (const event of ['hashchange', 'popstate', 'viewer:navigate'])
      window.removeEventListener(event, listener)
  }
}
function navigate(page, studyId) {
  const url = new URL(location.href)
  if (studyId) {
    url.search = ''
    url.searchParams.set('study', studyId)
  }
  url.hash = page
  if (url.href === location.href) return
  history.pushState(null, '', url)
  window.dispatchEvent(new Event('viewer:navigate'))
}
async function json(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Data unavailable (${response.status})`)
  return response.json()
}
export default function App() {
  const href = useSyncExternalStore(subscribeLocation, () => location.href),
    url = new URL(href)
  const [catalog, setCatalog] = useState(null),
    [error, setError] = useState(null),
    [studies, setStudies] = useState({}),
    [states, setStates] = useState({})
  const [recordings] = useState(() => new RecordingStore())
  const cache = useRef(new Map())
  const active =
    url.searchParams.get('study') || catalog?.studies[0]?.study_id || ''
  const page = url.hash.slice(1) || 'results',
    study = studies[active],
    view = states[active]
  useEffect(() => {
    const abort = new AbortController()
    json(new URL('catalog.json', location.href), abort.signal)
      .then((value) => {
        if (!Array.isArray(value.studies))
          throw new Error('Invalid viewer catalog')
        setCatalog(value)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError({ id: null, message: e.message })
      })
    return () => abort.abort()
  }, [])
  useEffect(() => () => recordings.dispose(), [recordings])
  useEffect(() => {
    if (!catalog || !active || study) return
    let cancelled = false
    const entry = catalog.studies.find((entry) => entry.study_id === active)
    const promise =
      cache.current.get(active) ||
      (entry
        ? json(new URL(entry.url, location.href)).then((raw) => {
            for (const config of raw.configurations)
              for (const run of config.runs)
                if (run.trajectoryUrl)
                  run.trajectoryUrl = new URL(
                    run.trajectoryUrl,
                    location.href,
                  ).href
            return completedStudy(raw)
          })
        : Promise.reject(new Error(`Study unavailable: ${active}`)))
    cache.current.set(active, promise)
    promise
      .then((result) => {
        if (cancelled) return
        setError(null)
        setStudies((previous) => ({ ...previous, [active]: result }))
        setStates((previous) =>
          previous[active]
            ? previous
            : {
                ...previous,
                [active]: readViewLink(
                  new URL(location.href).searchParams.get('view'),
                  initState(result),
                  result,
                ),
              },
        )
      })
      .catch((e) => {
        cache.current.delete(active)
        if (!cancelled) setError({ id: active, message: e.message })
      })
    return () => {
      cancelled = true
    }
  }, [catalog, active, study])
  const shared = url.searchParams.get('view')
  const appliedLink = useRef('')
  useEffect(() => {
    if (!study) return
    const key = `${active}/${shared}`
    if (appliedLink.current === key) return
    appliedLink.current = key
    if (shared)
      setStates((previous) => ({
        ...previous,
        [active]: readViewLink(shared, initState(study), study),
      }))
  }, [active, shared, study])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [active, page])
  const patch = useCallback(
    (change) =>
      setStates((previous) => {
        const current = previous[active]
        return current
          ? {
              ...previous,
              [active]: {
                ...current,
                ...(typeof change === 'function' ? change(current) : change),
              },
            }
          : previous
      }),
    [active],
  )
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
  const visibleError =
    error && (!error.id || error.id === active) ? error.message : ''
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
        <a className="brand" href="#results">
          <img src={logo} alt="" />
          Vessim
        </a>
        <Select
          id="study"
          label="Study"
          value={active}
          onChange={(id) => {
            setError(null)
            navigate('results', id)
          }}
          disabled={!catalog?.studies.length}
          options={
            catalog?.studies.map((entry) => ({
              value: entry.study_id,
              label: entry.name,
            })) || [{ value: '', label: 'Loading studies…' }]
          }
        />
        <nav aria-label="Study">
          <a
            id="results-nav"
            href="#results"
            className={page !== 'timeseries' ? 'active' : ''}
          >
            Results
          </a>
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
        {context && (
          <ShareLink
            key={`${active}/${page}`}
            study={study}
            view={view}
            page={page}
          />
        )}
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
