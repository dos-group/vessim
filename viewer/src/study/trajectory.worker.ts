import { parseTrajectory } from './trajectory'
self.onmessage = async (event: MessageEvent<{ url: string }>) => {
  try {
    const response = await fetch(event.data.url)
    if (!response.ok)
      throw new Error(
        'The recorded trajectory could not be loaded. The summary remains available.',
      )
    self.postMessage({
      data: parseTrajectory(await response.text()),
    })
  } catch (error) {
    self.postMessage({
      error: error instanceof Error ? error.message : String(error),
    })
  }
}
