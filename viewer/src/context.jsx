import { createContext, useContext } from 'react'
export const ViewerContext = createContext(null)
export function useViewer() {
  return useContext(ViewerContext)
}
