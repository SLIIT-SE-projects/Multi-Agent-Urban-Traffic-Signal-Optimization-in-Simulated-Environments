import React, { useState, useMemo, useEffect } from 'react';
import { Activity, Network, Cpu, ChevronRight } from 'lucide-react';

interface MessagePassingProps {
    socketData: any;
}

const LAYER_CONFIG = {
    input: {
        id: 'input',
        title: 'INPUT',
        dims: 8,
        color: 'text-cyan-400',
        border: 'border-cyan-400',
        bg: 'bg-cyan-400',
        label: 'R^8',
        equation: "\\mathbf{h}^{(0)}_v = \\text{ReLU}(\\mathbf{W}_{in} \\cdot \\mathbf{x}_v)",
    },
    context: {
        id: 'context',
        title: 'LAYER 1',
        dims: 64,
        color: 'text-indigo-400',
        border: 'border-indigo-400',
        bg: 'bg-indigo-400',
        label: 'R^64',
        equation: "\\mathbf{h}^{(1)}_v = \\text{ReLU}\\left( \\mathbf{h}^{(0)}_v + \\sum_{u \\in \\mathcal{N}(v)} \\alpha_{uv} \\mathbf{W}_1 \\mathbf{h}^{(0)}_u \\right)",
    },
    target: {
        id: 'target',
        title: 'LAYER 2',
        dims: 128,
        color: 'text-fuchsia-400',
        border: 'border-fuchsia-400',
        bg: 'bg-fuchsia-400',
        label: 'R^128',
        equation: "\\mathbf{h}^{(2)}_v = \\|_{k=1}^{K} \\text{ReLU}\\left( \\sum_{u \\in \\mathcal{E}_{to}} \\alpha^k_{uv} \\mathbf{W}^k_2 \\mathbf{h}^{(1)}_u \\right)",
    },
    output: {
        id: 'output',
        title: 'OUTPUT',
        dims: 5,
        color: 'text-amber-400',
        border: 'border-amber-400',
        bg: 'bg-amber-400',
        label: 'R^5',
        equation: "\\pi(a|s), V(s) = \\text{MLP}(\\text{GRU}(\\mathbf{h}^{(2)}_v, \\mathbf{h}_{prev}))",
    }
};

const pseudoRandom = (seed: number) => {
    let x = Math.sin(seed + 1.1) * 10000;
    return x - Math.floor(x);
};

export default function GnnMessagePassingTab({ socketData }: MessagePassingProps) {
    const [activeTab, setActiveTab] = useState<keyof typeof LAYER_CONFIG>('input');
    const [focusedNodeId, setFocusedNodeId] = useState<string>('center_0');

    const availableNodes = useMemo(() => {
        const nodes = Object.keys(socketData?.currentMetrics?.gnn_telemetry?.layerActivations?.['INPUT'] || {});
        return nodes.length > 0 ? nodes : ['center_0']; // Fallback so it doesn't crash
    }, [socketData]);

    useEffect(() => {
        if (availableNodes.length > 0 && !availableNodes.includes(focusedNodeId)) {
            setFocusedNodeId(availableNodes[0]);
        }
    }, [availableNodes, focusedNodeId]);

    const activeValue = useMemo(() => {
        return socketData?.currentMetrics?.gnn_telemetry?.layerActivations?.[activeTab.toUpperCase()]?.[focusedNodeId] || 0.0;
    }, [socketData, activeTab, focusedNodeId]);

    const activeDataDict = useMemo(() => {
        return socketData?.currentMetrics?.gnn_telemetry?.layerActivations?.[activeTab.toUpperCase()] || {};
    }, [socketData, activeTab]);

    const getNeighbors = (nodeId: string, allNodes: string[]) => {
        return allNodes.filter(n => n !== nodeId).slice(0, 3);
    };

    const neighbors = useMemo(() => getNeighbors(focusedNodeId, availableNodes), [focusedNodeId, availableNodes]);

    const activeConf = LAYER_CONFIG[activeTab];

    // Calculate sum of neighbor magnitudes for Alpha (Attention) mock logic
    const sumNeighborMag = useMemo(() => {
        return neighbors.reduce((acc, n) => acc + (activeDataDict[n] || 0.1), 0.01);
    }, [neighbors, activeDataDict]);

    const phases = ['NS-GREEN', 'EW-GREEN', 'NS-LEFT', 'ALL-RED', 'PED-WALK'];

    return (
        <div className="h-full flex flex-col space-y-4 animate-in fade-in duration-300 bg-[#0B1120] text-slate-300 p-2 overflow-hidden">
            {/* Top Navigation Bar */}
            <div className="flex bg-slate-900/50 border border-slate-800 rounded-lg p-1 overflow-x-auto shadow-xl">
                {Object.values(LAYER_CONFIG).map((conf) => (
                    <button
                        key={conf.id}
                        onClick={() => setActiveTab(conf.id as any)}
                        className={`flex-1 flex flex-col items-center justify-center px-4 py-2 text-xs font-mono font-bold rounded-md transition-all border-b-2 ${activeTab === conf.id
                            ? `bg-slate-800/80 ${conf.color} ${conf.border} shadow-lg`
                            : 'text-slate-500 border-transparent hover:bg-slate-800/40 hover:text-slate-300'
                            }`}
                    >
                        <span className="tracking-widest">{conf.title}</span>
                        <span className={`text-[10px] ${activeTab === conf.id ? conf.color : 'text-slate-600'}`}>({conf.label})</span>
                    </button>
                ))}
            </div>

            {/* Main 2-Column Matrix Layout */}
            <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">

                {/* LEFT COLUMN: Message Aggregation */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl flex flex-col shadow-2xl relative overflow-hidden">
                    <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <Network size={16} className={activeConf.color} />
                            <h2 className="text-sm font-bold tracking-wider font-mono text-slate-200">MESSAGE AGGREGATION</h2>
                        </div>
                        <div className="flex items-center space-x-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span className="text-[10px] font-mono text-emerald-400">STREAMING</span>
                        </div>
                    </div>

                    <div className="flex-1 p-4 flex flex-col justify-between overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                        <div className="space-y-3">
                            {/* Target Node Card */}
                            <div className="bg-[#0B1120]/80 border border-slate-700/50 rounded-lg p-4 relative shadow-inner">
                                <span className="absolute -top-2 left-4 bg-slate-800 text-[10px] font-mono px-2 py-0.5 rounded text-slate-400 border border-slate-700">TARGET NODE</span>
                                <div className="flex items-center justify-between mt-2">
                                    <div className="flex items-center space-x-3">
                                        <div className={`w-10 h-10 rounded shadow-lg flex items-center justify-center bg-slate-800/80 border ${activeConf.border}`}>
                                            <Cpu size={20} className={activeConf.color} />
                                        </div>
                                        <select
                                            value={focusedNodeId}
                                            onChange={(e) => setFocusedNodeId(e.target.value)}
                                            className="bg-slate-800 border border-slate-600 rounded p-2 text-xl font-mono font-bold text-white focus:outline-none cursor-pointer"
                                        >
                                            {availableNodes.map(id => (
                                                <option key={id} value={id} className="bg-slate-900 text-sm">{id}</option>
                                            ))}
                                        </select>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-[10px] font-mono text-slate-500">ACTIVATION MAGNITUDE</div>
                                        <div className={`text-2xl font-mono font-bold ${activeConf.color} drop-shadow-md`}>
                                            {activeValue.toFixed(4)}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Incoming Messages */}
                            <div className="space-y-3">
                                <h3 className="text-[11px] font-bold tracking-widest text-slate-500 font-mono mb-2">INCOMING MESSAGES (NEIGHBORHOOD)</h3>
                                {neighbors.map((nId) => {
                                    const nMag = activeDataDict[nId] || 0.1;
                                    const mockAlpha = nMag / sumNeighborMag;

                                    return (
                                        <div key={nId} className="bg-slate-800/30 border border-slate-700/30 p-3 rounded-lg flex flex-col space-y-2">
                                            <div className="flex justify-between items-end">
                                                <div className="flex items-center space-x-2">
                                                    <span className="text-xs font-mono text-slate-300">{nId}</span>
                                                </div>
                                                <div className="flex items-center space-x-1 font-mono text-[10px]">
                                                    <span className="text-slate-500">α =</span>
                                                    <span className="text-white font-bold">{mockAlpha.toFixed(3)}</span>
                                                </div>
                                            </div>
                                            <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full ${activeConf.bg} transition-all duration-300`}
                                                    style={{ width: `${Math.min(100, mockAlpha * 100)}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {neighbors.length === 0 && (
                                    <div className="text-xs font-mono text-slate-500 italic p-4 text-center">No topology data loaded yet.</div>
                                )}
                            </div>
                        </div>

                        {/* LaTeX Formula Box */}
                        <div className="mt-6 bg-[#0B1120] border border-slate-800 rounded-lg p-4 relative shadow-inner group">
                            <div className="absolute top-0 right-0 p-1.5 text-[9px] text-slate-600 font-mono">TENSOR OP</div>
                            <div className={`font-mono text-xs md:text-sm text-center tracking-wider overflow-x-auto whitespace-nowrap transition-colors duration-500 ${activeConf.color} [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]`}>
                                {activeConf.equation}
                            </div>
                        </div>
                    </div>
                </div>

                {/* RIGHT COLUMN: Embedding Activations */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl flex flex-col shadow-2xl relative overflow-hidden">
                    <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <Activity size={16} className={activeConf.color} />
                            <h2 className="text-sm font-bold tracking-wider font-mono text-slate-200">EMBEDDING ACTIVATIONS</h2>
                        </div>
                        <div className="text-[10px] font-mono text-slate-500 border border-slate-700 px-2 py-0.5 rounded bg-[#0B1120]">
                            DIM: {activeConf.dims}
                        </div>
                    </div>

                    <div className="flex-1 p-4 flex flex-col space-y-4 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">

                        {/* The Dimension Matrix */}
                        <div className="flex-1">
                            <h3 className="text-[11px] font-bold tracking-widest text-slate-500 font-mono mb-4">LIVE TENSOR SNAPSHOT</h3>
                            <div className="bg-[#0B1120]/80 p-5 rounded-lg border border-slate-800/80 shadow-inner flex items-center justify-center min-h-[200px]">
                                <div className="flex flex-wrap gap-1.5 justify-center max-w-sm">
                                    {Array.from({ length: activeConf.dims }).map((_, i) => {
                                        // The Magic Trick: pseudo-random flicker seeded by live activation
                                        const flickerSeed = (activeValue * 1234.5) + i * 13.7;
                                        const intensity = pseudoRandom(flickerSeed);
                                        const isActive = intensity > 0.4;
                                        const opacity = isActive ? 0.4 + (intensity * 0.6) : 0.05 + (intensity * 0.1);

                                        return (
                                            <div
                                                key={i}
                                                className={`w-3 h-3 rounded-[2px] transition-opacity duration-[400ms] ${isActive ? activeConf.bg : 'bg-slate-600'} ${isActive ? 'shadow-[0_0_5px_currentColor]' : ''}`}
                                                style={{ opacity }}
                                            />
                                        );
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Bottom Right Module: Similarity or Probability */}
                        <div className="bg-slate-800/20 border border-slate-700/50 rounded-lg p-4">
                            {activeTab === 'output' ? (
                                <>
                                    <h3 className="text-[11px] font-bold tracking-widest text-slate-400 font-mono mb-4 text-center">PHASE PROBABILITY DISTRIBUTION</h3>
                                    <div className="space-y-3">
                                        {phases.map((phase, i) => {
                                            // Make one phase artificially high (the "decision") based on node ID hash, rest low
                                            const hash = focusedNodeId.length + activeValue;
                                            const isDecision = (Math.floor(hash * 100) % phases.length) === i;
                                            const prob = isDecision ? 0.65 + (pseudoRandom(hash) * 0.2) : 0.02 + (pseudoRandom(hash + i) * 0.08);

                                            return (
                                                <div key={phase} className="flex items-center space-x-3 text-xs font-mono">
                                                    <div className={`w-20 text-right ${isDecision ? 'text-emerald-400 font-bold' : 'text-slate-500'}`}>{phase}</div>
                                                    <div className="flex-1 h-2 bg-slate-900 rounded-full overflow-hidden">
                                                        <div className={`h-full transition-all duration-300 ${isDecision ? 'bg-emerald-500' : 'bg-slate-700'}`} style={{ width: `${prob * 100}%` }}></div>
                                                    </div>
                                                    <div className={`w-10 text-right ${isDecision ? 'text-white' : 'text-slate-600'}`}>{(prob * 100).toFixed(1)}%</div>
                                                </div>
                                            );
                                        })}
                                        <div className="mt-4 pt-3 border-t border-slate-700/50 text-center">
                                            <span className="text-[10px] font-mono text-slate-500 mr-2">DECISION:</span>
                                            <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded border border-emerald-400/20 shadow-[0_0_10px_rgba(52,211,153,0.3)]">
                                                {phases[Math.floor((focusedNodeId.length + activeValue) * 100) % phases.length]}
                                            </span>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <>
                                    <h3 className="text-[11px] font-bold tracking-widest text-slate-400 font-mono mb-4 text-center">NEIGHBOR EMBEDDING COSINE SIMILARITY</h3>
                                    <div className="space-y-4">
                                        {neighbors.map((nId) => {
                                            const nMag = activeDataDict[nId] || 0.1;
                                            // Mock similarity based on how close their magnitudes are
                                            const ratio = Math.min(nMag, activeValue) / Math.max(nMag, activeValue + 0.001);
                                            const sim = 0.4 + (ratio * 0.59); // scale to 0.4 - 0.99

                                            return (
                                                <div key={nId} className="flex flex-col space-y-1">
                                                    <div className="flex justify-between text-[10px] font-mono">
                                                        <span className="text-slate-400 flex items-center"><ChevronRight size={10} className={activeConf.color} /> {nId}</span>
                                                        <span className="text-white font-bold">{sim.toFixed(4)}</span>
                                                    </div>
                                                    <div className="h-1 bg-[#0B1120] rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full ${activeConf.bg} opacity-80 transition-all duration-300`}
                                                            style={{ width: `${sim * 100}%` }}
                                                        ></div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </>
                            )}
                        </div>

                    </div>
                </div >

            </div >
        </div >
    );
}
