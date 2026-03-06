import { X, Activity, Clock, Car } from 'lucide-react';

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
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <p className="text-xs text-slate-400 mb-1">Current Phase</p>
                            <p className="text-2xl font-bold text-white">{nodeData.phase_index}</p>
                        </div>
                        <div>
                            <p className="text-xs text-slate-400 mb-1">Time to Switch</p>
                            <p className="text-lg font-bold text-emerald-400">
                                {nodeData.time_to_switch > 0 ? `${nodeData.time_to_switch.toFixed(1)}s` : 'Switching...'}
                            </p>
                        </div>
                    </div>
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
