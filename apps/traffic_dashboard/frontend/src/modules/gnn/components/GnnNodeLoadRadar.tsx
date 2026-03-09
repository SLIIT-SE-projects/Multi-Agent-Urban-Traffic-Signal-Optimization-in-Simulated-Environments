import { ResponsiveRadialBar } from '@nivo/radial-bar';
import { useNodeLoadMapper } from '../hooks/useNodeLoadMapper';

interface GnnNodeLoadRadarProps {
    socketData: any;
}

export default function GnnNodeLoadRadar({ socketData }: GnnNodeLoadRadarProps) {
    const { data, totalLoad } = useNodeLoadMapper(socketData.currentMetrics);

    // Dynamic color mapping: Green (Low) -> Amber (Medium) -> Red (High)
    const getColor = (bar: any) => {
        const val = bar.value;
        if (val < 5) return '#10b981'; // emerald-500
        if (val < 15) return '#f59e0b'; // amber-500
        return '#f43f5e'; // rose-500
    };

    if (!data || data.length === 0) {
        return <div className="flex items-center justify-center h-full text-slate-500 italic">Waiting for node metrics...</div>;
    }

    return (
        <div className="relative w-full h-full bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
            {/* Center metric showing global load */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-10">
                <span className="text-4xl font-black text-white tracking-tighter drop-shadow-md">
                    {totalLoad}
                </span>
                <span className="text-xs text-slate-400 font-semibold tracking-widest uppercase mt-1">
                    System Load
                </span>
            </div>

            <ResponsiveRadialBar
                data={data}
                valueFormat=">-.2f"
                padding={0.1}
                innerRadius={0.3}
                margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                colors={getColor}
                enableRadialGrid={false}
                enableCircularGrid={false}
                radialAxisStart={null}
                circularAxisOuter={null}
                labelsSkipAngle={360} // Disable all labels
                isInteractive={true}
                animate={true}
                motionConfig="gentle"
                tooltip={({ bar }) => (
                    <div className="bg-slate-900 border border-slate-700 px-3 py-2 rounded shadow-xl text-sm font-mono flex items-center gap-3">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: bar.color }} />
                        <span className="text-slate-300">Node: <span className="text-white font-bold">{bar.groupId}</span></span>
                        <span className="text-slate-500">|</span>
                        <span className="text-indigo-400">Load: {bar.value} veh</span>
                    </div>
                )}
            />
        </div>
    );
}
