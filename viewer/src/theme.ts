import { createContext, useContext } from 'react'

interface ThemeCtx {
  isDark: boolean
  toggle: () => void
}

export const ThemeContext = createContext<ThemeCtx>({ isDark: false, toggle: () => {} })

export const useTheme = () => useContext(ThemeContext)
