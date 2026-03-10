import { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Car, Zap, Clock, BarChart3, TrendingUp } from 'lucide-react';

// Reusing the same API base
const BASE_URL = '/api';

export default function SystemOverview() {
    const [status, setStatus] = useState<any>(null);
    const [dataHistory, setDataHistory] = useState<any[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                // Poll the same simulation data endpoint
                const res = await fetch(`${BASE_URL}/simulation/data`);
                if (res.ok) {
                    const data = await res.json();
                    setStatus(data);
                    setIsConnected(true);

                    if (data.status === 'success' && data.step > 0) {
                        setDataHistory(prev => {
                            // Avoid duplicates if steps haven't advanced
                            if (prev.length > 0 && prev[prev.length - 1].step === data.step) return prev;

                            const newData = {
                                step: data.step,
                                vehicles: data.vehicle_count,
                                avgSpeed: data.stats?.avg_speed || 0,
                                totalQueue: data.stats?.total_queue_length || 0, // Assuming API provides this or we use avg_queue
                                avgQueue: data.stats?.avg_queue_length || 0,
                                waitingTime: data.stats?.total_waiting_time || 0
                            };
                            return [...prev, newData].slice(-50); // Keep last 50 points
                        });
                    }
                } else {
                    setIsConnected(false);
                }
            } catch (e) {
                setIsConnected(false);
            }
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    // Metric Component Helper
    const StatCard = ({ title, value, unit, icon, color, subtext }: any) => (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-start justify-between">
            <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">{title}</p>
                <h3 className="text-2xl font-bold text-white">
                    {value} <span className="text-sm font-normal text-slate-500">{unit}</span>
                </h3>
                {subtext && <p className="text-xs text-slate-500 mt-2">{subtext}</p>}
            </div>
            <div className={`p-2.5 rounded-lg bg-slate-800/50 ${color} text-white`}>
                {icon}
            </div>
        </div>
    );

    if (!isConnected && !status) {
        return (
            <div className="h-full flex items-center justify-center flex-col text-slate-500">
                <Activity className="w-10 h-10 mb-4 animate-pulse opacity-50" />
                <p>Waiting for Simulation Stream...</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Header / Status */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white mb-1">System Overview</h1>
                    <p className="text-slate-400 text-sm">Real-time baseline performance metrics across the network.</p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 px-4 py-2 rounded-lg">
                        <div className={`w-2 h-2 rounded-full ${status?.is_running ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                        <span className="text-sm font-mono text-slate-300">
                            STEP: <span className="text-white font-bold">{status?.step || 0}</span>
                        </span>
                    </div>
                </div>
            </div>

            {/* Top Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="Avg Network Speed"
                    value={status?.stats?.avg_speed?.toFixed(1) || 0}
                    unit="m/s"
                    icon={<Zap size={18} />}
                    color="text-amber-400"
                    subtext="Target: > 8.0 m/s"
                />
                <StatCard
                    title="Avg Queue Length"
                    value={status?.stats?.avg_queue_length?.toFixed(1) || 0}
                    unit="veh"
                    icon={<BarChart3 size={18} />}
                    color="text-blue-500"
                    subtext="Per Lane Average"
                />
                <StatCard
                    title="Total Waiting Time"
                    value={status?.stats?.total_waiting_time?.toFixed(0) || 0}
                    unit="s"
                    icon={<Clock size={18} />}
                    color="text-rose-500"
                    subtext="Cumulative Delay"
                />
                <StatCard
                    title="Active Vehicles"
                    value={status?.stats?.vehicle_count || 0}
                    unit="cars"
                    icon={<Car size={18} />}
                    color="text-emerald-500"
                    subtext="In Network"
                />
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* 1. Queue Length Chart */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-80 flex flex-col">
                    <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-slate-200 font-semibold text-sm flex items-center gap-2">
                            <TrendingUp size={16} className="text-blue-500" />
                            Average Queue Length Trend
                        </h3>
                    </div>
                    <div className="flex-1 w-full min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={dataHistory}>
                                <defs>
                                    <linearGradient id="colorQueue" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                <XAxis dataKey="step" hide />
                                <YAxis hide domain={['auto', 'auto']} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }}
                                    itemStyle={{ color: '#e2e8f0' }}
                                    labelStyle={{ display: 'none' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="avgQueue"
                                    stroke="#3b82f6"
                                    strokeWidth={2}
                                    fill="url(#colorQueue)"
                                    isAnimationActive={false}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* 2. Speed Chart */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-80 flex flex-col">
                    <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-slate-200 font-semibold text-sm flex items-center gap-2">
                            <Activity size={16} className="text-amber-500" />
                            Average Network Speed
                        </h3>
                    </div>
                    <div className="flex-1 w-full min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={dataHistory}>
                                <defs>
                                    <linearGradient id="colorSpeed" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                <XAxis dataKey="step" hide />
                                <YAxis hide domain={['auto', 'auto']} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }}
                                    itemStyle={{ color: '#e2e8f0' }}
                                    labelStyle={{ display: 'none' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="avgSpeed"
                                    stroke="#f59e0b"
                                    strokeWidth={2}
                                    fill="url(#colorSpeed)"
                                    isAnimationActive={false}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>
        </div>
    );
}
