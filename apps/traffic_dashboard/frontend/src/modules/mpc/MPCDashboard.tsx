import { useEffect, useState } from 'react';
import { Activity, Sliders, Square, Pause } from 'lucide-react';
import MpcMonitorTab from './components/MpcMonitorTab';
import MpcConfigTab from './components/MpcConfigTab';

// API Service (Inline for simplicity)
const BASE_URL = '/api';

export function MPCDashboard() {
    const [activeSubTab, setActiveSubTab] = useState('monitor');
    const [status, setStatus] = useState<any>(null);
    const [dataHistory, setDataHistory] = useState<any[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isRunning, setIsRunning] = useState(false); // Using local state for button toggle logic mostly
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
                    // Sync local running state
                    setIsRunning(data.is_running && !data.is_paused);

                    if (data.status === 'success') {
                        setDataHistory(prev => {
                            const newData = [...prev, {
                                step: data.step,
                                vehicles: data.vehicle_count,
                                avgSpeed: data.stats?.avg_speed || 0,
                                waitingTime: data.stats?.total_waiting_time || 0,
                                maxQueue: data.stats?.max_queue_length || 0
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

    const handleActivateMPC = async () => {
        if (!isRunning) {
            await fetch(`${BASE_URL}/simulation/start`, { method: 'POST' });
            await fetch(`${BASE_URL}/simulation/auto-step/start`, { method: 'POST' });
        }
        await loadMPC();
    };

    const handleNormalSignals = async () => {
        await loadBaseline();
    };

    const handleStop = async () => {
        await fetch(`${BASE_URL}/simulation/stop`, { method: 'POST' });
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

    return (
        <div className="h-full flex flex-col">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        MPC Controller
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${isConnected ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
                            {isConnected ? 'Online' : 'Offline'}
                        </span>
                    </h1>
                    <p className="text-slate-400 text-sm">Model Predictive Control Traffic Signal Optimization</p>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={handleActivateMPC}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${mpcActive && isRunning
                            ? 'bg-indigo-500 text-white ring-2 ring-indigo-400 ring-offset-2 ring-offset-[#0B1120]'
                            : 'bg-indigo-600 text-white hover:bg-indigo-500'
                            }`}
                    >
                        <Activity size={16} fill={mpcActive && isRunning ? "currentColor" : "none"} />
                        {mpcActive && isRunning ? 'MPC Active' : 'Activate MPC'}
                    </button>

                    <button
                        onClick={handleNormalSignals}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${!mpcActive && isRunning
                            ? 'bg-slate-600 text-white ring-2 ring-slate-500 ring-offset-2 ring-offset-[#0B1120]'
                            : 'bg-slate-700 text-slate-200 hover:bg-slate-600'
                            }`}
                    >
                        <Pause size={16} />
                        Normal Signals
                    </button>

                    {isRunning && (
                        <button
                            onClick={handleStop}
                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20"
                        >
                            <Square size={16} fill="currentColor" /> Stop
                        </button>
                    )}
                </div>
            </div>

            <div className="flex border-b border-slate-800 mb-6">
                {[
                    { id: 'monitor', label: 'Real-time Monitor', icon: Activity },
                    { id: 'config', label: 'Controller Config', icon: Sliders },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveSubTab(tab.id)}
                        className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeSubTab === tab.id
                            ? 'border-indigo-500 text-indigo-400'
                            : 'border-transparent text-slate-400 hover:text-slate-200'
                            }`}
                    >
                        <tab.icon size={16} /> {tab.label}
                    </button>
                ))}
            </div>

            <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {activeSubTab === 'monitor' && <MpcMonitorTab status={status} dataHistory={dataHistory} />}
                {activeSubTab === 'config' && <MpcConfigTab />}
            </div>
        </div>
    );
}
