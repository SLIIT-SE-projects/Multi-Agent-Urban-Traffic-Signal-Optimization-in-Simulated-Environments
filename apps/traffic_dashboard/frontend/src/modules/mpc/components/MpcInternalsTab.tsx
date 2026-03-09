import React, { useEffect, useState } from 'react';
import { Cpu, Brain, Clock, Layers, Zap, AlertCircle, RefreshCw } from 'lucide-react';

const BASE_URL = '/api';

interface IntersectionDecision {
    id: string;
    max_queue: number;
    green_times: number[];
    lstm_mode: string;
}

interface InternalsData {
    status: string;
    lstm_mode: string;
    n_lanes: number;
    n_intersections: number;
    intersections: IntersectionDecision[];
    config: {
        cycle_time: number;
        min_green: number;
        max_green: number;
        horizon: number;
        control_horizon: number;
        w_queue: number;
        w_switch: number;
    };
    message?: string;
}

const PHASE_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444'];

const MpcInternalsTab: React.FC = () => {
    const [data, setData] = useState<InternalsData | null>(null);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState<string>('');

    const fetchData = async () => {
        try {
            const res = await fetch(`${BASE_URL}/optimizer/mpc/internals`);
            const json: InternalsData = await res.json();
            setData(json);
            setLastUpdated(new Date().toLocaleTimeString());
        } catch {
            setData(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const id = setInterval(fetchData, 2000);
        return () => clearInterval(id);
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-24">
                <RefreshCw size={20} className="text-slate-500 animate-spin mr-2" />
                <span className="text-slate-500 text-sm">Loading optimizer state…</span>
            </div>
        );
    }

    if (!data || data.status !== 'active') {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
                    <Cpu size={28} className="text-slate-600" />
                </div>
                <h3 className="text-slate-300 text-base font-semibold mb-2">MPC Not Active</h3>
                <p className="text-slate-500 text-sm max-w-xs">Activate MPC to see optimizer internals — green-time decisions, LSTM status, and controller parameters.</p>
            </div>
        );
    }

    const maxPhases = Math.max(...(data.intersections?.map(i => i.green_times.length) ?? [4]));
    const lstmActive = data.lstm_mode === 'neural_net';

    return (
        <div className="space-y-6 animate-in fade-in duration-500">

            {/* ── Header status bar ── */}
            <div className="flex flex-wrap items-center gap-3">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold
                    ${lstmActive ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'}`}>
                    <Brain size={13} />
                    LSTM: {lstmActive ? 'Neural Network' : 'Heuristic Fallback'}
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold">
                    <Layers size={13} />
                    {data.n_intersections} Intersections · {data.n_lanes} Lanes
                </div>
                <span className="text-slate-600 text-xs ml-auto">Updated: {lastUpdated}</span>
            </div>

            {/* ── Config Cards ── */}
            {data.config && (
                <div>
                    <h3 className="text-slate-300 text-sm font-semibold mb-3">Controller Configuration</h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                        {[
                            { label: 'Cycle Time', value: `${data.config.cycle_time}s`, icon: <Clock size={14} /> },
                            { label: 'Min Green', value: `${data.config.min_green}s`, icon: <Clock size={14} /> },
                            { label: 'Max Green', value: `${data.config.max_green}s`, icon: <Clock size={14} /> },
                            { label: 'Pred Horizon', value: `${data.config.horizon} steps`, icon: <Layers size={14} /> },
                            { label: 'Control Horizon', value: `${data.config.control_horizon} steps`, icon: <Layers size={14} /> },
                            { label: 'ω Queue', value: `${data.config.w_queue}`, icon: <Zap size={14} /> },
                            { label: 'ω Switch', value: `${data.config.w_switch}`, icon: <Zap size={14} /> },
                        ].map(c => (
                            <div key={c.label} className="bg-slate-900 border border-slate-800 rounded-xl p-3 flex flex-col gap-1">
                                <div className="flex items-center gap-1.5 text-slate-500 text-xs">{c.icon}{c.label}</div>
                                <p className="text-white text-sm font-bold">{c.value}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Per-Intersection Green Time Visual ── */}
            {data.intersections && data.intersections.length > 0 && (
                <div>
                    <h3 className="text-slate-300 text-sm font-semibold mb-3">Last Optimizer Decision — Green Time Allocation</h3>

                    {/* Phase colour legend */}
                    <div className="flex gap-4 mb-3 flex-wrap">
                        {Array.from({ length: maxPhases }, (_, i) => (
                            <span key={i} className="flex items-center gap-1.5 text-xs text-slate-400">
                                <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: PHASE_COLORS[i % PHASE_COLORS.length] }} />
                                Phase {i + 1}
                            </span>
                        ))}
                    </div>

                    {/* Bar chart per intersection */}
                    <div className="space-y-3">
                        {data.intersections.map((inter) => {
                            const total = inter.green_times.reduce((a, b) => a + b, 0) || 1;
                            return (
                                <div key={inter.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-3">
                                            <span className="text-slate-200 text-sm font-semibold">{inter.id}</span>
                                            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium
                                                ${inter.max_queue > 10 ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                                                    : inter.max_queue > 4 ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                                                        : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'}`}>
                                                Queue: {inter.max_queue} veh
                                            </span>
                                        </div>
                                        <div className="flex gap-2 text-xs text-slate-500">
                                            {inter.green_times.map((g, i) => (
                                                <span key={i} style={{ color: PHASE_COLORS[i % PHASE_COLORS.length] }} className="font-medium">
                                                    {g}s
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                    {/* Stacked bar */}
                                    <div className="flex rounded-full overflow-hidden h-4 gap-px bg-slate-800">
                                        {inter.green_times.map((g, i) => (
                                            <div
                                                key={i}
                                                title={`Phase ${i + 1}: ${g}s`}
                                                style={{
                                                    width: `${(g / total) * 100}%`,
                                                    backgroundColor: PHASE_COLORS[i % PHASE_COLORS.length],
                                                    opacity: 0.85,
                                                }}
                                            />
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* ── Decision Table ── */}
            {data.intersections && data.intersections.length > 0 && (
                <div>
                    <h3 className="text-slate-300 text-sm font-semibold mb-3">Decision Summary Table</h3>
                    <div className="overflow-x-auto rounded-xl border border-slate-800">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-slate-800/60 text-slate-400 text-xs uppercase tracking-wider">
                                    <th className="text-left px-4 py-3">Intersection</th>
                                    <th className="text-left px-4 py-3">Max Queue</th>
                                    {Array.from({ length: maxPhases }, (_, i) => (
                                        <th key={i} className="text-left px-4 py-3" style={{ color: PHASE_COLORS[i % PHASE_COLORS.length] }}>
                                            Phase {i + 1}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {data.intersections.map((inter, idx) => (
                                    <tr key={inter.id} className={`border-t border-slate-800 ${idx % 2 === 0 ? 'bg-slate-900' : 'bg-slate-900/50'}`}>
                                        <td className="px-4 py-3 font-semibold text-slate-200">{inter.id}</td>
                                        <td className="px-4 py-3">
                                            <span className={`font-medium ${inter.max_queue > 10 ? 'text-rose-400' : inter.max_queue > 4 ? 'text-amber-400' : 'text-emerald-400'}`}>
                                                {inter.max_queue} veh
                                            </span>
                                        </td>
                                        {Array.from({ length: maxPhases }, (_, i) => (
                                            <td key={i} className="px-4 py-3 text-slate-300 font-mono text-xs">
                                                {inter.green_times[i] != null ? `${inter.green_times[i]}s` : '—'}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {(!data.intersections || data.intersections.length === 0) && (
                <div className="flex items-center gap-2 text-amber-400 text-sm bg-amber-500/5 border border-amber-500/20 rounded-lg px-4 py-3">
                    <AlertCircle size={16} />
                    Waiting for first optimizer decision cycle…
                </div>
            )}
        </div>
    );
};

export default MpcInternalsTab;
