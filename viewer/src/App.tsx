import { useEffect, useState } from 'react'
import { MicrogridView } from './components/MicrogridView'
import { Sidebar } from './components/Sidebar'
import {
  fetchExperiments,
  loadExperiment,
  type ExperimentsResponse,
  type LoadedExperiment,
} from './data/fileLoader'
import { useTheme } from './ThemeContext'

export default function App() {
  const [experimentsResp, setExperimentsResp] = useState<ExperimentsResponse | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [experiment, setExperiment] = useState<LoadedExperiment | null>(null)
  const [selectedMicrogrid, setSelectedMicrogrid] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { isDark, toggle } = useTheme()

  const microgrids = experiment ? Object.keys(experiment.timeseriesByMicrogrid) : []
  const activeMicrogrid =
    selectedMicrogrid && microgrids.includes(selectedMicrogrid)
      ? selectedMicrogrid
      : microgrids[0] ?? null

  const isMulti = experimentsResp?.mode === 'multi'
  const showSidebar = isMulti && sidebarOpen

  // On mount: discover experiments and auto-load the first one
  useEffect(() => {
    async function init() {
      try {
        const resp = await fetchExperiments()
        setExperimentsResp(resp)
        const first = resp.experiments[0]
        if (first) {
          const exp = await loadExperiment(first.name)
          setExperiment(exp)
          setSelectedName(first.name)
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  async function handleSelectExperiment(name: string) {
    if (name === selectedName) return
    setLoading(true)
    setError(null)
    setSelectedMicrogrid(null)
    try {
      const exp = await loadExperiment(name)
      setExperiment(exp)
      setSelectedName(name)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleReload() {
    if (selectedName === null) return
    setLoading(true)
    setError(null)
    try {
      const exp = await loadExperiment(selectedName)
      setExperiment(exp)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const status = experiment?.metadata.execution?.status

  return (
    <div
      className="h-screen flex flex-col bg-gray-50 dark:bg-[#0d0f14] text-gray-900 dark:text-gray-100"
      style={{ fontFamily: 'system-ui, sans-serif' }}
    >
      {/* Header */}
      <header className="shrink-0 bg-white dark:bg-[#13161e] border-b border-gray-200 dark:border-gray-800 shadow-xs z-10">
        <div className="px-4 h-14 flex items-center gap-3">
          {/* Sidebar toggle */}
          {isMulti && (
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="w-7 h-7 flex items-center justify-center rounded text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}

          {/* Logo */}
          <div className="flex items-center gap-2 mr-2">
            <svg className="w-5 h-5" xmlns="http://www.w3.org/2000/svg" version="1.0" viewBox="0 0 250 280">
              <path fill="#009485" d="M 67.907 7.609 C 67.907 7.609 26.81 59.969 13.01 79.669 C 8.21 86.569 7.81 90.269 11.21 95.369 C 15.01 101.069 18.881 100.435 54.501 100.39 C 88.213 100.347 83.722 100.304 98.333 100.25 C 112.077 100.199 94.51 112.369 70.41 141.769 C 52.91 163.069 47.896 168.713 46.496 171.313 C 44.596 174.713 43.973 182.519 45.937 186.043 C 50.603 194.415 59.983 192.853 73.133 192.83 C 89.633 192.801 85.212 192.944 97.612 193.034 C 112.14 193.139 106.914 195.519 70.101 253.218 C 61.391 266.87 73.128 275.965 88.71 271.569 C 100.847 268.145 232.912 117.588 241.51 103.069 C 243.78 99.235 241.242 94.511 237.311 93.537 C 231.123 92.004 215.716 92.551 202.377 92.468 C 181.775 92.339 178.43 100.634 169.685 100.456 C 167.315 100.524 165.217 98.159 170.808 90.355 C 177.497 81.018 201.432 49.486 222.773 22.994 C 226.832 17.956 221.053 7.71 213.803 7.796" />
            </svg>
            <span className="text-base font-semibold text-gray-800 dark:text-gray-100 tracking-tight">
              Vessim
            </span>
          </div>

          {/* Microgrid tabs */}
          {microgrids.length === 1 && (
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{microgrids[0]}</span>
          )}
          {microgrids.length > 1 && (
            <div className="flex gap-1">
              {microgrids.map((mg) => (
                <button
                  key={mg}
                  onClick={() => setSelectedMicrogrid(mg)}
                  className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                    activeMicrogrid === mg
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

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        {showSidebar && experimentsResp && (
          <Sidebar
            experiments={experimentsResp.experiments}
            selected={selectedName}
            onSelect={handleSelectExperiment}
          />
        )}

        {/* Main content */}
        <main className="flex-1 overflow-y-auto px-6 py-6">
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

          {!loading && !error && activeMicrogrid && experiment && (
            <MicrogridView
              key={activeMicrogrid}
              allHistory={experiment.timeseriesByMicrogrid}
              history={experiment.timeseriesByMicrogrid[activeMicrogrid]}
              config={experiment.configByMicrogrid[activeMicrogrid]}
              metadata={experiment.metadata}
            />
          )}
        </main>
      </div>
    </div>
  )
}
