import { useEffect, useState, useRef } from 'react';
import { EVPS_WS_URL } from '../../../config';

export interface EvpsMetrics {
    active_evs?: number;
    override_junctions?: string[];
    evps_status?: string;
    fleet?: EvFleetItem[];
}

export interface EvFleetItem {
    id: string;
    speed: number;
    priority: number;
    safety_blocked: boolean;
    distance_to_tls?: number;
}

export const useEvpsSocket = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [metrics, setMetrics] = useState<EvpsMetrics>({
        active_evs: 0,
        override_junctions: [],
        evps_status: 'Idle',
        fleet: []
    });

    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        const socket = new WebSocket(EVPS_WS_URL);
        ws.current = socket;

        socket.onopen = () => {
            console.log('Connected to EVPS Dashboard API');
            setIsConnected(true);
        };

        socket.onclose = () => {
            console.log('Disconnected from EVPS Dashboard API');
            setIsConnected(false);
        };

        socket.onmessage = (event) => {
            try {
                const response = JSON.parse(event.data);

                // The EvpsAdapter native response is 'type': 'status'
                if (response.type === 'status') {
                    // It sends ev_id, active, active_fleet, green_wave_active, etc.
                    // We map active to evps_status
                    // override_junctions we parse from active_junctions

                    const fleetData = response.fleet || [];

                    setMetrics({
                        active_evs: response.active_fleet?.length || 0,
                        override_junctions: response.active_junctions?.map((j: any) => j.id) || [],
                        evps_status: response.active ? 'Active' : 'Idle',
                        fleet: fleetData
                    });
                }
            } catch (err) {
                console.error("Error parsing websocket message:", err);
            }
        };

        return () => {
            socket.close();
        };
    }, []);

    return {
        isConnected,
        metrics,
    };
};
