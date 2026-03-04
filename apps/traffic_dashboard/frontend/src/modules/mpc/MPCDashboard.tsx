import { useState, useEffect, useRef, useCallback } from 'react';
import { Activity, Square, Settings, BookMarked, Loader2, ChevronDown, X } from 'lucide-react';
import MpcMonitorTab from './components/MpcMonitorTab';
import MpcConfigTab from './components/MpcConfigTab';

const BASE_URL = '/api';

type DashboardMode = 'idle' | 'recording' | 'mpc_active';

// ── Record Baseline Config Dialog ────────────────────────────────────────────
interface RecordConfig {
    scenario: string;
    flowRate: string;   // '' means "use default / don't override"
    steps: string;      // number as string for input
}

interface RecordDialogProps {
    initialScenario: string;
    scenarios: string[];
    onConfirm: (cfg: RecordConfig) => void;
    onCancel: () => void;
}

function RecordDialog({ initialScenario, scenarios, onConfirm, onCancel }: RecordDialogProps) {
    const [cfg, setCfg] = useState<RecordConfig>({
        scenario: initialScenario,
        flowRate: '',
        steps: '500',
    });

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-6 animate-in fade-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="flex items-center justify-between mb-5">
                    <div className="flex items-center gap-2">
                        <BookMarked size={18} className="text-amber-400" />
                        <h2 className="text-white font-semibold text-base">Record Baseline Configuration</h2>
                    </div>
                    <button onClick={onCancel} className="text-slate-500 hover:text-slate-300 transition-colors">
                        <X size={18} />
                    </button>
                </div>

                <p className="text-slate-400 text-xs mb-5 leading-relaxed">
                    Choose the same scenario and flow rate you use when running MPC, so the baseline
                    comparison is fair and meaningful.
                </p>

                {/* Scenario Picker */}
                <label className="block mb-4">
                    <span className="text-slate-300 text-xs font-medium block mb-1.5">Scenario</span>
                    <div className="relative">
                        <select
                            value={cfg.scenario}
                            onChange={e => setCfg(p => ({ ...p, scenario: e.target.value }))}
                            className="w-full appearance-none bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50 pr-8"
                        >
                            {scenarios.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                    </div>
                </label>

                {/* Flow Rate Input */}
                <label className="block mb-4">
                    <span className="text-slate-300 text-xs font-medium block mb-1.5">
                        Global Flow Rate <span className="text-slate-500 font-normal">(vehicles / hour — leave blank to use scenario default)</span>
                    </span>
                    <input
                        type="number"
                        placeholder="e.g. 300"
                        value={cfg.flowRate}
                        onChange={e => setCfg(p => ({ ...p, flowRate: e.target.value }))}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                        min={1}
                    />
                </label>

                {/* Steps Input */}
                <label className="block mb-6">
                    <span className="text-slate-300 text-xs font-medium block mb-1.5">Number of Steps to Record</span>
                    <input
                        type="number"
                        value={cfg.steps}
                        onChange={e => setCfg(p => ({ ...p, steps: e.target.value }))}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                        min={100}
                        max={5000}
                    />
                </label>

                {/* Actions */}
                <div className="flex gap-3 justify-end">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={() => onConfirm(cfg)}
                        className="px-5 py-2 rounded-lg text-sm font-semibold bg-amber-500 text-slate-900 hover:bg-amber-400 transition-colors shadow-lg shadow-amber-500/20"
                    >
                        Start Recording
                    </button>
                </div>
            </div>
        </div>
    );
}


// ── Main Dashboard ────────────────────────────────────────────────────────────
export function MPCDashboard() {
    const [activeSubTab, setActiveSubTab] = useState('monitor');
    const [mode, setMode] = useState<DashboardMode>('idle');
    const [status, setStatus] = useState<any>(null);
    const [isConnected, setIsConnected] = useState(false);

    // MPC live data — only populated in mpc_active mode
    const [mpcHistory, setMpcHistory] = useState<any[]>([]);

    // Baseline
    const [baselineData, setBaselineData] = useState<any[] | null>(null);
    const [baselineMeta, setBaselineMeta] = useState<any>(null);

    // Baseline recording progress
    const [recordStep, setRecordStep] = useState(0);
    const [recordTarget, setRecordTarget] = useState(500);

    // Record dialog
    const [showRecordDialog, setShowRecordDialog] = useState(false);
    const [availableScenarios, setAvailableScenarios] = useState<string[]>([]);
    const [currentScenario, setCurrentScenario] = useState<string>('grid3x3');

    // Toast
    const [toast, setToast] = useState<{ title: string; message: string; type: 'success' | 'info' | 'error' } | null>(null);
    const showToast = useCallback((title: string, message: string, type: 'success' | 'info' | 'error' = 'info') => {
        setToast({ title, message, type });
        setTimeout(() => setToast(null), 5000);
    }, []);

    // ── Health check ─────────────────────────────────────────────────────────
    useEffect(() => {
        const id = setInterval(async () => {
            try {
                const res = await fetch(`${BASE_URL}/simulation/status`);
                setIsConnected(res.ok);
            } catch { setIsConnected(false); }
        }, 3000);
        return () => clearInterval(id);
    }, []);

    // ── Load available scenarios and current scenario from backend ────────────
    useEffect(() => {
        fetch(`${BASE_URL}/scenarios`)
            .then(r => r.json())
            .then(json => {
                if (json.scenarios) {
                    setAvailableScenarios(json.scenarios.map((s: any) => s.name));
                }
            }).catch(() => { });

        fetch(`${BASE_URL}/simulation/current-scenario`)
            .then(r => r.json())
            .then(json => {
                if (json.scenario_name) setCurrentScenario(json.scenario_name);
            }).catch(() => { });
    }, []);

    // ── Load saved baseline on mount ──────────────────────────────────────────
    useEffect(() => {
        fetch(`${BASE_URL}/mpc/baseline`)
            .then(r => r.ok ? r.json() : null)
            .then(json => {
                if (json?.status === 'success' && Array.isArray(json.data) && json.data.length > 0) {
                    setBaselineData(json.data);
                    setBaselineMeta(json.meta ?? null);
                }
            }).catch(() => { });
    }, []);

    // ── Poll baseline recording progress ─────────────────────────────────────
    useEffect(() => {
        if (mode !== 'recording') return;
        const id = setInterval(async () => {
            try {
                const res = await fetch(`${BASE_URL}/mpc/baseline/record/status`);
                const json = await res.json();
                setRecordStep(json.step);
                setRecordTarget(json.target);

                if (json.error) {
                    showToast('Recording Failed', json.error, 'error');
                    setMode('idle');
                    return;
                }
                if (!json.running && json.step >= json.target) {
                    // Reload baseline
                    const br = await fetch(`${BASE_URL}/mpc/baseline`);
                    const bj = await br.json();
                    if (bj?.status === 'success') {
                        setBaselineData(bj.data);
                        setBaselineMeta(bj.meta ?? null);
                    }
                    setMode('idle');
                    showToast('Baseline Recorded ✅', `${json.target} steps saved. Activate MPC to compare!`, 'success');
                }
            } catch { }
        }, 500);
        return () => clearInterval(id);
    }, [mode, showToast]);

    // ── Poll simulation data when MPC is active ───────────────────────────────
    const baselineRef = useRef(baselineData);
    useEffect(() => { baselineRef.current = baselineData; }, [baselineData]);

    useEffect(() => {
        if (mode !== 'mpc_active') return;
        const id = setInterval(async () => {
            try {
                const res = await fetch(`${BASE_URL}/simulation/data`);
                if (!res.ok) return;
                const data = await res.json();
                setStatus(data);
                if (data.status === 'success') {
                    setMpcHistory(prev => {
                        if (prev.length > 0 && prev[prev.length - 1].step === data.step) return prev;
                        const pt: any = {
                            step: data.step,
                            vehicles: data.vehicle_count,
                            avgSpeed: data.stats?.avg_speed ?? 0,
                            waitingTime: data.stats?.total_waiting_time ?? 0,
                            maxQueue: data.stats?.max_queue_length ?? 0,
                        };
                        const bl = baselineRef.current;
                        if (bl && bl.length > 0) {
                            const closest = bl.reduce((a, b) =>
                                Math.abs(b.step - data.step) < Math.abs(a.step - data.step) ? b : a);
                            if (Math.abs(closest.step - data.step) <= 20) {
                                pt.baseline_avgSpeed = closest.avgSpeed;
                                pt.baseline_waitingTime = closest.waitingTime;
                                pt.baseline_maxQueue = closest.maxQueue;
                            }
                        }
                        return [...prev, pt];
                    });
                }
            } catch { }
        }, 1000);
        return () => clearInterval(id);
    }, [mode]);

    // ── Button handlers ───────────────────────────────────────────────────────

    // Open dialog first, then confirm calls this
    const handleRecordConfirm = useCallback(async (cfg: RecordConfig) => {
        setShowRecordDialog(false);
        setRecordStep(0);
        setRecordTarget(Number(cfg.steps) || 500);

        const body: any = { steps: Number(cfg.steps) || 500 };
        if (cfg.scenario) body.scenario = cfg.scenario;
        if (cfg.flowRate) body.flow_rate = Number(cfg.flowRate);

        try {
            const res = await fetch(`${BASE_URL}/mpc/baseline/record`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const json = await res.json();
            if (json.status === 'started') {
                setMode('recording');
                const label = cfg.flowRate ? ` at ${cfg.flowRate} veh/hr` : '';
                showToast('Recording Started 📍', `Running ${body.steps} steps on "${cfg.scenario}"${label}…`, 'info');
            } else {
                showToast('Error', json.message ?? 'Could not start recording.', 'error');
            }
        } catch {
            showToast('Error', 'Backend unreachable.', 'error');
        }
    }, [showToast]);

    const handleActivateMPC = useCallback(async () => {
        if (mode === 'recording') return;
        try {
            await fetch(`${BASE_URL}/simulation/start`, { method: 'POST' });
            await fetch(`${BASE_URL}/simulation/auto-step/start`, { method: 'POST' });
            await fetch(`${BASE_URL}/optimizer/load`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'mpc' }),
            });
            setMpcHistory([]);
            setMode('mpc_active');
            showToast('MPC Activated ⚡', 'Live MPC signals controlling the intersection. Charts now streaming.', 'success');
        } catch {
            showToast('Activation Failed', 'Could not activate MPC. Is the backend running?', 'error');
        }
    }, [mode, showToast]);

    const handleStop = useCallback(async () => {
        try {
            await fetch(`${BASE_URL}/simulation/stop`, { method: 'POST' });
            await fetch(`${BASE_URL}/optimizer/unload`, { method: 'POST' });
        } catch { }
        setMode('idle');
        showToast('Stopped', 'Simulation stopped. Charts preserved.', 'info');
    }, [showToast]);

    // ── Derived ───────────────────────────────────────────────────────────────
    const recordPct = Math.round((recordStep / recordTarget) * 100);

    const baselineLabel = baselineMeta
        ? `${baselineMeta.scenario ?? '?'} · ${baselineMeta.flow_rate != null ? baselineMeta.flow_rate + ' veh/hr' : 'default flow'}`
        : null;

    return (
        <div className="h-full flex flex-col">

            {/* ── Record dialog ── */}
            {showRecordDialog && (
                <RecordDialog
                    initialScenario={currentScenario}
                    scenarios={availableScenarios.length > 0 ? availableScenarios : [currentScenario]}
                    onConfirm={handleRecordConfirm}
                    onCancel={() => setShowRecordDialog(false)}
                />
            )}

            {/* ── Header ── */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2 flex-wrap">
                        MPC Controller
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${isConnected
                            ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10'
                            : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
                            {isConnected ? 'Online' : 'Offline'}
                        </span>
                        {mode === 'mpc_active' && (
                            <span className="text-xs px-2 py-0.5 rounded-full border border-indigo-500/50 text-indigo-400 bg-indigo-500/10 animate-pulse">MPC Live</span>
                        )}
                    </h1>
                    <p className="text-slate-400 text-sm mt-0.5 flex items-center gap-2 flex-wrap">
                        Model Predictive Control — Traffic Signal Optimization
                        {baselineLabel && (
                            <span className="text-slate-500 text-xs border border-slate-700 rounded px-2 py-0.5">
                                Baseline: {baselineLabel}
                            </span>
                        )}
                    </p>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                    {/* Record Baseline */}
                    <button
                        onClick={() => mode === 'idle' && setShowRecordDialog(true)}
                        disabled={mode !== 'idle'}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all border
                            ${mode === 'recording'
                                ? 'bg-amber-500/10 border-amber-500/50 text-amber-300 cursor-not-allowed'
                                : mode === 'idle'
                                    ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-white cursor-pointer'
                                    : 'bg-slate-900 border-slate-800 text-slate-600 cursor-not-allowed'}`}
                    >
                        {mode === 'recording' ? <Loader2 size={16} className="animate-spin" /> : <BookMarked size={16} />}
                        {mode === 'recording' ? `Recording… ${recordStep}/${recordTarget}` : 'Record Baseline'}
                    </button>

                    {/* Activate MPC */}
                    <button
                        onClick={handleActivateMPC}
                        disabled={mode === 'recording'}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg
                            ${mode === 'mpc_active'
                                ? 'bg-indigo-500 text-white ring-2 ring-indigo-400 ring-offset-2 ring-offset-[#0B1120]'
                                : mode === 'recording'
                                    ? 'bg-slate-900 border border-slate-800 text-slate-600 cursor-not-allowed'
                                    : 'bg-indigo-600 text-white hover:bg-indigo-500'}`}
                    >
                        <Activity size={16} fill={mode === 'mpc_active' ? 'currentColor' : 'none'} />
                        {mode === 'mpc_active' ? 'MPC Active' : 'Activate MPC'}
                    </button>

                    {/* Stop */}
                    <button
                        onClick={handleStop}
                        disabled={mode === 'idle'}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-colors
                            ${mode === 'idle'
                                ? 'bg-slate-900 border border-slate-800 text-slate-600 cursor-not-allowed'
                                : 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20'}`}
                    >
                        <Square size={16} fill={mode !== 'idle' ? 'currentColor' : 'none'} />
                        Stop
                    </button>
                </div>
            </div>

            {/* ── Recording progress bar ── */}
            {mode === 'recording' && (
                <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-amber-300 text-sm font-semibold">Recording Baseline with Default Signals</span>
                        <span className="text-amber-400 text-xs tabular-nums">{recordStep} / {recordTarget} steps ({recordPct}%)</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div className="bg-amber-400 h-2 rounded-full transition-all duration-300" style={{ width: `${recordPct}%` }} />
                    </div>
                    <p className="text-slate-500 text-xs mt-2">The simulation will stop automatically when done.</p>
                </div>
            )}

            {/* ── Tabs ── */}
            <div className="flex border-b border-slate-800 mb-6">
                {[
                    { id: 'monitor', label: 'Real-time Monitor', icon: Activity },
                    { id: 'config', label: 'Controller Config', icon: Settings },
                ].map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveSubTab(tab.id)}
                        className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors
                            ${activeSubTab === tab.id ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
                    >
                        <tab.icon size={16} /> {tab.label}
                    </button>
                ))}
            </div>

            {/* ── Tab content ── */}
            <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
                {activeSubTab === 'monitor' && (
                    <MpcMonitorTab mode={mode} status={status} dataHistory={mpcHistory} hasBaseline={!!baselineData} />
                )}
                {activeSubTab === 'config' && <MpcConfigTab />}
            </div>

            {/* ── Toast ── */}
            {toast && (
                <div className="fixed bottom-6 right-6 z-50">
                    <div className={`flex items-start gap-4 px-6 py-4 rounded-xl shadow-2xl border backdrop-blur-md max-w-sm
                        ${toast.type === 'success' ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-100'
                            : toast.type === 'error' ? 'bg-rose-950/90 border-rose-500/50 text-rose-100'
                                : 'bg-slate-900/90 border-slate-700 text-slate-200'}`}>
                        <div className="mt-0.5 shrink-0">
                            {toast.type === 'success' ? <Activity className="text-emerald-400" size={20} />
                                : toast.type === 'error' ? <Square className="text-rose-400" size={20} />
                                    : <Settings className="text-slate-400" size={20} />}
                        </div>
                        <div>
                            <h4 className={`font-semibold text-sm mb-1 ${toast.type === 'success' ? 'text-emerald-300' : toast.type === 'error' ? 'text-rose-300' : 'text-slate-300'}`}>
                                {toast.title}
                            </h4>
                            <p className="text-xs opacity-80 leading-relaxed">{toast.message}</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
