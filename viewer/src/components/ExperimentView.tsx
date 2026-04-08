import { useEffect, useState } from 'react'
import type { LoadedExperiment } from '../data/fileLoader'
import { MicrogridView } from './MicrogridView'
import { OverviewTab } from './OverviewTab'

interface Props {
  experiment: LoadedExperiment
  onReload?: () => void
}

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 h-10 text-xs font-medium border-b-2 transition-colors whitespace-nowrap ${
        active
          ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
          : 'border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-white'
      }`}
    >
      {label}
    </button>
  )
}

export function ExperimentView({ experiment, onReload }: Props) {
  const microgrids = Object.keys(experiment.timeseriesByMicrogrid).sort()
  const [activeTab, setActiveTab] = useState<string>('overview')
  const status = experiment.metadata.execution?.status

  // Reset to overview whenever a new experiment is loaded
  useEffect(() => { setActiveTab('overview') }, [experiment])

  const activeMg = activeTab !== 'overview' && microgrids.includes(activeTab) ? activeTab : null

  return (
    <div className="flex flex-col h-full">

      {/* Tab bar */}
      <div className="shrink-0 bg-white dark:bg-[#13161e] border-b border-gray-200 dark:border-gray-800 h-10 flex items-center px-2">
        <TabBtn label="Overview" active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} />
        {microgrids.length > 0 && (
          <div className="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1 self-center shrink-0" />
        )}
        {microgrids.map((mg) => (
          <TabBtn key={mg} label={mg} active={activeTab === mg} onClick={() => setActiveTab(mg)} />
        ))}

        {/* Status + reload */}
        <div className="ml-auto flex items-center gap-3 px-2">
          {status === 'running' && (
            <>
              <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Running
              </div>
              {onReload && (
                <button
                  onClick={onReload}
                  className="text-xs text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                  Reload
                </button>
              )}
            </>
          )}
          {status === 'completed' && (
            <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500">
              <span className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600" />
              Completed
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeMg ? (
          <div className="px-6 py-6">
            <MicrogridView
              key={activeMg}
              allHistory={experiment.timeseriesByMicrogrid}
              history={experiment.timeseriesByMicrogrid[activeMg]}
              config={experiment.configByMicrogrid[activeMg]}
              metadata={experiment.metadata}
            />
          </div>
        ) : (
          <OverviewTab experiment={experiment} onSelectMicrogrid={setActiveTab} />
        )}
      </div>

    </div>
  )
}
