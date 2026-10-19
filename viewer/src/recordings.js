// Recordings are cached outside view state. Snapshots share trajectory arrays,
// so changing controls never copies recordings or restarts an active worker.
export class RecordingStore {
  entries = new Map()
  workers = new Set()
  listeners = new Set()
  subscribe = (listener) => {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }
  snapshot = () => this.entries
  get = (run) => this.entries.get(run.trajectoryUrl)
  ensure(run) {
    if (!run.trajectoryUrl || this.entries.has(run.trajectoryUrl)) return
    const worker = new Worker(
      new URL('./recording.worker.js', import.meta.url),
      { type: 'module' },
    )
    this.workers.add(worker)
    this.entries = new Map(this.entries).set(run.trajectoryUrl, {
      pending: true,
    })
    this.listeners.forEach((listener) => listener())
    const finish = (result) => {
      this.entries = new Map(this.entries).set(run.trajectoryUrl, result)
      worker.terminate()
      this.workers.delete(worker)
      this.listeners.forEach((listener) => listener())
    }
    worker.onmessage = (event) => finish(event.data)
    worker.onerror = () =>
      finish({ error: 'The recording could not be parsed.' })
    worker.postMessage({ url: run.trajectoryUrl })
  }
  dispose() {
    this.workers.forEach((worker) => worker.terminate())
    this.workers.clear()
    this.entries = new Map()
  }
}
