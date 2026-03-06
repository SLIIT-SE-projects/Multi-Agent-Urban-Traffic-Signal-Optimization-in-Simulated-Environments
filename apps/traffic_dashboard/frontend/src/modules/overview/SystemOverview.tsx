import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Activity, Car, Zap, Clock, BarChart3, TrendingUp, ShieldAlert, Play } from 'lucide-react';
import { WS_BASE_URL } from '../../config';

// Reusing the same API base
const BASE_URL = '/api';

export default function SystemOverview() {
    const [status, setStatus] = useState<any>(null);
    const [dataHistory, setDataHistory] = useState<any[]>([]);
    const [isConnected, setIsConnected] = useState(false);


    // --- EVPS State ---
    const [evpsMetrics, setEvpsMetrics] = useState<any>(null);
    const [evpsWsConnected, setEvpsWsConnected] = useState(false);

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

        // --- EVPS WebSocket Connection ---
        const ws = new WebSocket(WS_BASE_URL);
        ws.onopen = () => setEvpsWsConnected(true);
        ws.onclose = () => setEvpsWsConnected(false);
        ws.onmessage = (event) => {
            try {
                const response = JSON.parse(event.data);
                if (response.channel === 'evps_metrics') {
                    setEvpsMetrics(response.data);
                }
            } catch (err) {
                console.error("Error parsing EVPS WS message", err);
            }
        };

        return () => {
            clearInterval(interval);
            ws.close();
        };
    }, []);

    const handleStartEVPS = async () => {
        try {
            console.log("handleStartEVPS clicked! status:", status);
            // TraCI strictly requires num-clients at boot. 
            // If the simulation is running without EVPS, we must restart it.
            // Note: /api/simulation/data returns {status: 'success'} when properly running
            if (status?.status === 'success') {
                console.log("Stopping current simulation...");
                await fetch(`${BASE_URL}/simulation/stop`, { method: 'POST' });

                // Poll the backend until the background teardown thread finishes
                console.log("Waiting for SUMO to cleanly exit...");
                let stopped = false;
                for (let i = 0; i < 15; i++) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    const res = await fetch(`${BASE_URL}/simulation/status`);
                    const currentStatus = await res.json();

                    // The backend sets 'is_running' to false immediately, but keeps 'stopping'
                    // as true while the background thread handles the blocking traci.close() call.
                    if (currentStatus.stopping === false) {
                        stopped = true;
                        break;
                    }
                }
                if (!stopped) {
                    console.warn("SUMO took too long to stop. Attempting EVPS boot anyway...");
                }
            }

            console.log("Booting simulation with use_evps: true...");
            // Re-boot the Core Simulation in EVPS mode (2 clients)
            // The Flask API will also publish the 'start' command to Redis!
            const startRes = await fetch(`${BASE_URL}/simulation/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ use_evps: true })
            });
            const startData = await startRes.json();
            console.log("Start Response:", startData);

            if (startData.status === "success") {
                console.log("Starting auto-stepping...");
                // Start stepping automatically so the user immediately sees action
                await fetch(`${BASE_URL}/simulation/auto-step/start`, { method: 'POST' });
                console.log("EVPS Start Sequence Completed.");
            } else {
                console.error("Simulation failed to start in EVPS mode", startData);
            }

        } catch (e) {
            console.error("Failed to start EVPS sequence", e);
        }
    };

    const handleStopEVPS = async () => {
        try {
            console.log("handleStopEVPS clicked!");
            if (status?.status === 'success') {
                console.log("Stopping EVPS simulation...");
                await fetch(`${BASE_URL}/simulation/stop`, { method: 'POST' });

                // Poll the backend until the background teardown thread finishes
                console.log("Waiting for SUMO to cleanly exit...");
                let stopped = false;
                for (let i = 0; i < 15; i++) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    const res = await fetch(`${BASE_URL}/simulation/status`);
                    const currentStatus = await res.json();

                    if (currentStatus.stopping === false) {
                        stopped = true;
                        break;
                    }
                }
                if (!stopped) {
                    console.warn("SUMO took too long to stop. Attempting normal boot anyway...");
                }
            }

            console.log("Booting simulation with use_evps: false...");
            const startRes = await fetch(`${BASE_URL}/simulation/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ use_evps: false })
            });
            const startData = await startRes.json();

            if (startData.status === "success") {
                console.log("Starting auto-stepping...");
                await fetch(`${BASE_URL}/simulation/auto-step/start`, { method: 'POST' });
                console.log("Normal Start Sequence Completed.");
            } else {
                console.error("Simulation failed to start in normal mode", startData);
            }

        } catch (e) {
            console.error("Failed to stop EVPS sequence", e);
        }
    };

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
                <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 px-4 py-2 rounded-lg">
                    <div className={`w-2 h-2 rounded-full ${status?.is_running ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                    <span className="text-sm font-mono text-slate-300">
                        STEP: <span className="text-white font-bold">{status?.step || 0}</span>
                    </span>
                </div>
            </div>

            {/* EVPS Card */}
            <div className="bg-slate-900 border border-indigo-900/50 rounded-xl p-5 flex items-center justify-between shadow-lg shadow-indigo-900/10">
                <div className="flex items-center gap-4">
                    <div className="p-3 rounded-xl bg-indigo-500/20">
                        <ShieldAlert className="w-6 h-6 text-indigo-400" />
                    </div>
                    <div>
                        <h3 className="text-white font-semibold">Emergency Vehicle Preemption (EVPS)</h3>
                        <div className="flex items-center gap-4 mt-1 text-sm text-slate-400">
                            <span className="flex items-center gap-1">
                                <span className={`w-2 h-2 rounded-full ${evpsWsConnected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                                Server: {evpsWsConnected ? 'Connected' : 'Disconnected'}
                            </span>
                            {evpsMetrics && (
                                <>
                                    <span>•</span>
                                    <span>Active EVs: <strong className="text-white">{evpsMetrics.total_active_evs || 0}</strong></span>
                                    <span>•</span>
                                    <span>Green Waves: <strong className="text-indigo-400">{evpsMetrics.green_waves_active || 0}</strong></span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
                {status?.use_evps ? (
                    <button
                        onClick={handleStopEVPS}
                        className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
                    >
                        Stop EVPS
                    </button>
                ) : (
                    <button
                        onClick={handleStartEVPS}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition"
                    >
                        Start EVPS
                    </button>
                )}
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
