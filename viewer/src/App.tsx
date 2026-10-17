import { useEffect, useMemo, useState } from 'react'
import { useTheme } from './theme'
import { Explorer } from './study/Explorer'
import { Comparison } from './study/Comparison'
import { Inspector } from './study/Inspector'
import { indexCatalog } from './study/model'
import type { Catalog } from './study/model'

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [view, setView] = useState('explore')
  const [inspected, setInspected] = useState<string | null>(null)
  const { isDark, toggle: theme } = useTheme()
  useEffect(() => {
    const controller = new AbortController()
    const start = performance.now()
    fetch(new URL('catalog.json', document.baseURI), {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok)
          throw new Error(
            'Could not open this study. Start the viewer with vessim view <path>.',
          )
        return response.json()
      })
      .then((wire) => {
        const next = indexCatalog(wire)
        if (controller.signal.aborted) return
        setCatalog(next)
        const requested = new URLSearchParams(location.hash.slice(1)).get('run')
        const run = requested
          ? next.runs.find((r) => r.record.run_id === requested)
          : next.runs.length === 1
            ? next.runs[0]
            : undefined
        if (run) {
          setInspected(run.key)
          setView('inspect')
        }
        performance.measure('vessim-catalog-ready', {
          start,
          end: performance.now(),
        })
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : String(e))
      })
    return () => controller.abort()
  }, [])
  const selectedRuns = useMemo(
    () => catalog?.runs.filter((r) => selected.has(r.key)) ?? [],
    [catalog, selected],
  )
  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  const inspect = (key: string) => {
    setInspected(key)
    setView('inspect')
    const run = catalog?.runs.find((r) => r.key === key)
    if (run)
      history.replaceState(
        null,
        '',
        `#run=${encodeURIComponent(run.record.run_id)}`,
      )
    window.scrollTo({ top: 0 })
  }
  const navigate = (next: string) => {
    setView(next)
    history.replaceState(null, '', location.pathname + location.search)
    window.scrollTo({ top: 0 })
  }
  const activeRun = catalog?.runs.find((r) => r.key === inspected)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="app-sidebar">
        <button
          className="brand"
          onClick={() => navigate('explore')}
          aria-label="Vessim study explorer"
        >
          <span className="brand-mark">ϟ</span>
          <span>
            vessim<span className="brand-sub">EXPERIMENT WORKSPACE</span>
          </span>
        </button>
        <div className="nav-section">WORKSPACE</div>
        <nav aria-label="Workspace">
          <button
            className={view === 'explore' ? 'active' : ''}
            onClick={() => navigate('explore')}
          >
            <span className="nav-icon">▦</span>Explore
            <span className="nav-count">
              {catalog?.runs.length.toLocaleString() ?? '…'}
            </span>
          </button>
          <button
            className={view === 'compare' ? 'active' : ''}
            onClick={() => navigate('compare')}
          >
            <span className="nav-icon">⇄</span>Compare
            <span className="nav-count">{selected.size}</span>
          </button>
          {activeRun && (
            <button
              className={view === 'inspect' ? 'active' : ''}
              onClick={() => inspect(activeRun.key)}
            >
              <span className="nav-icon">≋</span>Run inspector
            </button>
          )}
        </nav>
        <div className="sidebar-note">
          <span className="note-symbol">↗</span>
          <h3>Every result has a story.</h3>
          <p>Move from the shape of a study to the details of a single run.</p>
        </div>
        <div className="sidebar-bottom">
          <a
            href="https://vessim.readthedocs.io/"
            target="_blank"
            rel="noreferrer"
          >
            Documentation ↗
          </a>
          <button onClick={theme} aria-label="Toggle color theme">
            {isDark ? '☀ Light appearance' : '◐ Dark appearance'}
          </button>
          <span className="local-badge">
            <i />
            Recorded experiment analysis
          </span>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <span className="slash">/</span>
            {view === 'explore'
              ? 'Study explorer'
              : view === 'compare'
                ? 'Compare runs'
                : 'Run inspector'}
          </div>
          <span className="topbar-right">
            Vessim <span className="pill">Studies</span>
          </span>
        </header>
        <main id="main" className="main-content">
          {error ? (
            <div className="empty error" role="alert">
              <h1>Could not open the workspace.</h1>
              <p>{error}</p>
              <button className="button" onClick={() => location.reload()}>
                Try again
              </button>
            </div>
          ) : !catalog ? (
            <div className="empty" role="status">
              <span className="loading-orbit" />
              <h2>Opening your study…</h2>
              <p>
                Loading recorded summaries. Trajectories stay on disk until
                needed.
              </p>
            </div>
          ) : (
            <>
              {catalog.errors.length > 0 && (
                <details className="notice error">
                  <summary>
                    {catalog.errors.length} records or artifacts need attention
                  </summary>
                  <ul>
                    {catalog.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </details>
              )}
              <div hidden={view !== 'explore'}>
                <Explorer
                  active={view === 'explore'}
                  catalog={catalog}
                  selected={selected}
                  toggle={toggle}
                  inspect={inspect}
                  compare={() => navigate('compare')}
                  selectMany={(keys) => setSelected(new Set(keys))}
                />
              </div>
              {view === 'compare' && (
                <Comparison
                  runs={selectedRuns}
                  columns={catalog.columns}
                  inspect={inspect}
                />
              )}
              {view === 'inspect' && activeRun && (
                <Inspector
                  key={activeRun.key}
                  run={activeRun}
                  columns={catalog.columns}
                  back={() => navigate('explore')}
                  selected={selected.has(activeRun.key)}
                  toggle={() => toggle(activeRun.key)}
                />
              )}
            </>
          )}
          <footer className="page-footer">
            <span>Vessim · Make sense of your energy experiments.</span>
            <span>Powered by recorded results</span>
          </footer>
        </main>
      </div>
    </div>
  )
}
