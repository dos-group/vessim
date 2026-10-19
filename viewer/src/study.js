import { useEffect, useRef, useState } from 'react'
import { completedStudy } from './model.js'

export async function json(url, signal) {
  const response = await fetch(url, { signal })
  if (!response.ok) throw new Error(`Data unavailable (${response.status})`)
  return response.json()
}
async function load(entry) {
  const base = location.href
  const raw = await json(new URL(entry.url, base))
  for (const config of raw.configurations)
    for (const run of config.runs)
      if (run.trajectoryUrl)
        run.trajectoryUrl = new URL(run.trajectoryUrl, base).href
  return completedStudy(raw)
}
export function useStudy(catalog, id) {
  const cache = useRef(new Map())
  const [result, setResult] = useState({})
  useEffect(() => {
    if (!catalog || !id) return
    let cancelled = false
    if (!cache.current.has(id)) {
      const entry = catalog.studies.find((entry) => entry.study_id === id)
      const pending = entry
        ? load(entry)
        : Promise.reject(new Error(`Study unavailable: ${id}`))
      cache.current.set(id, pending)
    }
    cache.current.get(id).then(
      (study) => {
        if (!cancelled) setResult({ id, study })
      },
      (error) => {
        cache.current.delete(id)
        if (!cancelled) setResult({ id, error: error.message })
      },
    )
    return () => {
      cancelled = true
    }
  }, [catalog, id])
  return result.id === id ? result : {}
}
