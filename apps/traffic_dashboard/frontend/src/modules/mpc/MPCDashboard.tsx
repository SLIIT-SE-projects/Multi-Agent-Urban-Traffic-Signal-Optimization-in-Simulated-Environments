import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Play, Pause, Square, Activity, Clock, Zap, Car } from 'lucide-react';

// API Service (Inline for simplicity, or import if existing)
const BASE_URL = '/api';

export function MPCDashboard() {
    const [status, setStatus] = useState<any>(null);
    const [dataHistory, setDataHistory] = useState<any[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [mpcActive, setMpcActive] = useState(false);

    // Poll Status
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${BASE_URL}/simulation/data`);
                if (res.ok) {
                    const data = await res.json();
                    setStatus(data);
                    setIsConnected(true);

                    if (data.status === 'success') {
                        setDataHistory(prev => {
                            const newData = [...prev, {
                                step: data.step,
                                vehicles: data.vehicle_count,
                                avgSpeed: data.stats?.avg_speed || 0,
                                waitingTime: data.stats?.total_waiting_time || 0
                            }];
                            return newData.slice(-50); // Keep last 50 points
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

    const handleStart = async () => {
        // await fetch(`${BASE_URL}/simulation/start`, { method: 'POST' });
        // await fetch(`${BASE_URL}/simulation/auto-step/start`, { method: 'POST' });

        // Default to MPC if this is the MPC dashboard
        loadMPC();
    };

    const handleStop = async () => {
        await fetch(`${BASE_URL}/optimizer/unload`, { method: 'POST' });
    };

    const loadMPC = async () => {
        await fetch(`${BASE_URL}/optimizer/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'mpc' })
        });
        setMpcActive(true);
    };

    const loadBaseline = async () => {
        await fetch(`${BASE_URL}/optimizer/unload`, { method: 'POST' });
        setMpcActive(false);
    };

    if (!isConnected && !status) {
        return (
            <div className="flex items-center justify-center h-screen bg-gray-50 text-gray-500">
                <div className="text-center">
                    <Activity className="w-12 h-12 mx-auto mb-4 animate-pulse" />
                    <p className="text-xl">Connecting to Traffic Simulation...</p>
                    <p className="text-sm mt-2">Make sure the backend is running on port 5000</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 p-6 font-sans text-slate-900">

            {/* Header */}
            <header className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-3">
                        <span className="bg-blue-600 text-white p-2 rounded-lg"><Activity size={24} /></span>
                        Traffic Command Center
                    </h1>
                    <p className="text-slate-500 mt-1 ml-14">Real-time MPC Optimization & Monitoring</p>
                </div>

                <div className="flex gap-4 items-center">
                    <div className={`px-4 py-2 rounded-full text-sm font-semibold border ${status?.is_paused ? 'bg-yellow-100 text-yellow-700 border-yellow-200' :
                            status?.step > 0 ? 'bg-green-100 text-green-700 border-green-200' :
                                'bg-slate-200 text-slate-600 border-slate-300'
                        }`}>
                        {status?.is_paused ? 'PAUSED' : status?.step > 0 ? 'LIVE' : 'READY'}
                    </div>
                    <div className="bg-white px-4 py-2 rounded-lg border border-slate-200 shadow-sm">
                        <span className="text-slate-400 text-xs uppercase tracking-wider block">Current Step</span>
                        <span className="font-mono text-xl font-bold">{status?.step || 0}</span>
                    </div>
                </div>
            </header>

            {/* Controls */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
                <div className="lg:col-span-1 space-y-4">
                    <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
                        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Simulation Control</h3>
                        <div className="flex gap-2 mb-4">
                            <button onClick={handleStart} className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium transition-colors">
                                <Play size={18} fill="currentColor" /> Start
                            </button>
                            <button onClick={handleStop} className="flex-1 flex items-center justify-center gap-2 bg-red-100 hover:bg-red-200 text-red-600 py-3 rounded-lg font-medium transition-colors">
                                <Square size={18} fill="currentColor" /> Stop
                            </button>
                        </div>
                    </div>

                    <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-200">
                        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Optimizer Logic</h3>
                        <div className="space-y-2">
                            <button
                                onClick={loadMPC}
                                className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${mpcActive
                                        ? 'bg-blue-50 border-blue-500 text-blue-700 shadow-sm'
                                        : 'bg-white border-slate-200 text-slate-600 hover:border-blue-300'
                                    }`}
                            >
                                <span className="font-medium flex items-center gap-2"><Zap size={16} /> MPC Optimized</span>
                                {mpcActive && <span className="bg-blue-200 text-blue-800 text-xs px-2 py-0.5 rounded-full">Active</span>}
                            </button>

                            <button
                                onClick={loadBaseline}
                                className={`w-full flex items-center justify-between p-3 rounded-lg border transition-all ${!mpcActive
                                        ? 'bg-slate-100 border-slate-400 text-slate-800 shadow-sm'
                                        : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                                    }`}
                            >
                                <span className="font-medium flex items-center gap-2"><Clock size={16} /> Fixed Time (Baseline)</span>
                                {!mpcActive && <span className="bg-slate-200 text-slate-600 text-xs px-2 py-0.5 rounded-full">Active</span>}
                            </button>
                        </div>
                    </div>
                </div>

                {/* HUD Metrics */}
                <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <MetricCard
                        label="Active Vehicles"
                        value={status?.stats?.vehicle_count || 0}
                        unit="cars"
                        icon={<Car className="text-blue-500" />}
                        trend={12}
                    />
                    <MetricCard
                        label="Avg Speed"
                        value={status?.stats?.avg_speed?.toFixed(1) || 0}
                        unit="m/s"
                        icon={<Zap className="text-amber-500" />}
                        inverseTrend
                    />
                    <MetricCard
                        label="Total Waiting Time"
                        value={status?.stats?.total_waiting_time?.toFixed(0) || 0}
                        unit="s"
                        icon={<Clock className="text-red-500" />}
                        inverseTrend
                        isBad={(status?.stats?.total_waiting_time || 0) > 1000}
                    />

                    {/* Main Chart */}
                    <div className="md:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-slate-200 h-80">
                        <h3 className="text-lg font-bold text-slate-800 mb-6">Traffic Performance History</h3>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={dataHistory}>
                                <defs>
                                    <linearGradient id="colorWait" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.1} />
                                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                    </linearGradient>
                                    <linearGradient id="colorSpeed" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis dataKey="step" hide />
                                <YAxis yAxisId="left" orientation="left" stroke="#ef4444" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis yAxisId="right" orientation="right" stroke="#3b82f6" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                />
                                <Legend />
                                <Area yAxisId="left" type="monotone" dataKey="waitingTime" name="Waiting Time" stroke="#ef4444" fillOpacity={1} fill="url(#colorWait)" strokeWidth={2} />
                                <Area yAxisId="right" type="monotone" dataKey="avgSpeed" name="Avg Speed" stroke="#3b82f6" fillOpacity={1} fill="url(#colorSpeed)" strokeWidth={2} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

        </div>
    );
}

function MetricCard({ label, value, unit, icon, isBad }: any) {
    return (
        <div className={`bg-white p-6 rounded-xl shadow-sm border ${isBad ? 'border-red-200 bg-red-50' : 'border-slate-200'}`}>
            <div className="flex justify-between items-start mb-4">
                <div className="p-2 bg-slate-50 rounded-lg">{icon}</div>
                {/* <span className={`text-xs font-bold px-2 py-1 rounded-full ${isBad ? 'bg-red-200 text-red-800' : 'bg-green-100 text-green-800'}`}>
                    {active ? '+4%' : '--'}
                </span> */}
            </div>
            <div className="text-3xl font-bold text-slate-800 mb-1">{value} <span className="text-sm font-normal text-slate-400">{unit}</span></div>
            <div className="text-sm text-slate-500">{label}</div>
        </div>
    )
}
