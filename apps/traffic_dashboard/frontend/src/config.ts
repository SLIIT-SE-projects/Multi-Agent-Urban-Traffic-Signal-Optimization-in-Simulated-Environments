
export const API_BASE_URL = import.meta.env.VITE_DASHBOARD_API_URL || 'http://localhost:8000/api';
export const DASHBOARD_API_URL = 'http://localhost:8000';
export const WS_BASE_URL = import.meta.env.VITE_DASHBOARD_WS_URL || 'ws://localhost:8000/ws';
export const EVPS_WS_URL = import.meta.env.VITE_EVPS_WS_URL || 'ws://localhost:5000/ws';

export const ENDPOINTS = {
  CONTROL: `${API_BASE_URL}/control`,
};