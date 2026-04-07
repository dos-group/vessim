import type { ExperimentEntry } from '../data/fileLoader'

interface SidebarProps {
  experiments: ExperimentEntry[]
  selected: string | null
  onSelect: (name: string) => void
}

export function Sidebar({ experiments, selected, onSelect }: SidebarProps) {
  return (
    <aside className="w-52 shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-[#13161e] flex flex-col overflow-hidden">
      <div className="px-3 py-2.5 border-b border-gray-100 dark:border-gray-800">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
          Experiments
        </span>
      </div>
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
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-gray-200'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  exp.status === 'running'
                    ? 'bg-emerald-400 animate-pulse'
                    : exp.status === 'completed'
                      ? 'bg-gray-300 dark:bg-gray-600'
                      : 'bg-gray-200 dark:bg-gray-700'
                }`}
              />
              <span className="truncate text-xs font-mono">{label}</span>
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
