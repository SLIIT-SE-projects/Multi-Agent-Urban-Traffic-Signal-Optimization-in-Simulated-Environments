import { useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LaneData {
  queue_length: number
  vehicle_count: number
  occupancy: number
  /** Raw SUMO value — equals the speed *limit* when no vehicles are present. */
  avg_speed: number
  co2: number
  waiting_time: number
}

interface SimulationStepEvent {
  step: number
  lanes: Record<string, LaneData>
  global: {
    arrived_vehicles: number
  }
}

interface DataPoint {
  step: number
  avgSpeed: number      // m/s averaged across all lanes
  totalQueue: number    // vehicles, summed across all lanes
  arrivedVehicles: number
}

// ── Constants ─────────────────────────────────────────────────────────────────

// Connect through the Vite dev-server proxy (/socket.io → localhost:5000).
// In production, point this at the backend origin instead.
const BACKEND_URL = ''
const BUFFER_SIZE = 60

// ── Helpers ───────────────────────────────────────────────────────────────────

function deriveMetrics(event: SimulationStepEvent): DataPoint {
  const laneValues = Object.values(event.lanes)

  const totalQueue = laneValues.reduce((sum, l) => sum + (l.queue_length ?? 0), 0)

  // Only include lanes that actually have vehicles — SUMO returns the free-flow
  // speed limit (not 0) for empty lanes, which would produce a misleadingly
  // high average when no traffic is present.
  // Use vehicle_count when available (requires backend restart); fall back to
  // occupancy > 0 which was always present in the snapshot.
  const occupiedLanes = laneValues.filter(
    (l) => (l.vehicle_count ?? 0) > 0 || (l.occupancy ?? 0) > 0,
  )
  const speedSum = occupiedLanes.reduce((sum, l) => sum + l.avg_speed, 0)
  const avgSpeed = occupiedLanes.length > 0 ? speedSum / occupiedLanes.length : 0

  return {
    step: event.step,
    avgSpeed: parseFloat(avgSpeed.toFixed(3)),
    totalQueue,
    arrivedVehicles: event.global?.arrived_vehicles ?? 0,
  }
}

function pushToBuffer(prev: DataPoint[], next: DataPoint): DataPoint[] {
  const updated = [...prev, next]
  return updated.length > BUFFER_SIZE ? updated.slice(updated.length - BUFFER_SIZE) : updated
}

// ── Shared chart helpers ───────────────────────────────────────────────────────

const CHART_MARGIN = { top: 8, right: 20, left: 0, bottom: 0 }

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-base font-semibold text-gray-800">{title}</h3>
      <p className="text-xs text-gray-500 mb-3">{subtitle}</p>
      {children}
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

interface PerformanceDashboardProps {
  isRunning: boolean
}

export function PerformanceDashboard({ isRunning }: PerformanceDashboardProps) {
  const [buffer, setBuffer] = useState<DataPoint[]>([])
  const [connected, setConnected] = useState(false)
  const socketRef = useRef<Socket | null>(null)

  // Manage Socket.IO lifecycle
  useEffect(() => {
    const socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
    })
    socketRef.current = socket

    socket.on('connect', () => setConnected(true))
    socket.on('disconnect', () => setConnected(false))

    socket.on('simulation_step', (event: SimulationStepEvent) => {
      setBuffer((prev) => pushToBuffer(prev, deriveMetrics(event)))
    })

    return () => {
      socket.disconnect()
    }
  }, [])

  // Clear buffer when simulation stops
  useEffect(() => {
    if (!isRunning) setBuffer([])
  }, [isRunning])

  const hasData = buffer.length > 0

  return (
    <div className="bg-gray-50 rounded-lg shadow p-6 mb-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Performance Dashboard</h2>
          <p className="text-sm text-gray-500">
            Live metrics from the last {BUFFER_SIZE} simulation steps
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div
            className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-400'} animate-pulse`}
          />
          <span className="text-gray-500">{connected ? 'Socket connected' : 'Socket disconnected'}</span>
          {hasData && (
            <span className="ml-3 bg-blue-100 text-blue-700 font-medium px-2 py-0.5 rounded-full">
              {buffer.length} pts
            </span>
          )}
        </div>
      </div>

      {!isRunning && !hasData && (
        <div className="text-sm text-gray-400 italic text-center py-8">
          Start the simulation to see live performance charts.
        </div>
      )}

      {(isRunning || hasData) && (
        <div className="grid grid-cols-1 gap-5">

          {/* ── Chart 1: Average Speed ── */}
          <ChartCard
            title="Average Network Speed"
            subtitle="Mean vehicle speed across all lanes (m/s)"
          >
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={buffer} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="step"
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Step', position: 'insideBottomRight', offset: -4, fontSize: 11 }}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{ value: 'm/s', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
                  domain={[0, 'auto']}
                />
                <Tooltip
                  formatter={(v: number) => [`${v.toFixed(2)} m/s`, 'Avg Speed']}
                  labelFormatter={(l) => `Step ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="avgSpeed"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* ── Chart 2: Total Queue Length ── */}
          <ChartCard
            title="Total Queue Length"
            subtitle="Halted vehicles summed across all lanes"
          >
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={buffer} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="step"
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Step', position: 'insideBottomRight', offset: -4, fontSize: 11 }}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{ value: 'vehicles', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
                  domain={[0, 'auto']}
                />
                <Tooltip
                  formatter={(v: number) => [`${v} veh`, 'Queue']}
                  labelFormatter={(l) => `Step ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="totalQueue"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                <ReferenceLine y={0} stroke="#e5e7eb" />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* ── Chart 3: Arrived Vehicles ── */}
          <ChartCard
            title="Arrived Vehicles"
            subtitle="Cumulative vehicles that completed their trip this step"
          >
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={buffer} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="step"
                  tick={{ fontSize: 11 }}
                  label={{ value: 'Step', position: 'insideBottomRight', offset: -4, fontSize: 11 }}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{ value: 'vehicles', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }}
                  domain={[0, 'auto']}
                />
                <Tooltip
                  formatter={(v: number) => [`${v} veh`, 'Arrived']}
                  labelFormatter={(l) => `Step ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="arrivedVehicles"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

        </div>
      )}
    </div>
  )
}
