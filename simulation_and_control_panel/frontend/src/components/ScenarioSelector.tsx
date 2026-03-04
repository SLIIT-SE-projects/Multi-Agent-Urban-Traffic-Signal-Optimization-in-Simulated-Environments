import { useEffect, useState } from 'react'
import { getScenarios, getCurrentScenario, switchScenario } from '../services/api'

interface Scenario {
  name: string
  config_file: string
  path: string
}

interface ScenarioSelectorProps {
  onSwitch?: () => void
  isRunning?: boolean
}

export function ScenarioSelector({ onSwitch, isRunning = false }: ScenarioSelectorProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [currentScenario, setCurrentScenario] = useState<string | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [switchError, setSwitchError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  useEffect(() => {
    fetchScenarios()
  }, [])

  const fetchScenarios = async () => {
    try {
      setFetchError(null)
      const [scenariosRes, currentRes] = await Promise.all([
        getScenarios(),
        getCurrentScenario(),
      ])
      const list: Scenario[] = scenariosRes.data.scenarios ?? []
      setScenarios(list)

      const current: string | null = currentRes.data.scenario_name ?? null
      setCurrentScenario(current)
      // Pre-select current scenario in dropdown
      setSelected(current ?? (list[0]?.name ?? ''))
    } catch (err) {
      setFetchError('Failed to load scenarios')
    }
  }

  const handleSwitch = async () => {
    if (!selected) return
    try {
      setLoading(true)
      setSwitchError(null)
      setSuccessMsg(null)
      const res = await switchScenario(selected)
      const msg = res.data.restarted
        ? `Switched to "${selected}" and restarted simulation.`
        : `Scenario set to "${selected}". Press Start to begin.`
      setSuccessMsg(msg)
      setCurrentScenario(selected)
      onSwitch?.()
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err) {
      setSwitchError(`Switch failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const isAlreadyActive = selected === currentScenario

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Scenario</h2>

      {fetchError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {fetchError}
          <button onClick={fetchScenarios} className="ml-3 underline text-red-800 hover:text-red-900">
            Retry
          </button>
        </div>
      )}

      {switchError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {switchError}
        </div>
      )}

      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4 text-sm">
          {successMsg}
        </div>
      )}

      {/* Currently loaded badge */}
      {currentScenario && (
        <div className="mb-3 flex items-center gap-2 text-sm text-gray-600">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500"></span>
          Currently loaded:
          <span className="font-semibold text-gray-800">{currentScenario}</span>
          {isRunning && (
            <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full font-medium">
              Running
            </span>
          )}
        </div>
      )}

      <div className="flex gap-3 items-center">
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value)
            setSwitchError(null)
            setSuccessMsg(null)
          }}
          className="flex-1 border border-gray-300 rounded px-3 py-2 text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {scenarios.length === 0 && (
            <option value="" disabled>
              No scenarios found
            </option>
          )}
          {scenarios.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>

        <button
          onClick={handleSwitch}
          disabled={loading || !selected || isAlreadyActive}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-2 px-5 rounded transition whitespace-nowrap"
        >
          {loading
            ? 'Switching…'
            : isAlreadyActive
            ? 'Active'
            : isRunning
            ? 'Switch & Restart'
            : 'Switch'}
        </button>
      </div>

      {isRunning && selected !== currentScenario && (
        <p className="mt-2 text-xs text-yellow-700">
          ⚠ Switching will stop the current simulation and restart with the selected scenario.
        </p>
      )}
    </div>
  )
}
