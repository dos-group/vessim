import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import { initState } from './state.js'
import { readViewLink, writeViewLink } from './view-link.js'

// Only navigation events change this snapshot. Replacing the current view's URL
// must not restore it again or discard UI state that is not part of the link.
let route = { url: new URL(location.href), restore: true }
function subscribe(listener) {
  const changed = (event) => {
    if (route.url.href === location.href) return
    route = {
      url: new URL(location.href),
      restore: event.type !== 'viewer:navigate',
    }
    listener()
  }
  const events = ['hashchange', 'popstate', 'viewer:navigate']
  events.forEach((event) => window.addEventListener(event, changed))
  return () =>
    events.forEach((event) => window.removeEventListener(event, changed))
}
export function useNavigation() {
  return useSyncExternalStore(subscribe, () => route)
}
export function navigate(page, studyId) {
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
export function useViewState(study, route) {
  const [views, setViews] = useState({})
  const defaults = useMemo(() => study && initState(study), [study])
  const applied = useRef(null)
  const id = study?.study_id,
    view = views[id]
  const patch = useCallback(
    (change) => {
      setViews((previous) =>
        previous[id]
          ? {
              ...previous,
              [id]: {
                ...previous[id],
                ...(typeof change === 'function'
                  ? change(previous[id])
                  : change),
              },
            }
          : previous,
      )
    },
    [id],
  )
  useEffect(() => {
    if (!study) return
    if (applied.current !== route) {
      applied.current = route
      if (route.restore || !view) {
        const shared = route.url.searchParams.get('view')
        setViews((previous) => ({
          ...previous,
          [id]: readViewLink(shared, defaults, study),
        }))
        return
      }
    }
    const href = writeViewLink(
      location.href,
      id,
      route.url.hash.slice(1) || 'results',
      view,
      defaults,
    )
    if (href !== location.href) history.replaceState(null, '', href)
  }, [study, route, id, view, defaults])
  return [view, patch]
}
