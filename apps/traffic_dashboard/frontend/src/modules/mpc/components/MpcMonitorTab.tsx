import React from 'react';
import { Activity, Car, Zap, Clock, BarChart2, BookMarked } from 'lucide-react';
import MpcStatCard from './MpcStatCard';
import MpcChartCard from './MpcChartCard';

type DashboardMode = 'idle' | 'recording' | 'mpc_active';

interface MpcMonitorTabProps {
    mode: DashboardMode;
    status: any;
    dataHistory: any[];
    hasBaseline: boolean;
}

const MpcMonitorTab: React.FC<MpcMonitorTabProps> = ({ mode, status, dataHistory, hasBaseline }) => {
    const metrics = {
        activeVehicles: status?.stats?.vehicle_count ?? status?.vehicle_count ?? 0,
        avgSpeed: status?.stats?.avg_speed ?? 0,
        totalWait: status?.stats?.total_waiting_time ?? 0,
        maxQueue: status?.stats?.max_queue_length ?? 0,
    };

    // ── Idle placeholder ─────────────────────────────────────────────────────
    if (mode === 'idle') {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-center animate-in fade-in duration-500">
                <div className="w-20 h-20 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-6">
                    <BarChart2 size={36} className="text-slate-600" />
                </div>
                <h3 className="text-slate-300 text-lg font-semibold mb-2">No Active Session</h3>
                <p className="text-slate-500 text-sm max-w-xs leading-relaxed">
                    Use <span className="text-amber-400 font-medium">Record Baseline</span> to capture default signal behaviour,
                    then click <span className="text-indigo-400 font-medium">Activate MPC</span> to start live optimization and see the comparison.
                </p>
                {!hasBaseline && (
                    <div className="mt-6 flex items-center gap-2 bg-amber-400/5 border border-amber-400/20 rounded-lg px-4 py-3 text-amber-400 text-xs">
                        <BookMarked size={14} />
                        No baseline recorded yet — Record one first for a proper comparison.
                    </div>
                )}
                {hasBaseline && (
                    <div className="mt-6 flex items-center gap-2 bg-emerald-500/5 border border-emerald-500/20 rounded-lg px-4 py-3 text-emerald-400 text-xs">
                        <Activity size={14} />
                        Baseline is ready. Click Activate MPC to compare!
                    </div>
                )}
            </div>
        );
    }

    // ── Recording placeholder ────────────────────────────────────────────────
    if (mode === 'recording') {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-center animate-in fade-in duration-500">
                <div className="w-20 h-20 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mb-6">
                    <BookMarked size={36} className="text-amber-400 animate-pulse" />
                </div>
                <h3 className="text-amber-300 text-lg font-semibold mb-2">Recording Baseline…</h3>
                <p className="text-slate-500 text-sm max-w-xs leading-relaxed">
                    Running the simulation with default SUMO traffic signals for 500 steps.
                    Charts will appear once you activate MPC.
                </p>
            </div>
        );
    }

    // ── MPC Active: Live Charts + Stats ──────────────────────────────────────
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <MpcStatCard title="Active Vehicles" value={metrics.activeVehicles} unit="cars" icon={<Car />} color="text-blue-500" />
                <MpcStatCard title="Avg Speed" value={metrics.avgSpeed} unit="m/s" icon={<Zap />} color="text-amber-400" />
                <MpcStatCard title="Total Wait" value={metrics.totalWait} unit="s" icon={<Clock />} color="text-rose-500" />
                <MpcStatCard title="Max Queue" value={metrics.maxQueue} unit="veh" icon={<Activity />} color="text-purple-500" />
            </div>

            {/* Legend */}
            {hasBaseline && (
                <div className="flex items-center gap-6 text-xs text-slate-400 px-1">
                    <span className="flex items-center gap-2">
                        <span className="inline-block w-8 h-0.5 bg-indigo-400 rounded" />
                        MPC Control Signals (Live)
                    </span>
                    <span className="flex items-center gap-2">
                        <span className="inline-block w-8 border-t-2 border-dashed border-slate-500" />
                        Baseline (Default Signals)
                    </span>
                </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <MpcChartCard
                    title="Total Waiting Time"
                    data={dataHistory}
                    dataKey="waitingTime"
                    baselineKey={hasBaseline ? "baseline_waitingTime" : undefined}
                    color="text-rose-500"
                    fillId="wGrad"
                />
                <MpcChartCard
                    title="Network Speed Flow"
                    data={dataHistory}
                    dataKey="avgSpeed"
                    baselineKey={hasBaseline ? "baseline_avgSpeed" : undefined}
                    color="text-amber-400"
                    fillId="sGrad"
                />
            </div>
            <div className="grid grid-cols-1 gap-6">
                <MpcChartCard
                    title="Max Queue Length"
                    data={dataHistory}
                    dataKey="maxQueue"
                    baselineKey={hasBaseline ? "baseline_maxQueue" : undefined}
                    color="text-purple-500"
                    fillId="qGrad"
                    height="h-64"
                />
            </div>
        </div>
    );
};

export default MpcMonitorTab;
