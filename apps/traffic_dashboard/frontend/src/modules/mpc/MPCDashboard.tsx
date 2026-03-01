import { useState, useEffect, useRef } from 'react';
import { Activity, Square, Settings } from 'lucide-react';
import MpcMonitorTab from './components/MpcMonitorTab';
import MpcConfigTab from './components/MpcConfigTab';

// API Service (Inline for simplicity)
const BASE_URL = '/api';

export function MPCDashboard() {
    const [activeSubTab, setActiveSubTab] = useState('monitor');
    const [status, setStatus] = useState<any>(null);
    const [dataHistory, setDataHistory] = useState<any[]>([]);
    const [isConnected, setIsConnected] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [mpcActive, setMpcActive] = useState(false);
    const [toast, setToast] = useState<{ title: string; message: string; type: 'success' | 'info' | 'error' } | null>(null);

    const showToast = (title: string, message: string, type: 'success' | 'info' | 'error' = 'info') => {
        setToast({ title, message, type });
        setTimeout(() => setToast(null), 4000);
    };

    // --- Baseline Logic ---
    const [baselineData, setBaselineData] = useState<any[] | null>(null);
    const [isBaselineRun, setIsBaselineRun] = useState(false);
    const hasSavedBaseline = useRef(false); // Validated save to prevent duplicates

    // 1. Fetch Baseline on Mount
    useEffect(() => {
        const fetchBaseline = async () => {
            try {
                const res = await fetch(`${BASE_URL}/mpc/baseline`);
                if (res.ok) {
                    const json = await res.json();
                    if (json.status === 'success' && Array.isArray(json.data) && json.data.length > 0) {
                        setBaselineData(json.data);
                        console.log("Loaded Baseline Data:", json.data.length, "points");
                    } else {
                        console.warn("Baseline found but empty/invalid.");
                        setIsBaselineRun(true);
                    }
                } else {
                    console.log("No Baseline Found. This run will be recorded as Baseline.");
                    setIsBaselineRun(true);
                }
            } catch (e) {
                console.error("Failed to fetch baseline:", e);
                setIsBaselineRun(true);
            }
        };
        fetchBaseline();
    }, []);

    // 2. Poll Status & Update Data
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${BASE_URL}/simulation/data`);
                if (res.ok) {
                    const data = await res.json();
                    setStatus(data);
                    setIsConnected(true);
                    const simRunning = data.is_running && !data.is_paused;
                    setIsRunning(simRunning);

                    // Reset saved flag if we start running again
                    if (simRunning && hasSavedBaseline.current) {
                        hasSavedBaseline.current = false;
                    }

                    if (data.status === 'success') {
                        setDataHistory(prev => {
                            // Deduplication: Don't add if step is same as last
                            if (prev.length > 0 && prev[prev.length - 1].step === data.step) return prev;

                            // 2a. Create current data point
                            const newPoint: any = {
                                step: data.step,
                                vehicles: data.vehicle_count,
                                avgSpeed: data.stats?.avg_speed || 0,
                                waitingTime: data.stats?.total_waiting_time || 0,
                                maxQueue: data.stats?.max_queue_length || 0
                            };

                            // 2b. Merge with Baseline (if exists)
                            if (baselineData && baselineData.length > 0) {
                                // Find baseline point with CLOSEST step to handle polling jitter
                                // We filter for points reasonably close (e.g. within 10 steps) to avoid matching step 100 to step 0
                                const closest = baselineData.reduce((prev, curr) => {
                                    return (Math.abs(curr.step - data.step) < Math.abs(prev.step - data.step) ? curr : prev);
                                });

                                // Only use if it's within a reasonable threshold (e.g. 20 steps)
                                if (Math.abs(closest.step - data.step) <= 20) {
                                    newPoint.baseline_avgSpeed = closest.avgSpeed;
                                    newPoint.baseline_waitingTime = closest.waitingTime;
                                    newPoint.baseline_maxQueue = closest.maxQueue;
                                }
                            }

                            // Keep history manageable
                            // If isBaselineRun, we might want to keep ALL history to save it?
                            // Yes, for recording baseline we need full history.
                            // But for display we might slice. 
                            // Strategy: Keep full history in a separate ref if recording? 
                            // Or just allow growing array (simulation isn't infinite in this context).
                            // Let's cap visual history but maybe we need full persistence.
                            // User said: "Record metrics... for every simulation step and save... at the end".

                            // Let's just keep last 100 for display, but full array for saving?
                            // Actually, if we slice, we lose data to save.
                            // Let's just keep growing array for now (assuming scenario < 1 hr).
                            return [...prev, newPoint];
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
    }, [baselineData]); // Re-bind when baselineData loads

    // 3. Save Baseline on Stop
    useEffect(() => {
        if (!isRunning && isBaselineRun && dataHistory.length > 100 && !hasSavedBaseline.current) {
            saveBaseline();
        }
    }, [isRunning, isBaselineRun, dataHistory]);

    const saveBaseline = async () => {
        try {
            console.log("Saving Baseline Run...", dataHistory.length);
            await fetch(`${BASE_URL}/mpc/baseline`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dataHistory)
            });
            hasSavedBaseline.current = true;
            // Optionally, we load it back as baseline so next time it shows dotted?
            // setBaselineData(dataHistory);
            // setIsBaselineRun(false);
        } catch (e) {
            console.error("Failed to save baseline:", e);
        }
    };

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
        try {
            await fetch(`${BASE_URL}/optimizer/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'mpc' })
            });
            setMpcActive(true);
            showToast('MPC Activated', 'The Model Predictive Controller has taken over the traffic signals. Watching for live data...', 'success');
        } catch (error) {
            showToast('Activation Failed', 'Could not activate MPC. Check backend logs.', 'error');
        }
    };

    const loadBaseline = async () => {
        try {
            await fetch(`${BASE_URL}/optimizer/unload`, { method: 'POST' });
            setMpcActive(false);
            showToast('Normal Signals', 'Reverted to default static traffic signals (Baseline).', 'info');
        } catch (error) {
            showToast('Action Failed', 'Could not unload MPC.', 'error');
        }
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
                    <p className="text-slate-400 text-sm flex items-center gap-2">
                        Model Predictive Control Traffic Signal Optimization
                        {isBaselineRun && <span className="text-amber-400 text-xs px-2 py-0.5 bg-amber-400/10 border border-amber-400/50 rounded-full">Recording Baseline</span>}
                        {baselineData && <span className="text-blue-400 text-xs px-2 py-0.5 bg-blue-400/10 border border-blue-400/50 rounded-full">Comparison Mode</span>}
                    </p>
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
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${!mpcActive && isRunning
                            ? 'bg-slate-700 text-white border border-slate-500'
                            : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                            }`}
                    >
                        <Settings size={16} />
                        Normal Signals
                    </button>

                    <button
                        onClick={handleStop}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20 transition-colors"
                    >
                        <Square size={16} fill="currentColor" />
                        Stop
                    </button>
                </div>
            </div>

            <div className="flex border-b border-slate-800 mb-6">
                <button
                    onClick={() => setActiveSubTab('monitor')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeSubTab === 'monitor'
                        ? 'border-indigo-500 text-indigo-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                >
                    <Activity size={16} /> Real-time Monitor
                </button>
                <button
                    onClick={() => setActiveSubTab('config')}
                    className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeSubTab === 'config'
                        ? 'border-indigo-500 text-indigo-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                        }`}
                >
                    <Settings size={16} /> Controller Config
                </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {activeSubTab === 'monitor' && <MpcMonitorTab status={status} dataHistory={dataHistory} />}
                {activeSubTab === 'config' && <MpcConfigTab />}
            </div>

            {/* User Friendly Toast Notification */}
            {toast && (
                <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-5 fade-in duration-300">
                    <div className={`flex items-start gap-4 px-6 py-4 rounded-xl shadow-2xl border ${toast.type === 'success' ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-100' :
                            toast.type === 'error' ? 'bg-rose-950/90 border-rose-500/50 text-rose-100' :
                                'bg-slate-900/90 border-slate-700 text-slate-200'
                        } backdrop-blur-md max-w-sm`}>
                        <div className="mt-0.5">
                            {toast.type === 'success' ? <Activity className="text-emerald-400" size={20} /> :
                                toast.type === 'error' ? <Square className="text-rose-400" size={20} /> :
                                    <Settings className="text-slate-400" size={20} />}
                        </div>
                        <div>
                            <h4 className={`font-semibold text-sm mb-1 ${toast.type === 'success' ? 'text-emerald-300' :
                                    toast.type === 'error' ? 'text-rose-300' : 'text-slate-300'
                                }`}>{toast.title}</h4>
                            <p className="text-xs opacity-80 leading-relaxed">{toast.message}</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
