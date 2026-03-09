import React, { useEffect, useState } from 'react';
import { Activity, Car, Cpu, Brain } from 'lucide-react';
import GnnStatCard from './GnnStatCard';
import GnnChartCard from './GnnChartCard';
import GnnRealTimeLatencyBarChart from './GnnRealTimeLatencyBarChart';
import GnnRealTimeUncertaintyChart from './GnnRealTimeUncertaintyChart';
import GnnActionLog from './GnnActionLog';
import { DASHBOARD_API_URL } from '../../../config';

interface GnnMonitorTabProps {
    socketData: {
        currentMetrics: any;
        dataHistory: any[];
    };
    isRunning: boolean;
}

const GnnMonitorTab: React.FC<GnnMonitorTabProps> = ({ socketData, isRunning }) => {
    const { currentMetrics, dataHistory } = socketData;
    const gnnTelemetry = currentMetrics?.gnn_telemetry || { perNodeLatencyMs: {}, uncertaintyScore: 0 };

    // Process new per-node latency map into an average for the stat card
    const latencies = Object.values(gnnTelemetry.perNodeLatencyMs || {}) as number[];
    const avgLatency = latencies.length > 0
        ? latencies.reduce((sum, val) => sum + val, 0) / latencies.length
        : 0;
    const [baselineData, setBaselineData] = useState<any[]>([]);

    useEffect(() => {
        const fetchBaseline = async () => {
            try {
                const res = await fetch(`${DASHBOARD_API_URL}/api/baseline/data`);
                const data = await res.json();
                if (Array.isArray(data)) {
                    setBaselineData(data);
                }
            } catch (err) {
                console.error("Failed to fetch baseline:", err);
            }
        };
        fetchBaseline();
    }, []);

    if (!isRunning) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-4 animate-in fade-in">
                <Activity size={48} className="opacity-20" />
                <p className="text-lg font-medium">Agent is Offline</p>
                <p className="text-sm opacity-60">Start the GNN Agent to view real-time metrics and baseline comparison.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <GnnStatCard title="Avg Node Latency" value={avgLatency.toFixed(2)} unit="ms" icon={<Cpu />} color="text-emerald-500" />
                <GnnStatCard title="Model Uncertainty" value={typeof gnnTelemetry.uncertaintyScore === 'number' ? gnnTelemetry.uncertaintyScore.toFixed(4) : '0.0000'} unit="Score" icon={<Brain />} color="text-amber-500" />
                <GnnStatCard title="Avg Queue" value={currentMetrics.total_queue} unit="veh" icon={<Car />} color="text-blue-500" />
                <GnnStatCard title="Throughput" value={currentMetrics.cumulative_throughput} unit="veh" icon={<Activity />} color="text-purple-500" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GnnRealTimeLatencyBarChart socketData={socketData} />
                <GnnRealTimeUncertaintyChart socketData={socketData} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GnnChartCard title="Queue Length (Congestion)" data={dataHistory} baselineData={baselineData} dataKey="total_queue" color="text-blue-500" fillId="qGrad" />
                <GnnChartCard title="Network Speed Flow" data={dataHistory} baselineData={baselineData} dataKey="avg_speed" color="text-amber-400" fillId="sGrad" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1">
                    <GnnChartCard title="CO2 Impact" data={dataHistory} baselineData={baselineData} dataKey="total_co2" color="text-emerald-500" fillId="cGrad" height="h-64" />
                </div>
                <div className="lg:col-span-2">
                    <GnnActionLog socketData={socketData} />
                </div>
            </div>
        </div>
    );
};

export default GnnMonitorTab;
