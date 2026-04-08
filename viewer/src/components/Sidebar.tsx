import { useTheme } from '../ThemeContext'
import type { ExperimentEntry } from '../data/fileLoader'

interface SidebarProps {
  experiments: ExperimentEntry[]
  selected: string | null
  onSelect: (name: string) => void
}

export function Sidebar({ experiments, selected, onSelect }: SidebarProps) {
  const { isDark, toggle } = useTheme()

  return (
    <aside className="w-52 shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#13161e] flex flex-col overflow-hidden">

      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 h-10 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <svg className="w-5 h-5 shrink-0" xmlns="http://www.w3.org/2000/svg" version="1.0" viewBox="0 0 250 280">
          <path fill="#009485" d="M 67.907 7.609 C 67.907 7.609 26.81 59.969 13.01 79.669 C 8.21 86.569 7.81 90.269 11.21 95.369 C 15.01 101.069 18.881 100.435 54.501 100.39 C 88.213 100.347 83.722 100.304 98.333 100.25 C 112.077 100.199 94.51 112.369 70.41 141.769 C 52.91 163.069 47.896 168.713 46.496 171.313 C 44.596 174.713 43.973 182.519 45.937 186.043 C 50.603 194.415 59.983 192.853 73.133 192.83 C 89.633 192.801 85.212 192.944 97.612 193.034 C 112.14 193.139 106.914 195.519 70.101 253.218 C 61.391 266.87 73.128 275.965 88.71 271.569 C 100.847 268.145 232.912 117.588 241.51 103.069 C 243.78 99.235 241.242 94.511 237.311 93.537 C 231.123 92.004 215.716 92.551 202.377 92.468 C 181.775 92.339 178.43 100.634 169.685 100.456 C 167.315 100.524 165.217 98.159 170.808 90.355 C 177.497 81.018 201.432 49.486 222.773 22.994 C 226.832 17.956 221.053 7.71 213.803 7.796" />
        </svg>
        <span className="text-sm font-semibold tracking-tight">Vessim</span>
        <a
          href="https://vessim.readthedocs.io/"
          target="_blank"
          rel="noreferrer"
          className="ml-auto text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
          title="Documentation"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
          </svg>
        </a>
      </div>

      {/* Experiments section label */}
      <div className="px-3 pt-3 pb-1 shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
          Experiments
        </span>
      </div>

      {/* Experiment list */}
      <nav className="flex-1 overflow-y-auto py-1">
        {experiments.map((exp) => {
          const isSelected = exp.name === selected
          const label = exp.name || 'experiment'
          return (
            <button
              key={exp.name}
              onClick={() => onSelect(exp.name)}
              className={`w-full flex items-center gap-2.5 px-3 py-1.5 text-left transition-colors ${
                isSelected
                  ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                exp.status === 'running' ? 'bg-emerald-400 animate-pulse'
                : exp.status === 'completed' ? 'bg-gray-300 dark:bg-gray-600'
                : 'bg-gray-200 dark:bg-gray-700'
              }`} />
              <span className="truncate text-xs font-mono">{label}</span>
            </button>
          )
        })}
      </nav>

      {/* Theme toggle */}
      <div className="shrink-0 border-t border-gray-200 dark:border-gray-800 px-3 py-3 flex items-center">
        <button
          onClick={toggle}
          className="w-7 h-7 flex items-center justify-center rounded text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
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

    </aside>
  )
}
