import React, { useMemo } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import {
    ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer,
} from 'recharts';

interface MpcAnalysisTabProps {
    dataHistory: any[];
    baselineMeta: any;
}

interface KpiCardProps {
    label: string;
    pct: number;
    higherIsBetter?: boolean;
    unit?: string;
    baseVal?: number;
    mpcVal?: number;
}

function KpiCard({ label, pct, higherIsBetter = false, baseVal, mpcVal }: KpiCardProps) {
    const improved = higherIsBetter ? pct > 0 : pct < 0;
    const Icon = improved ? TrendingUp : pct === 0 ? Minus : TrendingDown;
    const badgeColor = improved
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
        : 'bg-rose-500/10 text-rose-400 border-rose-500/30';
    const sign = pct >= 0 ? '+' : '';

    return (
        <div className={`bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col gap-3`}>
            <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">{label}</p>
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-bold w-fit ${badgeColor}`}>
                <Icon size={14} />
                {sign}{Math.abs(pct).toFixed(1)}%
            </div>
            {baseVal !== undefined && mpcVal !== undefined && (
                <div className="flex gap-4 text-xs text-slate-500">
                    <span>Baseline: <span className="text-slate-300">{baseVal.toFixed(1)}</span></span>
                    <span>MPC: <span className={improved ? 'text-emerald-400' : 'text-rose-400'}>{mpcVal.toFixed(1)}</span></span>
                </div>
            )}
        </div>
    );
}

function avg(arr: number[]) {
    if (!arr.length) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

const MpcAnalysisTab: React.FC<MpcAnalysisTabProps> = ({ dataHistory, baselineMeta }) => {
    // Build aligned dataset for charts
    const chartData = useMemo(() => {
        return dataHistory.map((pt) => ({
            step: pt.step,
            mpcWait: pt.waitingTime ?? 0,
            mpcQueue: pt.maxQueue ?? 0,
            mpcSpeed: pt.avgSpeed ?? 0,
            baseWait: pt.baseline_waitingTime ?? null,
            baseQueue: pt.baseline_maxQueue ?? null,
            baseSpeed: pt.baseline_avgSpeed ?? null,
        }));
    }, [dataHistory]);

    // KPI computation
    const kpis = useMemo(() => {
        const mpcWaits = dataHistory.map(p => p.waitingTime ?? 0);
        const mpcQueues = dataHistory.map(p => p.maxQueue ?? 0);
        const mpcSpeeds = dataHistory.map(p => p.avgSpeed ?? 0);
        const baseWaits = dataHistory.map(p => p.baseline_waitingTime).filter(v => v != null) as number[];
        const baseQueues = dataHistory.map(p => p.baseline_maxQueue).filter(v => v != null) as number[];
        const baseSpeeds = dataHistory.map(p => p.baseline_avgSpeed).filter(v => v != null) as number[];

        const safe = (b: number, m: number, hib: boolean) => {
            if (b === 0) return 0;
            return hib ? ((m - b) / b) * 100 : ((b - m) / b) * 100;
        };

        const avgMW = avg(mpcWaits), avgBW = avg(baseWaits);
        const avgMQ = avg(mpcQueues), avgBQ = avg(baseQueues);
        const avgMS = avg(mpcSpeeds), avgBS = avg(baseSpeeds);

        return {
            wait: { pct: safe(avgBW, avgMW, false), base: avgBW, mpc: avgMW },
            queue: { pct: safe(avgBQ, avgMQ, false), base: avgBQ, mpc: avgMQ },
            speed: { pct: safe(avgBS, avgMS, true), base: avgBS, mpc: avgMS },
        };
    }, [dataHistory]);

    const hasBaseline = dataHistory.some(p => p.baseline_waitingTime != null);

    if (!hasBaseline || dataHistory.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
                    <TrendingDown size={28} className="text-slate-600" />
                </div>
                <h3 className="text-slate-300 text-base font-semibold mb-2">No Comparison Data Yet</h3>
                <p className="text-slate-500 text-sm max-w-xs">
                    Record a Baseline first, then Activate MPC. Analysis will appear here once both datasets are available.
                </p>
            </div>
        );
    }

    const metaLabel = baselineMeta
        ? `${baselineMeta.scenario ?? 'grid3x3'} · ${baselineMeta.flow_rate != null ? baselineMeta.flow_rate + ' veh/hr' : 'default flow'}`
        : 'Baseline recorded';

    const chartProps = {
        margin: { top: 5, right: 20, left: 0, bottom: 0 },
    };
    const axisStyle = { fill: '#94a3b8', fontSize: 11 };
    const gridStyle = { strokeDasharray: '3 3', stroke: '#1e293b' };

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Baseline badge */}
            <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-2 w-fit">
                <span className="w-2 h-2 rounded-full bg-slate-500 inline-block" />
                Baseline: <span className="text-slate-200 font-medium ml-1">{metaLabel}</span>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <KpiCard label="Waiting Time" pct={kpis.wait.pct} baseVal={kpis.wait.base} mpcVal={kpis.wait.mpc} />
                <KpiCard label="Queue Length" pct={kpis.queue.pct} baseVal={kpis.queue.base} mpcVal={kpis.queue.mpc} />
                <KpiCard label="Network Speed" pct={kpis.speed.pct} higherIsBetter baseVal={kpis.speed.base} mpcVal={kpis.speed.mpc} />
            </div>

            {/* Legend */}
            <div className="flex items-center gap-6 text-xs text-slate-400 px-1">
                <span className="flex items-center gap-2">
                    <span className="inline-block w-8 h-0.5 bg-indigo-400 rounded" />MPC (Live)
                </span>
                <span className="flex items-center gap-2">
                    <span className="inline-block w-8 border-t-2 border-dashed border-slate-500" />Baseline (Fixed-Time)
                </span>
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Waiting Time */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <h4 className="text-slate-200 text-sm font-semibold mb-3">Total Waiting Time</h4>
                    <ResponsiveContainer width="100%" height={200}>
                        <ComposedChart data={chartData} {...chartProps}>
                            <CartesianGrid {...gridStyle} />
                            <XAxis dataKey="step" tick={axisStyle} />
                            <YAxis tick={axisStyle} />
                            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }} />
                            <Area type="monotone" dataKey="mpcWait" stroke="#6366f1" fill="#6366f120" strokeWidth={2} dot={false} name="MPC Wait (s)" />
                            <Line type="monotone" dataKey="baseWait" stroke="#64748b" strokeDasharray="5 3" strokeWidth={1.5} dot={false} name="Baseline Wait (s)" />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>

                {/* Queue */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                    <h4 className="text-slate-200 text-sm font-semibold mb-3">Max Queue Length</h4>
                    <ResponsiveContainer width="100%" height={200}>
                        <ComposedChart data={chartData} {...chartProps}>
                            <CartesianGrid {...gridStyle} />
                            <XAxis dataKey="step" tick={axisStyle} />
                            <YAxis tick={axisStyle} />
                            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }} />
                            <Area type="monotone" dataKey="mpcQueue" stroke="#a855f7" fill="#a855f720" strokeWidth={2} dot={false} name="MPC Queue (veh)" />
                            <Line type="monotone" dataKey="baseQueue" stroke="#64748b" strokeDasharray="5 3" strokeWidth={1.5} dot={false} name="Baseline Queue (veh)" />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>

                {/* Speed */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 lg:col-span-2">
                    <h4 className="text-slate-200 text-sm font-semibold mb-3">Avg Network Speed</h4>
                    <ResponsiveContainer width="100%" height={200}>
                        <ComposedChart data={chartData} {...chartProps}>
                            <CartesianGrid {...gridStyle} />
                            <XAxis dataKey="step" tick={axisStyle} />
                            <YAxis tick={axisStyle} unit=" m/s" />
                            <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }} />
                            <Area type="monotone" dataKey="mpcSpeed" stroke="#f59e0b" fill="#f59e0b18" strokeWidth={2} dot={false} name="MPC Speed (m/s)" />
                            <Line type="monotone" dataKey="baseSpeed" stroke="#64748b" strokeDasharray="5 3" strokeWidth={1.5} dot={false} name="Baseline Speed (m/s)" />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
};

export default MpcAnalysisTab;
