import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Share2, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { DASHBOARD_API_URL } from '../../../config';

interface Node {
    id: string;
    x: number;
    y: number;
    type?: string;
    parent_edge?: string;
}

interface Edge {
    id?: string;
    from: string;
    to: string;
}

interface GraphData {
    intersections: Node[];
    lanes: Node[];
    adjacency: Edge[];
    flow: Edge[];
    membership: Edge[];
}

const GnnGraphTab = () => {
    const [graph, setGraph] = useState<GraphData | null>(null);
    const [loading, setLoading] = useState(true);

    // Zoom & Pan State
    const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
    const svgRef = useRef<SVGSVGElement>(null);

    useEffect(() => {
        fetch(`${DASHBOARD_API_URL}/api/network-graph`)
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    console.error(data.error);
                } else {
                    setGraph(data);
                }
                setLoading(false);
            })
            .catch(e => {
                console.error(e);
                setLoading(false);
            });
    }, []);

    // Calculate ViewBox to fit the map
    const viewBox = useMemo(() => {
        if (!graph || (!graph.intersections.length && !graph.lanes.length)) return "0 0 100 100";

        const allNodes = [...graph.intersections, ...graph.lanes];
        const xs = allNodes.map(n => n.x);
        const ys = allNodes.map(n => n.y);

        const minX = Math.min(...xs);
        const maxX = Math.max(...xs);
        const minY = Math.min(...ys);
        const maxY = Math.max(...ys);

        // Add padding
        const padding = 50;
        const width = maxX - minX + (padding * 2);
        const height = maxY - minY + (padding * 2);

        // SVG coordinate system has Y increasing downwards, but SUMO is cartesian (Y up).
        // We render with -y, so we need to flip the bounding box Y coords.
        const flippedMinY = -maxY;

        return `${minX - padding} ${flippedMinY - padding} ${width} ${height}`;
    }, [graph]);

    // --- Zoom & Pan Handlers ---

    const handleWheel = (e: React.WheelEvent) => {
        e.preventDefault();
        const scaleFactor = 1.1;
        const delta = -e.deltaY;
        const newScale = delta > 0 ? transform.k * scaleFactor : transform.k / scaleFactor;

        // Clamp zoom
        if (newScale < 0.1 || newScale > 10) return;

        setTransform(prev => ({
            ...prev,
            k: newScale
        }));
    };

    const handleMouseDown = (e: React.MouseEvent) => {
        setIsDragging(true);
        setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isDragging) return;
        setTransform(prev => ({
            ...prev,
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y
        }));
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    const resetZoom = () => setTransform({ x: 0, y: 0, k: 1 });
    const zoomIn = () => setTransform(prev => ({ ...prev, k: Math.min(prev.k * 1.2, 10) }));
    const zoomOut = () => setTransform(prev => ({ ...prev, k: Math.max(prev.k / 1.2, 0.1) }));

    if (loading) return <div className="text-slate-400 p-10 flex items-center justify-center h-full">Loading Network Geometry...</div>;
    if (!graph) return <div className="text-rose-400 p-10 flex items-center justify-center h-full">Failed to load graph data</div>;

    return (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 h-full flex flex-col animate-in fade-in duration-500">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2 justify-between">
                <div className="flex items-center gap-2">
                    <Share2 size={20} className="text-indigo-400" /> Connected Network Topology
                </div>
                <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
                    <button onClick={zoomOut} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors" title="Zoom Out">
                        <ZoomOut size={16} />
                    </button>
                    <button onClick={resetZoom} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors" title="Reset View">
                        <Maximize size={16} />
                    </button>
                    <button onClick={zoomIn} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors" title="Zoom In">
                        <ZoomIn size={16} />
                    </button>
                </div>
            </h3>

            <div className="flex-1 bg-[#0B1120] rounded-lg overflow-hidden border border-slate-800 relative cursor-move">
                {/* Grid Pattern Background */}
                <div className="absolute inset-0 opacity-20 pointer-events-none"
                    style={{
                        backgroundImage: 'radial-gradient(#4f46e5 1px, transparent 1px)',
                        backgroundSize: '20px 20px'
                    }}>
                </div>

                <svg
                    ref={svgRef}
                    className="w-full h-full"
                    viewBox={viewBox}
                    preserveAspectRatio="xMidYMid meet"
                    onWheel={handleWheel}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                >
                    <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>

                        {/* Layer 1: Adjacency (Intersection -> Intersection) - Orange Dashed */}
                        {graph.adjacency.map((edge, i) => {
                            const from = graph.intersections.find(n => n.id === edge.from);
                            const to = graph.intersections.find(n => n.id === edge.to);
                            if (!from || !to) return null;
                            return (
                                <line
                                    key={`adj-${i}`}
                                    x1={from.x} y1={-from.y}
                                    x2={to.x} y2={-to.y}
                                    stroke="#f97316" // Orange-500
                                    strokeWidth="2"
                                    strokeDasharray="5,5"
                                    opacity="0.3"
                                />
                            );
                        })}

                        {/* Layer 3: Membership (Lane -> Intersection) - Green */}
                        {graph.membership.map((edge, i) => {
                            const from = graph.lanes.find(n => n.id === edge.from);
                            const to = graph.intersections.find(n => n.id === edge.to);
                            if (!from || !to) return null;
                            return (
                                <line
                                    key={`mem-${i}`}
                                    x1={from.x} y1={-from.y}
                                    x2={to.x} y2={-to.y}
                                    stroke="#22c55e" // Green-500
                                    strokeWidth="1"
                                    opacity="0.2"
                                />
                            );
                        })}

                        {/* Layer 2: Flow (Lane -> Lane) - Purple */}
                        {graph.flow.map((edge, i) => {
                            const from = graph.lanes.find(n => n.id === edge.from);
                            const to = graph.lanes.find(n => n.id === edge.to);
                            if (!from || !to) return null;
                            return (
                                <line
                                    key={`flow-${i}`}
                                    x1={from.x} y1={-from.y}
                                    x2={to.x} y2={-to.y}
                                    stroke="#a855f7" // Purple-500
                                    strokeWidth="0.8"
                                    opacity="0.4"
                                    markerEnd="url(#arrow)"
                                />
                            );
                        })}

                        {/* Layer 4: Lane Nodes - Blue */}
                        {graph.lanes.map(node => (
                            <circle
                                key={node.id}
                                cx={node.x}
                                cy={-node.y}
                                r={1.5}
                                fill="#3b82f6" // Blue-500
                                opacity="0.8"
                            >
                                <title>{node.id} (Lane)</title>
                            </circle>
                        ))}

                        {/* Layer 5: Intersection Nodes - Red */}
                        {graph.intersections.map(node => (
                            <circle
                                key={node.id}
                                cx={node.x}
                                cy={-node.y}
                                r={node.type === 'traffic_light' ? 6 : 3}
                                fill={node.type === 'traffic_light' ? '#ef4444' : '#fca5a5'} // Red-500 / Red-300
                                stroke="#0f172a"
                                strokeWidth="0.5"
                                className="transition-all duration-300 hover:r-8 cursor-pointer"
                            >
                                <title>{node.id} ({node.type})</title>
                            </circle>
                        ))}
                    </g>

                    <defs>
                        <marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                            <path d="M0,0 L0,6 L9,3 z" fill="#a855f7" opacity="0.6" />
                        </marker>
                    </defs>

                </svg>

                {/* Legend */}
                <div className="absolute bottom-4 right-4 bg-slate-900/90 backdrop-blur p-3 rounded-lg text-xs text-slate-400 border border-slate-700 shadow-xl flex flex-col gap-2 pointer-events-none select-none">
                    <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-red-500 border border-slate-900"></span> Intersection</div>
                    <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-blue-500 opacity-80"></span> Lane</div>
                    <div className="flex items-center gap-2"><span className="w-4 h-0.5 bg-orange-500 border-dashed border-t border-orange-500 opacity-60"></span> Adjacency</div>
                    <div className="flex items-center gap-2"><span className="w-4 h-0.5 bg-purple-500 opacity-60"></span> Flow</div>
                    <div className="flex items-center gap-2"><span className="w-4 h-0.5 bg-green-500 opacity-40"></span> Part Of</div>
                </div>
            </div>
        </div>
    );
};

export default GnnGraphTab;
