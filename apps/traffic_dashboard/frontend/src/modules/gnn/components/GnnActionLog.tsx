import { useEffect, useState, useRef } from 'react';
import { Terminal } from 'lucide-react';

interface GnnActionLogProps {
    socketData: any;
}

interface LogEntry {
    id: string;
    text: string;
    timestamp: Date;
}

export default function GnnActionLog({ socketData }: GnnActionLogProps) {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const prevIntersectionsRef = useRef<Record<string, any>>({});
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!socketData?.currentMetrics?.intersections) return;

        const currentIntersections = socketData.currentMetrics.intersections;
        const prevIntersections = prevIntersectionsRef.current;
        const currentStep = socketData.currentMetrics.step || 0;

        const newLogs: LogEntry[] = [];

        // Compare current with prev to find phase changes
        Object.keys(currentIntersections).forEach(tlsId => {
            const currentPhase = currentIntersections[tlsId].phase_index;
            const prevPhase = prevIntersections[tlsId]?.phase_index;

            // Log if a phase has transitioned (and it's not the initial mounting frame)
            if (prevPhase !== undefined && currentPhase !== prevPhase) {
                newLogs.push({
                    id: `${tlsId}-${currentStep}-${currentPhase}-${Date.now()}`,
                    text: `[Step ${currentStep}] AGENT_${tlsId}: Executed Phase Switch -> Phase ${currentPhase}`,
                    timestamp: new Date()
                });
            }
        });

        if (newLogs.length > 0) {
            setLogs(prev => {
                const combined = [...prev, ...newLogs];
                // Keep only the last 50 logs to prevent memory leaks
                return combined.length > 50 ? combined.slice(combined.length - 50) : combined;
            });
        }

        // Update ref for next comparison frame
        prevIntersectionsRef.current = currentIntersections;

    }, [socketData?.currentMetrics?.intersections]);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (containerRef.current) {
            containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
    }, [logs]);

    return (
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden flex flex-col h-64 shadow-inner">
            <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex items-center gap-2">
                <Terminal size={14} className="text-emerald-500" />
                <span className="text-xs font-mono text-slate-400 font-semibold tracking-wider">GNN_ACTION_TERMINAL</span>
                <span className="ml-auto flex gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-700"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-700"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-slate-700"></span>
                </span>
            </div>

            <div
                ref={containerRef}
                className="flex-1 p-4 overflow-y-auto font-mono text-xs text-slate-300 space-y-1.5 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent"
            >
                {logs.length === 0 ? (
                    <div className="text-slate-600 italic">Waiting for agent actions...</div>
                ) : (
                    logs.map(log => (
                        <div key={log.id} className="flex gap-3 hover:bg-slate-800/50 px-1 -mx-1 rounded">
                            <span className="text-slate-500 shrink-0">
                                {log.timestamp.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </span>
                            <span className="text-emerald-400">
                                {log.text}
                            </span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
