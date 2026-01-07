import React from 'react';
import { Activity, Car, Zap, Clock } from 'lucide-react';
import MpcStatCard from './MpcStatCard';
import MpcChartCard from './MpcChartCard';

interface MpcMonitorTabProps {
    status: any;
    dataHistory: any[];
}

const MpcMonitorTab: React.FC<MpcMonitorTabProps> = ({ status, dataHistory }) => {
    // Determine metrics from status object (which matches the backend response structure)
    const metrics = {
        activeVehicles: status?.stats?.vehicle_count || 0,
        avgSpeed: status?.stats?.avg_speed || 0,
        totalWait: status?.stats?.total_waiting_time || 0,
        maxQueue: status?.stats?.max_queue_length || 0
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <MpcStatCard title="Active Vehicles" value={metrics.activeVehicles} unit="cars" icon={<Car />} color="text-blue-500" />
                <MpcStatCard title="Avg Speed" value={metrics.avgSpeed} unit="m/s" icon={<Zap />} color="text-amber-400" />
                <MpcStatCard title="Total Wait" value={metrics.totalWait} unit="s" icon={<Clock />} color="text-rose-500" />
                <MpcStatCard title="Max Queue" value={metrics.maxQueue} unit="veh" icon={<Activity />} color="text-purple-500" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/*  Use waitingTime and avgSpeed from history */}
                <MpcChartCard title="Total Waiting Time" data={dataHistory} dataKey="waitingTime" color="text-rose-500" fillId="wGrad" />
                <MpcChartCard title="Network Speed Flow" data={dataHistory} dataKey="avgSpeed" color="text-amber-400" fillId="sGrad" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-1 gap-6">
                <MpcChartCard title="Active Vehicles" data={dataHistory} dataKey="vehicles" color="text-blue-500" fillId="vGrad" height="h-64" />
            </div>
        </div>
    );
};

export default MpcMonitorTab;
