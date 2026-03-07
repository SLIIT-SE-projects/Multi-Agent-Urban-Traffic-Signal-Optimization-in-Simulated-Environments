import { X, Activity, Clock, Car } from 'lucide-react';

// Add 'red-yellow' to the type definition
interface LightState {
    color: 'green' | 'yellow' | 'red' | 'red-yellow';
    time: number;
}

interface TrafficLightProps {
    phaseIndex: number;
    timeToSwitch: number;
}

const TrafficLightVisualizer: React.FC<TrafficLightProps> = ({ phaseIndex, timeToSwitch }) => {
    const pIdx = (phaseIndex !== undefined) ? (phaseIndex % 4) : 0;
    const time = Math.max(0, Math.round(timeToSwitch));

    let nsState: LightState = { color: 'red', time: 0 };
    let ewState: LightState = { color: 'red', time: 0 };

    // --- ADVANCED REAL-WORLD PHASE MAPPING ---
    switch (pIdx) {
        case 0: // NS is Green (Go), EW is solid Red
            nsState = { color: 'green', time: time };
            ewState = { color: 'red', time: 0 };
            break;
        case 1: // NS is Yellow (Stopping), EW is Red+Yellow (Preparing to go)
            nsState = { color: 'yellow', time: time };
            ewState = { color: 'red-yellow', time: time };
            break;
        case 2: // NS is solid Red, EW is Green (Go)
            nsState = { color: 'red', time: 0 };
            ewState = { color: 'green', time: time };
            break;
        case 3: // NS is Red+Yellow (Preparing to go), EW is Yellow (Stopping)
            nsState = { color: 'red-yellow', time: time };
            ewState = { color: 'yellow', time: time };
            break;
        default:
            nsState = { color: 'red', time: 0 };
            ewState = { color: 'red', time: 0 };
    }

    const renderLightStack = (label: string, state: LightState) => {
        // Dynamic styling that supports multiple lights being active at once
        const getCircleClass = (lightColor: 'red' | 'yellow' | 'green') => {
            let isActive = false;
            if (lightColor === 'red') isActive = state.color === 'red' || state.color === 'red-yellow';
            if (lightColor === 'yellow') isActive = state.color === 'yellow' || state.color === 'red-yellow';
            if (lightColor === 'green') isActive = state.color === 'green';

            const base = "w-12 h-12 rounded-full border-2 border-slate-950 flex items-center justify-center font-mono font-bold text-lg transition-all duration-300 ";
            const inactive = "bg-slate-800 border-slate-800 text-slate-600";

            switch (lightColor) {
                case 'red':
                    return base + (isActive ? 'bg-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.8)] text-slate-950' : inactive);
                case 'yellow':
                    return base + (isActive ? 'bg-amber-400 shadow-[0_0_15px_rgba(251,191,36,0.8)] text-slate-950' : inactive);
                case 'green':
                    return base + (isActive ? 'bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.8)] text-slate-950' : inactive);
            }
        };

        return (
            <div className="flex flex-col items-center gap-1.5 p-2 bg-slate-950/80 border-2 border-slate-800 rounded-3xl w-20 shadow-inner">
                <div className="text-sm font-bold text-slate-300 mb-1">{label}</div>

                {/* RED Circle */}
                <div className={getCircleClass('red')}>
                    {/* Typically countdown is shown in yellow/green, but can be added here if desired */}
                </div>

                {/* YELLOW Circle */}
                <div className={getCircleClass('yellow')}>
                    {(state.color === 'yellow' || state.color === 'red-yellow') ? state.time : ''}
                </div>

                {/* GREEN Circle */}
                <div className={getCircleClass('green')}>
                    {state.color === 'green' ? state.time : ''}
                </div>
            </div>
        );
    };

    return (
        <div className="flex items-start justify-center gap-4 my-6">
            {renderLightStack("N-S", nsState)}
            {renderLightStack("E-W", ewState)}
        </div>
    );
};

interface NodeInspectorProps {
    nodeId: string;
    socketData: any;
    onClose: () => void;
}

export default function NodeInspector({ nodeId, socketData, onClose }: NodeInspectorProps) {
    const nodeData = socketData?.currentMetrics?.intersections?.[nodeId];
    const lanes = socketData?.currentMetrics?.lanes || {};

    if (!nodeData) return null;

    // Find lanes connecting to this node
    const connectedLanes = Object.entries(lanes)
        .filter(([laneId]) => laneId.includes(nodeId) || laneId.includes(nodeId.split('_')[0]))
        .sort((a: any, b: any) => (b[1].queue_length || 0) - (a[1].queue_length || 0))
        .slice(0, 5); // Take top 5 congested

    return (
        <div className="fixed top-0 right-0 h-full w-80 bg-slate-900/95 backdrop-blur-md border-l border-slate-800 p-6 z-50 overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-300">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Activity className="text-indigo-400" size={24} />
                    Agent {nodeId}
                </h2>
                <button
                    onClick={onClose}
                    className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                >
                    <X size={20} />
                </button>
            </div>

            <div className="space-y-6">
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                        <Clock size={16} className="text-amber-400" />
                        Phase Control State
                    </h3>
                    <TrafficLightVisualizer
                        phaseIndex={nodeData.phase_index}
                        timeToSwitch={nodeData.time_to_switch}
                    />
                </div>

                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50">
                    <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
                        <Car size={16} className="text-blue-400" />
                        Local Lane Congestion (Top 5)
                    </h3>

                    {connectedLanes.length === 0 ? (
                        <p className="text-sm text-slate-500 italic">No incoming lanes detected.</p>
                    ) : (
                        <div className="space-y-4">
                            {connectedLanes.map(([laneId, lData]: [string, any]) => {
                                const queue = lData.queue_length || 0;
                                const maxQueue = 30; // arbitrary max for percentage 
                                const pct = Math.min(100, (queue / maxQueue) * 100);
                                const isHeavy = queue > 10;

                                return (
                                    <div key={laneId} className="space-y-1">
                                        <div className="flex justify-between text-xs">
                                            <span className="text-slate-300 truncate max-w-[150px]" title={laneId}>{laneId}</span>
                                            <span className={isHeavy ? "text-rose-400 font-bold" : "text-slate-400"}>{queue} veh</span>
                                        </div>
                                        <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full ${isHeavy ? 'bg-rose-500' : queue > 3 ? 'bg-amber-500' : 'bg-blue-500'}`}
                                                style={{ width: `${Math.max(2, pct)}%` }}
                                            />
                                        </div>
                                        <div className="text-[10px] text-slate-500 flex justify-between">
                                            <span>Wait: {lData.waiting_time?.toFixed(1) || 0}s</span>
                                            <span>Speed: {lData.avg_speed?.toFixed(1) || 0}m/s</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
