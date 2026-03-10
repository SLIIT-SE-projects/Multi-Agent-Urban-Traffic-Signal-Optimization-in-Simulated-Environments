import { useEffect, useState, useRef } from 'react';
import { WS_BASE_URL, ENDPOINTS } from '../../../config';

export interface GnnPerformanceMetrics {
    perNodeLatencyMs: Record<string, number>;
    perNodeUncertainty: Record<string, number>;
    layerActivations?: Record<string, Record<string, number>>;
    uncertaintyScore: number;
}

export interface TrafficData {
    step: number;
    total_queue: number;
    avg_speed: number;
    total_co2: number;
    total_waiting_time: number;
    cumulative_throughput: number;
    gnn_telemetry?: GnnPerformanceMetrics;
    intersections?: Record<string, any>;
    lanes?: Record<string, any>;
}

export const useTrafficSocket = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [dataHistory, setDataHistory] = useState<TrafficData[]>([]);
    const [currentMetrics, setCurrentMetrics] = useState<TrafficData>({
        step: 0, total_queue: 0, avg_speed: 0, total_co2: 0, total_waiting_time: 0, cumulative_throughput: 0, gnn_telemetry: { perNodeLatencyMs: {}, perNodeUncertainty: {}, uncertaintyScore: 0 }
    });

    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        // UPDATED: Using constant from config
        const socket = new WebSocket(WS_BASE_URL);
        ws.current = socket;

        socket.onopen = () => {
            console.log(' Connected to Dashboard API');
            setIsConnected(true);
        };

        socket.onclose = () => {
            console.log(' Disconnected from Dashboard API');
            setIsConnected(false);
        };

        socket.onmessage = (event) => {
            try {
                const response = JSON.parse(event.data);

                if (response.channel === 'gnn_metrics') {
                    const data = response.data;

                    setCurrentMetrics(prev => {
                        // Only overwrite gnn_telemetry if the incoming data actually contains the perNode maps
                        const incomingTelemetry = data.gnn_telemetry;
                        const hasNewTelemetry = incomingTelemetry &&
                            incomingTelemetry.perNodeLatencyMs &&
                            Object.keys(incomingTelemetry.perNodeLatencyMs).length > 0;

                        const finalTelemetry = hasNewTelemetry ? incomingTelemetry : prev.gnn_telemetry;

                        return {
                            ...prev,
                            ...data,
                            gnn_telemetry: finalTelemetry, // Use the safeguarded telemetry
                            cumulative_throughput: prev.cumulative_throughput + (data.throughput || 0)
                        };
                    });

                    setDataHistory(prev => {
                        const newH = [...prev, { ...data, cumulative_throughput: 0 }];
                        return newH.length > 60 ? newH.slice(newH.length - 60) : newH;
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

    const sendCommand = async (action: 'start' | 'stop') => {
        try {
            // UPDATED: Using constant from config
            await fetch(ENDPOINTS.CONTROL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: action,
                    model: 'gnn'
                })
            });
        } catch (e) {
            console.error(`Failed to send ${action} command`, e);
        }
    };

    return {
        isConnected,
        currentMetrics,
        dataHistory,
        handleStart: () => sendCommand('start'),
        handleStop: () => sendCommand('stop')
    };
};
