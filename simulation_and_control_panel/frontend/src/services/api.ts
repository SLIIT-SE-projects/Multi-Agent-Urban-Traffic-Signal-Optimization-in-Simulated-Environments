import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 5000,
})

// Health Check
export const healthCheck = () => apiClient.get('/health')

// Simulation Control
export const startSimulation = (options?: { suppressDemand?: boolean }) =>
  apiClient.post('/simulation/start', { suppress_demand: options?.suppressDemand ?? false })
export const stepSimulation = () => apiClient.post('/simulation/step')
export const pauseSimulation = () => apiClient.post('/simulation/pause')
export const resumeSimulation = () => apiClient.post('/simulation/resume')
export const stopSimulation = () => apiClient.post('/simulation/stop')

// Auto-Stepping
export const startAutoStep = (stepDelay?: number) =>
  apiClient.post('/simulation/auto-step/start', { step_delay: stepDelay })
export const pauseAutoStep = () => apiClient.post('/simulation/auto-step/pause')
export const resumeAutoStep = () => apiClient.post('/simulation/auto-step/resume')
export const stopAutoStep = () => apiClient.post('/simulation/auto-step/stop')

// Status
export const getStatus = () => apiClient.get('/simulation/status')

// Scenarios
export const getScenarios = () => apiClient.get('/scenarios')
export const getCurrentScenario = () => apiClient.get('/simulation/current-scenario')
export const switchScenario = (scenarioName: string) =>
  apiClient.post('/simulation/switch-scenario', { scenario_name: scenarioName })
export const reloadScenario = () => apiClient.post('/simulation/reload')

// Flow Rate Control
export const getRoutes = () => apiClient.get<{ status: string; routes: string[] }>('/simulation/routes')
export const setFlowRate = (routeId: string, vehiclesPerHour: number) =>
  apiClient.post('/simulation/flow-rate', {
    route_id: routeId,
    vehicles_per_hour: vehiclesPerHour,
  })
export const setGlobalFlowRate = (vehiclesPerHour: number) =>
  apiClient.post<{ status: string; message: string; vehicles_per_hour: number; route_count: number }>(
    '/simulation/flow-rate/global',
    { vehicles_per_hour: vehiclesPerHour },
  )

export default apiClient
