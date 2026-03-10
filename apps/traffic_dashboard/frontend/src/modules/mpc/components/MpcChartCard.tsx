import React from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

interface ChartCardProps {
    title: string;
    data: any[];
    dataKey: string;
    color: string;
    fillId: string;
    height?: string;
    baselineKey?: string;
}

const MpcChartCard: React.FC<ChartCardProps> = ({ title, data, dataKey, color, fillId, height = "h-80", baselineKey }) => (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-5 ${height} flex flex-col`}>
        <div className="flex items-center justify-between mb-4">
            <h3 className="text-slate-200 font-semibold flex items-center gap-2 text-sm">
                <div className={`w-1.5 h-4 rounded-full ${color.replace('text', 'bg')}`} />
                {title}
            </h3>
            {baselineKey && (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="w-2 h-0.5 bg-slate-500 border-t border-slate-500 border-dashed" style={{ borderTopWidth: '2px' }}></span>
                    Baseline
                </div>
            )}
        </div>
        <div className="flex-1 w-full min-h-0">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                    <defs>
                        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="currentColor" stopOpacity={0.3} className={color} />
                            <stop offset="95%" stopColor="currentColor" stopOpacity={0} className={color} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="step" hide />
                    <YAxis hide domain={['auto', 'auto']} />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                        itemStyle={{ color: '#e2e8f0' }}
                        labelStyle={{ color: '#94a3b8' }}
                        formatter={(value: any, name: any) => [
                            name === baselineKey ? `Baseline: ${Number(value).toFixed(1)}` : `Current: ${Number(value).toFixed(1)}`
                        ]}
                    />
                    <Area
                        type="monotone"
                        dataKey={dataKey}
                        stroke="currentColor"
                        strokeWidth={2}
                        fill={`url(#${fillId})`}
                        className={color}
                        isAnimationActive={false}
                    />
                    {baselineKey && (
                        <Area
                            type="monotone"
                            dataKey={baselineKey}
                            stroke="#64748b"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            fill="none"
                            isAnimationActive={false}
                        />
                    )}
                </AreaChart>
            </ResponsiveContainer>
        </div>
    </div>
);

export default MpcChartCard;
