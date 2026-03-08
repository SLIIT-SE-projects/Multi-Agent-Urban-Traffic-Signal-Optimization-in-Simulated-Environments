import React, { useMemo } from 'react';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
    ReferenceLine
} from 'recharts';

interface RealTimeUncProps {
    socketData: any;
}

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-lg shadow-xl text-xs font-mono">
                <p className="text-slate-400 mb-2 border-b border-slate-700 pb-1">Node: {label}</p>
                {payload.map((entry: any) => (
                    <div key={entry.dataKey} className="flex justify-between gap-4">
                        <span style={{ color: entry.color }}>Score:</span>
                        <span className="font-bold text-slate-200">{Number(entry.value).toFixed(4)}</span>
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

const GnnRealTimeUncertaintyChart: React.FC<RealTimeUncProps> = ({ socketData }) => {
    const { chartData, globalScore } = useMemo(() => {
        const telemetry = socketData?.currentMetrics?.gnn_telemetry;
        const uncertainties = telemetry?.perNodeUncertainty || {};
        const global = telemetry?.uncertaintyScore || 0;

        const data = Object.entries(uncertainties)
            .map(([nodeId, score]) => ({
                nodeID: nodeId,
                score: score
            }))
            .sort((a, b) => a.nodeID.localeCompare(b.nodeID));

        return { chartData: data, globalScore: global };
    }, [socketData?.currentMetrics]);

    console.log("DEBUG Frontend Chart Data Length:", chartData.length);

    return (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex flex-col h-full shadow-lg animate-in fade-in duration-300">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Instantaneous Agent Uncertainty</h3>

            <div className="flex-grow w-full h-64">
                {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} margin={{ top: 20, right: 10, left: -20, bottom: 40 }}>
                            <defs>
                                <linearGradient id="uncGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#f59e0b" />
                                    <stop offset="100%" stopColor="#ef4444" />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} vertical={false} />
                            <XAxis
                                dataKey="nodeID"
                                stroke="#94a3b8"
                                tickLine={false}
                                axisLine={false}
                                tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#94a3b8' }}
                                interval={0}
                                angle={-90}
                                textAnchor="end"
                                height={70}
                            />
                            <YAxis
                                stroke="#94a3b8"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                                width={50}
                            />
                            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.4 }} />
                            <ReferenceLine
                                y={globalScore}
                                stroke="#10b981"
                                strokeDasharray="3 3"
                                label={{ position: 'top', value: 'Global Avg', fill: '#10b981', fontSize: 10 }}
                            />
                            <Bar
                                dataKey="score"
                                fill="url(#uncGradient)"
                                barSize={12}
                                isAnimationActive={false}
                                radius={[2, 2, 0, 0]}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="flex items-center justify-center h-full text-slate-500 text-sm">Waiting for telemetry...</div>
                )}
            </div>
        </div>
    );
};

export default GnnRealTimeUncertaintyChart;
