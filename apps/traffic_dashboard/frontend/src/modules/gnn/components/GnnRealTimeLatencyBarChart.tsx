import React, { useMemo } from 'react';
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid
} from 'recharts';

interface BarChartProps {
    socketData: any;
}

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-slate-900/95 border border-slate-700 p-3 rounded-lg shadow-xl text-xs font-mono">
                <p className="text-slate-400 mb-2 border-b border-slate-700 pb-1">Node: {label}</p>
                {payload.map((entry: any) => (
                    <div key={entry.dataKey} className="flex justify-between gap-4">
                        <span style={{ color: entry.color }}>Latency:</span>
                        <span className="font-bold text-slate-200">{Number(entry.value).toFixed(2)} ms</span>
                    </div>
                ))}
            </div>
        );
    }
    return null;
};

const GnnRealTimeLatencyBarChart: React.FC<BarChartProps> = ({ socketData }) => {
    const chartData = useMemo(() => {
        const latencies = socketData?.currentMetrics?.gnn_telemetry?.perNodeLatencyMs || {};
        return Object.entries(latencies)
            .map(([nodeId, latency]) => ({
                nodeID: nodeId,
                latency: latency
            }))
            .sort((a, b) => a.nodeID.localeCompare(b.nodeID)); // Keep stable for eye tracking
    }, [socketData?.currentMetrics]);

    return (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 flex flex-col h-full shadow-lg animate-in fade-in duration-300">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Instantaneous Distributed Agent Latency (ms)</h3>

            <div className="flex-grow w-full h-64">
                {chartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
                            <defs>
                                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#3b82f6" />
                                    <stop offset="100%" stopColor="#10b981" />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} vertical={false} />
                            <XAxis
                                dataKey="nodeID"
                                stroke="#94a3b8"
                                tickLine={false}
                                axisLine={false}
                                tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#94a3b8' }}
                                interval={0} // Force all labels to show
                                angle={-90} // Rotate -90 degrees
                                textAnchor="end" // Align correctly after rotation
                                height={70} // Give enough room for the labels
                            />
                            <YAxis
                                stroke="#94a3b8"
                                fontSize={12}
                                tickLine={false}
                                axisLine={false}
                                width={50}
                            />
                            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#334155', opacity: 0.4 }} />
                            <Bar
                                dataKey="latency"
                                fill="url(#barGradient)"
                                barSize={12} // Fix the width of the bars
                                minPointSize={2} // Ensure very low latency is still a dot
                                isAnimationActive={false} // Disable animation for pure real-time performance
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

export default GnnRealTimeLatencyBarChart;
