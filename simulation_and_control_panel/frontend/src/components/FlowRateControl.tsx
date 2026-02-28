import { useEffect, useRef, useState } from 'react'
import { getRoutes, setGlobalFlowRate } from '../services/api'

interface FlowRateControlProps {
  /** Whether the simulation is currently running (TraCI connected). */
  isRunning: boolean
}

const MIN_RATE = 0
const MAX_RATE = 1000
const STEP = 10

export function FlowRateControl({ isRunning }: FlowRateControlProps) {
  const [routeCount, setRouteCount] = useState<number>(0)
  const [rate, setRate] = useState<number>(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [lastApplied, setLastApplied] = useState<number | null>(null)

  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Fetch route count when simulation starts so we can show the badge
  useEffect(() => {
    if (!isRunning) {
      setRouteCount(0)
      setRate(0)
      setLoadError(null)
      setLastApplied(null)
      return
    }

    let cancelled = false

    const fetchRoutes = async () => {
      try {
        setLoadError(null)
        const response = await getRoutes()
        if (!cancelled) setRouteCount(response.data.routes?.length ?? 0)
      } catch (err) {
        if (!cancelled)
          setLoadError(`Failed to load routes: ${err instanceof Error ? err.message : 'Unknown error'}`)
      }
    }

    fetchRoutes()
    return () => { cancelled = true }
  }, [isRunning])

  const handleSliderChange = (value: number) => {
    setRate(value)
    setSaveError(null)

    // Debounce — send request ~300 ms after user stops dragging
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(async () => {
      setSaving(true)
      try {
        const response = await setGlobalFlowRate(value)
        setLastApplied(value)
        // Backend may have updated the route count (e.g. new routes loaded)
        if (response.data.route_count !== undefined)
          setRouteCount(response.data.route_count)
      } catch (err) {
        setSaveError(`Failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
      } finally {
        setSaving(false)
      }
    }, 300)
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (debounceTimer.current) clearTimeout(debounceTimer.current) }
  }, [])

  return (
    <div className="bg-white rounded-lg shadow p-6 mb-6">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-xl font-semibold text-gray-800">Network Flow Rate</h2>
        {isRunning && routeCount > 0 && (
          <span className="text-xs bg-blue-100 text-blue-700 font-medium px-2 py-1 rounded-full">
            {routeCount} route{routeCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-5">
        Set vehicle insertion rate for the entire network (vehicles&nbsp;/&nbsp;hour).
        The same rate is applied uniformly to all routes via TraCI.
      </p>

      {!isRunning && (
        <div className="text-sm text-gray-400 italic">Start the simulation to control flow rates.</div>
      )}

      {isRunning && loadError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {loadError}
        </div>
      )}

      {isRunning && (
        <div>
          {/* Rate display */}
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Insertion rate</span>
            <div className="flex items-center gap-2">
              {saving && <span className="text-xs text-blue-500 animate-pulse">Applying…</span>}
              {!saving && lastApplied !== null && (
                <span className="text-xs text-green-600">&#10003; Applied</span>
              )}
              <span className="text-2xl font-bold text-gray-900 w-28 text-right tabular-nums">
                {rate}&nbsp;<span className="text-sm font-normal text-gray-500">veh/h</span>
              </span>
            </div>
          </div>

          {/* Slider */}
          <input
            id="global-flow-slider"
            type="range"
            min={MIN_RATE}
            max={MAX_RATE}
            step={STEP}
            value={rate}
            disabled={!isRunning}
            onChange={(e) => handleSliderChange(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0 (off)</span>
            <span>250</span>
            <span>500</span>
            <span>750</span>
            <span>1000</span>
          </div>

          {saveError && <p className="text-xs text-red-600 mt-2">{saveError}</p>}

          {/* Quick-set presets */}
          <div className="flex gap-2 mt-4 flex-wrap">
            {[0, 100, 250, 500, 750, 1000].map((preset) => (
              <button
                key={preset}
                onClick={() => handleSliderChange(preset)}
                disabled={!isRunning}
                className={`text-xs px-3 py-1 rounded border transition font-medium
                  ${rate === preset
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400 hover:text-blue-600'}
                  disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {preset === 0 ? 'Off' : `${preset}`}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
