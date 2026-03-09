import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Pause, Play } from 'lucide-react';

interface GnnActionLogProps {
    socketData: any;
}

interface SyncLog {
    id: string;
    timestamp: string;
    step: number;
    agentId: string;
    action: string;
    rawPayload: string;
    byteSize: number;
}

export default function GnnActionLog({ socketData }: GnnActionLogProps) {
    const [logs, setLogs] = useState<SyncLog[]>([]);
    const [isPaused, setIsPaused] = useState(false);
    const prevIntersectionsRef = useRef<Record<string, any>>({});
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const currentIntersections = socketData?.currentMetrics?.intersections;
        if (!currentIntersections) return;

        const prevIntersections = prevIntersectionsRef.current;
        const currentStep = socketData?.currentMetrics?.step || 0;
        const perNodeUncertainty = socketData?.currentMetrics?.gnn_telemetry?.perNodeUncertainty || {};

        const newLogs: SyncLog[] = [];

        // Compare current with prev to find phase changes
        Object.keys(currentIntersections).forEach(tlsId => {
            const currentPhase = currentIntersections[tlsId].phase_index;
            const prevPhase = prevIntersections[tlsId]?.phase_index;

            // Log if a phase has transitioned (and it's not the initial mounting frame)
            if (prevPhase !== undefined && currentPhase !== prevPhase) {
                const payloadObj = {
                    state: "UPDATE",
                    target_phase: currentPhase,
                    confidence: perNodeUncertainty[tlsId] !== undefined ? perNodeUncertainty[tlsId] : 1.0
                };

                const rawStr = JSON.stringify(payloadObj);

                newLogs.push({
                    id: `${tlsId}-${currentStep}-${currentPhase}-${Date.now()}`,
                    timestamp: new Date().toISOString(),
                    step: currentStep,
                    agentId: tlsId,
                    action: "PHASE_TRANSITION",
                    rawPayload: rawStr,
                    byteSize: rawStr.length + 64
                });
            }
        });

        if (newLogs.length > 0 && !isPaused) {
            setLogs(prev => {
                const combined = [...prev, ...newLogs];
                // Keep only the last 50 logs to prevent memory leaks
                return combined.length > 50 ? combined.slice(combined.length - 50) : combined;
            });
        }

        // Update ref for next comparison frame regardless of pause 
        // to prevent backlog dumping when unpaused
        prevIntersectionsRef.current = currentIntersections;

    }, [socketData?.currentMetrics, isPaused]);

    // Auto-scroll to bottom when new logs arrive (if not paused)
    useEffect(() => {
        if (containerRef.current && !isPaused) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [logs, isPaused]);

    return (
        <div className="bg-black border border-slate-800 rounded-xl overflow-hidden flex flex-col h-64 shadow-inner font-mono text-xs">
            <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex items-center gap-2 sticky top-0 z-10">
                <Terminal size={14} className="text-emerald-500 shrink-0" />
                <span className="text-xs font-mono text-slate-300 font-semibold tracking-wider flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                    LIVE: MULTI-AGENT WEBSOCKET SYNC STREAM
                </span>
                <button
                    onClick={() => setIsPaused(!isPaused)}
                    className={`ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] uppercase font-bold transition-colors ${isPaused ? 'bg-amber-500/20 text-amber-500 hover:bg-amber-500/30' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}
                >
                    {isPaused ? <Play size={10} /> : <Pause size={10} />}
                    {isPaused ? 'RESUME' : 'PAUSE'}
                </button>
            </div>

            <div
                ref={containerRef}
                className="flex-1 p-4 overflow-y-auto space-y-3 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent"
            >
                {logs.length === 0 ? (
                    <div className="text-slate-600 italic">Waiting for multi-agent synchronization events...</div>
                ) : (
                    logs.map(log => (
                        <div key={log.id} className="flex flex-col hover:bg-slate-900/50 p-1 -mx-1 rounded">
                            <div className="flex flex-wrap gap-2 text-slate-300 mb-1">
                                <span className="text-slate-500">[{log.timestamp}]</span>
                                <span className="text-blue-400">[STEP {log.step}]</span>
                                <span className="text-emerald-500">[SYNC: {log.byteSize}B]</span>
                                <span className="text-slate-300">-&gt; AGENT: {log.agentId}</span>
                            </div>
                            <div className="text-slate-400 pl-4 break-all">
                                {log.rawPayload}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
