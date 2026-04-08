import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ExperimentView } from './components/ExperimentView'
import {
  fetchExperiments,
  loadExperiment,
  type ExperimentsResponse,
  type LoadedExperiment,
} from './data/fileLoader'

export default function App() {
  const [experimentsResp, setExperimentsResp] = useState<ExperimentsResponse | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const [experiment, setExperiment] = useState<LoadedExperiment | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div
      className="h-screen flex bg-gray-50 dark:bg-[#0d0f14] text-gray-900 dark:text-gray-100"
      style={{ fontFamily: 'system-ui, sans-serif' }}
    >
      {/* Sidebar — always visible */}
      <Sidebar
        experiments={experimentsResp?.experiments ?? []}
        selected={selectedName}
        onSelect={handleSelectExperiment}
      />

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        {loading && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm animate-pulse">
            Loading experiment...
          </div>
        )}

        {error && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500">
            <svg className="w-12 h-12 text-gray-300 dark:text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M12 9v3m0 3h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && experiment && (
          <ExperimentView experiment={experiment} onReload={handleReload} />
        )}
      </div>
    </div>
  )
}
