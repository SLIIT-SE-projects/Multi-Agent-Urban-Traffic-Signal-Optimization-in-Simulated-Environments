import React from 'react';
import { Cpu } from 'lucide-react';

interface GnnNodeFeatureCardProps {
    nodeId: string;
    metrics: any;
}

const GnnNodeFeatureCard: React.FC<GnnNodeFeatureCardProps> = ({ nodeId, metrics }) => {
    return (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                <Cpu size={14} className="text-indigo-400" />
                {nodeId}
            </h4>
            <div className="text-xs text-slate-400">
                Phase Index: <span className="text-white font-mono">{metrics?.phase_index ?? 'N/A'}</span>
            </div>
            <div className="text-xs text-slate-400">
                Time to Switch: <span className="text-emerald-400 font-mono">{metrics?.time_to_switch?.toFixed(2) ?? 'N/A'}s</span>
            </div>
        </div>
    );
};

export default GnnNodeFeatureCard;
