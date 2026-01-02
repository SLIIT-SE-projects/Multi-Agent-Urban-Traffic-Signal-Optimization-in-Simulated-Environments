
export const API_BASE_URL = import.meta.env.VITE_DASHBOARD_API_URL || 'http://localhost:8000/api';
export const WS_BASE_URL = import.meta.env.VITE_DASHBOARD_WS_URL || 'ws://localhost:8000/ws';

export const ENDPOINTS = {
  CONTROL: `${API_BASE_URL}/control`,
};