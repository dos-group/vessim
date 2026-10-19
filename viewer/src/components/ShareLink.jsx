import { useState } from 'react'
import { initState } from '../state.js'
import { writeViewLink } from '../view-link.js'
export function ShareLink({ study, view, page }) {
  const [message, setMessage] = useState(''),
    [fallback, setFallback] = useState('')
  async function copy() {
    const link = writeViewLink(
      location.href,
      study.study_id,
      page,
      view,
      initState(study),
    )
    try {
      await navigator.clipboard.writeText(link)
      setMessage('Link copied')
      setFallback('')
    } catch {
      setFallback(link)
      setMessage('Select and copy the link below')
    }
  }
  return (
    <div className="share-link">
      <button onClick={copy}>Copy link</button>
      <span role="status">{message}</span>
      {fallback && (
        <input
          aria-label="Link to this view"
          value={fallback}
          readOnly
          onFocus={(e) => e.target.select()}
        />
      )}
    </div>
  )
}
