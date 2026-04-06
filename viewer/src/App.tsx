import { useEffect, useRef, useState } from 'react'
import { MicrogridView } from './components/MicrogridView'
import { loadFromFiles, loadFromServer, type LoadedExperiment } from './data/fileLoader'
import { useTheme } from './ThemeContext'

export default function App() {
  const [experiment, setExperiment] = useState<LoadedExperiment | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [serverMode, setServerMode] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { isDark, toggle } = useTheme()

  const microgrids = experiment ? Object.keys(experiment.timeseriesByMicrogrid) : []
  const active = selected && microgrids.includes(selected) ? selected : microgrids[0] ?? null

  // Auto-load from server when served via `vessim view`
  useEffect(() => {
    let cancelled = false
    async function tryServerLoad() {
      setLoading(true)
      try {
        const exp = await loadFromServer()
        if (!cancelled) {
          setExperiment(exp)
          setServerMode(true)
        }
      } catch {
        // Not served via `vessim view` — show file picker instead
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    tryServerLoad()
    return () => { cancelled = true }
  }, [])

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setLoading(true)
    setError(null)
    try {
      const exp = await loadFromFiles(files)
      setExperiment(exp)
      setSelected(null)
      setServerMode(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleReload() {
    if (serverMode) {
      setLoading(true)
      setError(null)
      try {
        const exp = await loadFromServer()
        setExperiment(exp)
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
      return
    }
    if (!inputRef.current?.files) return
    await handleFiles(inputRef.current.files)
  }

  const status = experiment?.metadata.status

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0d0f14] text-gray-900 dark:text-gray-100" style={{ fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white dark:bg-[#13161e] border-b border-gray-200 dark:border-gray-800 shadow-xs">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2 mr-4">
            <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span className="text-base font-semibold text-gray-800 dark:text-gray-100 tracking-tight">Vessim</span>
          </div>

          {/* Microgrid selector */}
          {microgrids.length === 1 && (
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{microgrids[0]}</span>
          )}
          {microgrids.length > 1 && (
            <div className="flex gap-1">
              {microgrids.map((mg) => (
                <button
                  key={mg}
                  onClick={() => setSelected(mg)}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    active === mg
                      ? 'bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400'
                      : 'text-gray-500 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                  }`}
                >
                  {mg}
                </button>
              ))}
            </div>
          )}

          <div className="ml-auto flex items-center gap-3">
            {/* Status indicator */}
            {experiment && status === 'running' && (
              <>
                <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Running
                </div>
                <button
                  onClick={handleReload}
                  className="text-xs text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                  Reload
                </button>
              </>
            )}
            {experiment && status === 'completed' && (
              <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                <span className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600" />
                Completed
              </div>
            )}
            {experiment && !status && (
              <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                <span className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600" />
                Loaded
              </div>
            )}

            {/* Load button */}
            <label className="cursor-pointer px-3 py-1.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
              {experiment ? 'Load other' : 'Load experiment'}
              <input
                ref={inputRef}
                type="file"
                // @ts-expect-error webkitdirectory is non-standard but widely supported
                webkitdirectory=""
                className="hidden"
                onChange={(e) => handleFiles(e.target.files)}
              />
            </label>

            {/* Theme toggle */}
            <button
              onClick={toggle}
              className="w-8 h-8 flex items-center justify-center rounded text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 100 10 5 5 0 000-10z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {loading && (
          <div className="flex items-center justify-center py-32 text-gray-300 dark:text-gray-700 text-sm animate-pulse">
            Loading experiment...
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center py-32 gap-3 text-gray-400 dark:text-gray-600">
            <svg className="w-12 h-12 text-gray-200 dark:text-gray-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M12 9v3m0 3h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && active && experiment && (
          <MicrogridView
            key={active}
            history={experiment.timeseriesByMicrogrid[active]}
            config={experiment.configByMicrogrid[active]}
          />
        )}

        {!loading && !error && !experiment && (
          <div className="flex flex-col items-center justify-center py-40 gap-4 text-gray-400 dark:text-gray-600">
            <svg className="w-14 h-14 text-gray-200 dark:text-gray-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <p className="text-sm">Load a Vessim experiment results directory to view data.</p>
            <label className="cursor-pointer px-4 py-2 rounded text-sm font-medium bg-blue-500 text-white hover:bg-blue-600 transition-colors">
              Select directory
              <input
                type="file"
                // @ts-expect-error webkitdirectory is non-standard but widely supported
                webkitdirectory=""
                className="hidden"
                onChange={(e) => handleFiles(e.target.files)}
              />
            </label>
          </div>
        )}
      </main>
    </div>
  )
}