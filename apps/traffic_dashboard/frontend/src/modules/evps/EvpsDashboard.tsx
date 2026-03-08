import { useEvpsSocket } from './hooks/useEvpsSocket';
import { Activity, Zap, Car, AlertTriangle, CheckCircle, Play, Square } from 'lucide-react';

// Using the same API base as SystemOverview for the toggle fetch
const BASE_URL = '/api';

export default function EvpsDashboard() {
    const { isConnected, metrics } = useEvpsSocket();

    const { active_evs = 0, override_junctions = [], evps_status = 'Idle', fleet = [] } = metrics;

    const isSystemActive = evps_status === 'Active';

    // Toggle function mapping to the real-time isSystemActive state
    const toggleEvps = async () => {
        try {
            const newState = !isSystemActive;
            await fetch(`${BASE_URL}/evps/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enable: newState })
            });
            // State will automatically update on next websocket tick
        } catch (e) {
            console.error("Failed to toggle EVPS", e);
        }
    };

    // Metric Component Helper
    const StatCard = ({ title, value, unit, icon, color, subtext }: any) => (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-start justify-between">
            <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">{title}</p>
                <h3 className="text-2xl font-bold text-white">
                    {value} {unit && <span className="text-sm font-normal text-slate-500">{unit}</span>}
                </h3>
                {subtext && <p className="text-xs text-slate-500 mt-2">{subtext}</p>}
            </div>
            <div className={`p-2.5 rounded-lg bg-slate-800/50 ${color} text-white`}>
                {icon}
            </div>
        </div>
    );

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header / Status */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
                        EVPS Dashboard
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${isConnected ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
                            {isConnected ? 'Online' : 'Offline'}
                        </span>
                    </h1>
                    <p className="text-slate-400 text-sm">Emergency Vehicle Preemption System Metrics & Fleet Status</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={toggleEvps}
                        disabled={!isConnected}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg ${isSystemActive
                            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20'
                            : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/20'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        {isSystemActive ? <><Square size={16} fill="currentColor" /> Stop EVPS</> : <><Play size={16} fill="currentColor" /> Start EVPS</>}
                    </button>
                </div>
            </div>

            {/* Top Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <StatCard
                    title="Active Emergency Vehicles"
                    value={active_evs}
                    icon={<Car size={18} />}
                    color="text-amber-500"
                    subtext="EVs currently requesting priority"
                />
                <StatCard
                    title="Active Green Waves"
                    value={override_junctions.length}
                    icon={<Zap size={18} />}
                    color="text-emerald-500"
                    subtext="Signals overridden for EVs"
                />
                <StatCard
                    title="System Status"
                    value={evps_status}
                    icon={<Activity size={18} />}
                    color={isSystemActive ? "text-emerald-500" : "text-slate-500"}
                    subtext="Overall EVPS operational state"
                />
            </div>

            {/* Live Fleet Telemetry Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mt-8">
                <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                    <h3 className="text-white font-semibold flex items-center gap-2">
                        <AlertTriangle size={18} className="text-amber-500" />
                        Live Fleet Telemetry
                    </h3>
                </div>

                {fleet.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">
                        <Car className="mx-auto h-12 w-12 text-slate-700 mb-3 opacity-50" />
                        <p>No emergency vehicles currently active in the simulation.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto border-t-0">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-slate-400 uppercase bg-slate-800/50 border-b border-slate-800">
                                <tr>
                                    <th className="px-6 py-4 font-medium">Vehicle ID</th>
                                    <th className="px-6 py-4 font-medium text-right">Current Speed</th>
                                    <th className="px-6 py-4 font-medium text-center">Dispatch Priority</th>
                                    <th className="px-6 py-4 font-medium text-center">Safety Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fleet.map((ev, idx) => (
                                    <tr key={ev.id || idx} className="border-b border-slate-800 hover:bg-slate-800/30 transition-colors">
                                        <td className="px-6 py-4 font-medium text-white flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                                                <Car size={14} className="text-indigo-400" />
                                            </div>
                                            {ev.id}
                                        </td>
                                        <td className="px-6 py-4 text-slate-300 text-right font-mono">
                                            {(ev.speed || 0).toFixed(1)} <span className="text-slate-500 text-xs ml-1">km/h</span>
                                        </td>
                                        <td className="px-6 py-4 text-center border-l-transparent">
                                            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                                Level {ev.priority || 1}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex justify-center">
                                                {ev.safety_blocked ? (
                                                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                                        <AlertTriangle size={14} />
                                                        BLOCKED / DENIED
                                                    </span>
                                                ) : (
                                                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                        <CheckCircle size={14} />
                                                        CLEAR
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
