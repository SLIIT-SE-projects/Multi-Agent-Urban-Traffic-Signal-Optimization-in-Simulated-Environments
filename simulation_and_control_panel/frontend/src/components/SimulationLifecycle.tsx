import { useState } from 'react'
import { startSimulation, pauseSimulation, resumeSimulation, stopSimulation } from '../services/api'

interface SimulationLifecycleProps {
  onRefresh?: () => void
  isRunning?: boolean
  isPaused?: boolean
  isStopping?: boolean
  suppressDemand?: boolean
  onSuppressDemandChange?: (value: boolean) => void
}

export function SimulationLifecycle({
  onRefresh,
  isRunning = false,
  isPaused = false,
  isStopping = false,
  suppressDemand = true,
  onSuppressDemandChange,
}: SimulationLifecycleProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAction = async (action: () => Promise<any>, actionName: string) => {
    try {
      setLoading(true)
      setError(null)
      await action()
      onRefresh?.()
    } catch (err) {
      setError(`${actionName} failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <h3 className="text-lg font-semibold text-gray-800 mb-4">Simulation Lifecycle</h3>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {/* Demand mode toggle — only meaningful before starting */}
      <div className="mb-4">
        <label className={`flex items-start gap-3 cursor-pointer select-none ${isRunning || isStopping ? 'opacity-50 cursor-not-allowed' : ''}`}>
          <input
            type="checkbox"
            checked={suppressDemand}
            disabled={isRunning || isStopping}
            onChange={(e) => onSuppressDemandChange?.(e.target.checked)}
            className="mt-0.5 w-4 h-4 accent-blue-600 cursor-pointer"
          />
          <div>
            <span className="text-sm font-medium text-gray-800">
              Flow-rate control only (suppress built-in demand)
            </span>
            <p className="text-xs text-gray-500 mt-0.5">
              {suppressDemand
                ? 'SUMO will start with no pre-loaded vehicles. Use the Network Flow Rate slider to inject traffic.'
                : 'Scenario vehicles will run as normal alongside any injected vehicles.'}
            </p>
          </div>
        </label>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button
          onClick={() => handleAction(() => startSimulation({ suppressDemand }), 'Start')}
          disabled={loading || isRunning || isStopping}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded transition"
        >
          {isStopping ? 'Closing...' : 'Start'}
        </button>

        <button
          onClick={() => handleAction(pauseSimulation, 'Pause')}
          disabled={loading || !isRunning || isPaused}
          className="bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded transition"
        >
          Pause
        </button>

        <button
          onClick={() => handleAction(resumeSimulation, 'Resume')}
          disabled={loading || !isRunning || !isPaused}
          className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded transition"
        >
          Resume
        </button>

        <button
          onClick={() => handleAction(stopSimulation, 'Stop')}
          disabled={loading || !isRunning}
          className="bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded transition"
        >
          Stop
        </button>
      </div>
    </div>
  )
}
