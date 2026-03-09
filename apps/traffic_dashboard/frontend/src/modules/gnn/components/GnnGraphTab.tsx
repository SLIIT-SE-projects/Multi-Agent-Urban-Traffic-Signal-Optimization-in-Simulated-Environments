import React, { useEffect, useState, useMemo } from 'react';
import { Share2 } from 'lucide-react';
import {
    ReactFlow,
    Background,
    Controls,
    useNodesState,
    useEdgesState,
    BackgroundVariant
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { DASHBOARD_API_URL } from '../../../config';
import NodeInspector from './NodeInspector';
import GnnCustomNode from './GnnCustomNode';

interface GnnGraphTabProps {
    socketData?: any;
}

export default function GnnGraphTab({ socketData }: GnnGraphTabProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    const nodeTypes = useMemo(() => ({ custom: GnnCustomNode }), []);

    useEffect(() => {
        fetch(`${DASHBOARD_API_URL}/api/network-graph`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    setError(data.error);
                } else {
                    // Map nodes (intersections)
                    const newNodes = (data.intersections || []).map((intersection: any) => ({
                        id: intersection.id,
                        type: 'custom',
                        position: { x: intersection.x, y: -(intersection.y || 0) },
                        data: { label: intersection.id }
                    }));

                    // Map edges (adjacency)
                    const newEdges = (data.adjacency || []).map((edge: any) => ({
                        id: edge.id || `e-${edge.from}-${edge.to}`,
                        source: edge.from,
                        target: edge.to,
                        style: { stroke: '#475569', strokeWidth: 2 }, // slate-600
                        animated: true,
                    }));

                    setNodes(newNodes);
                    setEdges(newEdges);
                }
                setLoading(false);
            })
            .catch(e => {
                console.error(e);
                setError('Failed to load graph data');
                setLoading(false);
            });
    }, [setNodes, setEdges]);

    // Listen to live WebSocket telemetry for dynamic styling
    useEffect(() => {
        if (!socketData?.currentMetrics) return;

        const liveIntersections = socketData.currentMetrics.intersections || {};
        const liveLanes = socketData.currentMetrics.lanes || {};

        setNodes((nds) =>
            nds.map((node) => {
                const liveData = liveIntersections[node.id];
                if (liveData) {
                    return {
                        ...node,
                        data: { ...node.data, phase_index: liveData.phase_index }
                    };
                }

                return {
                    ...node,
                    data: { ...node.data, phase_index: undefined }
                };
            })
        );

        setEdges((eds) =>
            eds.map((edge) => {
                let edgeQueue = 0;
                let laneCount = 0;

                // Match lanes connecting to this edge
                for (const [laneId, laneData] of Object.entries<any>(liveLanes)) {
                    if (laneId.startsWith(edge.id + '_')) {
                        edgeQueue += laneData.queue_length || 0;
                        laneCount++;
                    }
                }

                let stroke = '#475569'; // Muted dark slate
                let strokeWidth = 2;

                if (laneCount > 0) {
                    if (edgeQueue > 10) {
                        stroke = '#ef4444'; // Red for heavy jam
                        strokeWidth = 4;
                    } else if (edgeQueue > 3) {
                        stroke = '#f59e0b'; // Amber for moderate queue
                        strokeWidth = 3;
                    } else {
                        stroke = '#3b82f6'; // Blue for flowing
                    }
                }

                return {
                    ...edge,
                    style: { ...edge.style, stroke, strokeWidth }
                };
            })
        );
    }, [socketData?.currentMetrics, setNodes, setEdges]);

    if (loading) return <div className="text-slate-400 p-10 flex items-center justify-center h-full">Loading Network Geometry...</div>;
    if (error) return <div className="text-rose-400 p-10 flex items-center justify-center h-full">{error}</div>;

    return (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 h-full flex flex-col animate-in fade-in duration-500">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Share2 size={20} className="text-indigo-400" /> Live Graph Topology
            </h3>

            <div className="flex-1 bg-[#0B1120] rounded-lg overflow-hidden border border-slate-800 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    nodeTypes={nodeTypes}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={(_, node) => setSelectedNodeId(node.id)}
                    fitView
                    colorMode="dark"
                >
                    <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#334155" />
                    <Controls className="bg-slate-800 border-slate-700 fill-slate-300" />
                </ReactFlow>

                {selectedNodeId && (
                    <NodeInspector
                        nodeId={selectedNodeId}
                        socketData={socketData}
                        onClose={() => setSelectedNodeId(null)}
                    />
                )}

                <div className="absolute bottom-4 right-4 bg-slate-900/90 backdrop-blur p-4 rounded-lg text-sm text-slate-300 border border-slate-700 shadow-xl flex flex-col gap-3 pointer-events-none select-none">
                    <div className="font-semibold text-white mb-1">Graph Legend</div>
                    <div className="flex items-center gap-3"><span className="w-3 h-3 rounded-full bg-[#1e293b] border-2 border-[#22c55e] shadow-[0_0_8px_rgba(34,197,94,0.4)]"></span> Connected Intersection</div>
                    <div className="flex items-center gap-3"><span className="w-3 h-3 rounded-full bg-[#1e293b] border border-[#334155]"></span> Disconnected Node</div>
                    <div className="h-px bg-slate-800 my-1"></div>
                    <div className="flex items-center gap-3"><span className="w-5 h-1.5 bg-[#ef4444] rounded-full"></span> Severe Traffic Jam</div>
                    <div className="flex items-center gap-3"><span className="w-5 h-1 bg-[#f59e0b] rounded-full"></span> Moderate Queuing</div>
                    <div className="flex items-center gap-3"><span className="w-5 h-0.5 bg-[#3b82f6] rounded-full"></span> Free Flowing</div>
                    <div className="flex items-center gap-3"><span className="w-5 h-0.5 bg-[#475569] rounded-full"></span> Offline / No Flow</div>
                </div>
            </div>
        </div>
    );
}
