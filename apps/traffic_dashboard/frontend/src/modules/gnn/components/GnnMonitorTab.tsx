import React from 'react';
import { Activity, Car, Zap, Leaf } from 'lucide-react';
import GnnStatCard from './GnnStatCard';
import GnnChartCard from './GnnChartCard';

interface GnnMonitorTabProps {
    socketData: {
        currentMetrics: any;
        dataHistory: any[];
    };
}

const GnnMonitorTab: React.FC<GnnMonitorTabProps> = ({ socketData }) => {
    const { currentMetrics, dataHistory } = socketData;
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <GnnStatCard title="Avg Queue" value={currentMetrics.total_queue} unit="veh" icon={<Car />} color="text-blue-500" />
                <GnnStatCard title="Avg Speed" value={currentMetrics.avg_speed} unit="m/s" icon={<Zap />} color="text-amber-400" />
                <GnnStatCard title="Emissions" value={currentMetrics.total_co2} unit="g/s" icon={<Leaf />} color="text-emerald-500" />
                <GnnStatCard title="Throughput" value={currentMetrics.cumulative_throughput} unit="veh" icon={<Activity />} color="text-purple-500" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <GnnChartCard title="Queue Length (Congestion)" data={dataHistory} dataKey="total_queue" color="text-blue-500" fillId="qGrad" />
                <GnnChartCard title="Network Speed Flow" data={dataHistory} dataKey="avg_speed" color="text-amber-400" fillId="sGrad" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1">
                    <GnnChartCard title="CO2 Impact" data={dataHistory} dataKey="total_co2" color="text-emerald-500" fillId="cGrad" height="h-64" />
                </div>
                <div className="lg:col-span-2">
                    <GnnChartCard title="Waiting Time Distribution" data={dataHistory} dataKey="total_waiting_time" color="text-rose-500" fillId="wGrad" height="h-64" />
                </div>
            </div>
        </div>
    );
};

export default GnnMonitorTab;
