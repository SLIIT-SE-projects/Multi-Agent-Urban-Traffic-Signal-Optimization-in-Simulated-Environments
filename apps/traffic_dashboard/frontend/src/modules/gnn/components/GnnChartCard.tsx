import React, { useMemo } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Line
} from 'recharts';

interface ChartCardProps {
    title: string;
    data: any[];
    baselineData?: any[];
    dataKey: string;
    color: string;
    fillId: string;
    height?: string;
}

const GnnChartCard: React.FC<ChartCardProps> = ({ title, data, baselineData = [], dataKey, color, fillId, height = "h-80" }) => {

    // Merge data to ensure both lines show up on the same X-Axis (step)
    const mergedData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Create a map of baseline data for quick lookup by step
        const baselineMap = new Map();
        baselineData.forEach(item => {
            if (item && item.step !== undefined) {
                baselineMap.set(item.step, item);
            }
        });

        // Map live data and attach corresponding baseline data
        return data.map(liveItem => {
            const currentStep = liveItem.step;
            const baselineItem = baselineMap.get(currentStep);

            return {
                step: currentStep,
                [dataKey]: liveItem[dataKey],
                [`baseline_${dataKey}`]: baselineItem ? baselineItem[dataKey] : null
            };
        });
    }, [data, baselineData, dataKey]);

    return (
        <div className={`bg-slate-900 border border-slate-800 rounded-xl p-5 ${height} flex flex-col`}>
            <h3 className="text-slate-200 font-semibold mb-4 flex items-center gap-2 text-sm">
                <div className={`w-1.5 h-4 rounded-full ${color.replace('text', 'bg')}`} />
                {title}
                {baselineData.length > 0 && <span className="text-xs text-slate-500 ml-auto flex items-center gap-1">
                    <span className="w-2 h-0.5 bg-slate-500"></span> Baseline
                </span>}
            </h3>
            <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={mergedData}>
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
                        />
                        {/* Baseline Line (Dashed) */}
                        <Line
                            type="monotone"
                            dataKey={`baseline_${dataKey}`}
                            stroke="#64748b"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                            isAnimationActive={false}
                        />
                        {/* Live Data Area */}
                        <Area
                            type="monotone"
                            dataKey={dataKey}
                            stroke="currentColor"
                            strokeWidth={2}
                            fill={`url(#${fillId})`}
                            className={color}
                            isAnimationActive={false}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default GnnChartCard;
