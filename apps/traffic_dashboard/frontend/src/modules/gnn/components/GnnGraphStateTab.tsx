import React from 'react';
import GnnNodeLoadRadar from './GnnNodeLoadRadar';
import GnnNodeFeatureCard from './GnnNodeFeatureCard';
import { Layers } from 'lucide-react';

interface GnnGraphStateTabProps {
    socketData: any;
}

const GnnGraphStateTab: React.FC<GnnGraphStateTabProps> = ({ socketData }) => {
    const intersections = socketData?.currentMetrics?.intersections || {};

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Top Radar Chart Section */}
            <div className="w-full h-[500px]">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Layers size={20} className="text-indigo-400" /> Global Graph Load Distribution
                </h3>
                <GnnNodeLoadRadar socketData={socketData} />
            </div>

            {/* Bottom Grid for Individual Nodes */}
            <div>
                <h3 className="text-lg font-semibold text-white mb-4">GNN Embeddings (Active Nodes)</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-4">
                    {Object.entries<any>(intersections).map(([nodeId, metrics]) => (
                        <GnnNodeFeatureCard key={nodeId} nodeId={nodeId} metrics={metrics} />
                    ))}
                    {Object.keys(intersections).length === 0 && (
                        <p className="text-sm text-slate-500 col-span-full">No active nodes connected.</p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default GnnGraphStateTab;
