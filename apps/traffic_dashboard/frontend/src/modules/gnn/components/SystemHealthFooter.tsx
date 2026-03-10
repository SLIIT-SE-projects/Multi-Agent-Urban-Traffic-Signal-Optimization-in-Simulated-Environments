import { useEffect, useState } from 'react';

interface SystemHealthFooterProps {
    socketConnected: boolean;
}

const BACKEND_URL = 'http://localhost:5000';

export default function SystemHealthFooter({ socketConnected }: SystemHealthFooterProps) {
    const [apiConnected, setApiConnected] = useState(false);

    useEffect(() => {
        const checkHealth = async () => {
            try {
                const res = await fetch(`${BACKEND_URL}/api/health`, { method: 'GET' });
                if (res.ok) {
                    setApiConnected(true);
                } else {
                    setApiConnected(false);
                }
            } catch (err) {
                setApiConnected(false);
            }
        };

        // Initial check
        checkHealth();

        // Poll every 15 seconds
        const intervalId = setInterval(checkHealth, 15000);

        return () => clearInterval(intervalId);
    }, []);

    return (
        <div className="h-8 w-full bg-slate-950 border-t border-slate-800 flex items-center justify-between px-4 text-xs font-mono text-slate-400 shrink-0">
            <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                    <span className="text-slate-500">WebSocket:</span>
                    <span className={`w-2 h-2 rounded-full ${socketConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'}`}></span>
                    <span className={socketConnected ? 'text-emerald-400' : 'text-rose-400'}>{socketConnected ? 'CONNECTED' : 'DISCONNECTED'}</span>
                </div>

                <div className="flex items-center gap-2">
                    <span className="text-slate-500">REST Hub:</span>
                    <span className={`w-2 h-2 rounded-full ${apiConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'}`}></span>
                    <span className={apiConnected ? 'text-emerald-400' : 'text-rose-400'}>{apiConnected ? 'ONLINE' : 'OFFLINE'}</span>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <span className="text-slate-500">Active Model:</span>
                <span className="text-indigo-400 font-semibold px-2 py-0.5 bg-indigo-500/10 rounded border border-indigo-500/20">RecurrentHGAT-v3 (Loaded)</span>
            </div>
        </div>
    );
}
