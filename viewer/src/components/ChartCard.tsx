import type { ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  children: ReactNode
  fullWidth?: boolean
}

export function ChartCard({ title, subtitle, children, fullWidth = false }: Props) {
  return (
    <div
      className={`bg-white dark:bg-[#13161e] border border-gray-200 dark:border-gray-800 rounded p-5 shadow-xs flex flex-col gap-3 ${fullWidth ? 'col-span-1 md:col-span-2' : ''}`}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-600">
          {title}
        </span>
        {subtitle && (
          <span className="text-[10px] text-gray-300 dark:text-gray-700 font-normal truncate">
            {subtitle}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}
