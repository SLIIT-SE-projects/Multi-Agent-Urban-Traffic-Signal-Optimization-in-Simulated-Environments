import { Handle, Position } from '@xyflow/react';

interface GnnCustomNodeProps {
    data: any;
    selected?: boolean;
}

export default function GnnCustomNode({ data, selected }: GnnCustomNodeProps) {
    // Determine color based on phase_index
    const getPhaseStyle = () => {
        if (data.phase_index === undefined) {
            return {
                borderClass: 'border-slate-600',
                glowClass: 'shadow-none',
                bgClass: 'bg-slate-800',
                textClass: 'text-slate-400'
            };
        }

        // Even phase (0, 2, 4) -> Green
        if (data.phase_index % 2 === 0) {
            return {
                borderClass: 'border-emerald-500',
                glowClass: 'shadow-[0_0_15px_rgba(16,185,129,0.8)]',
                bgClass: 'bg-slate-900',
                textClass: 'text-emerald-400'
            };
        }

        // Odd phase (1, 3, 5) -> Yellow
        return {
            borderClass: 'border-amber-400',
            glowClass: 'shadow-[0_0_15px_rgba(251,191,36,0.8)]',
            bgClass: 'bg-slate-900',
            textClass: 'text-amber-400'
        };
    };

    const { borderClass, glowClass, bgClass, textClass } = getPhaseStyle();

    return (
        <div
            className={`
                w-10 h-10 rounded-full flex items-center justify-center font-bold text-[10px] select-none
                transition-all duration-300 border-2
                ${bgClass} ${textClass}
                ${selected ? `scale-125 ${borderClass} ${glowClass}` : `scale-100 ${borderClass} opacity-90`}
            `}
        >
            <Handle type="target" position={Position.Top} className="opacity-0" />
            {data.label}
            <Handle type="source" position={Position.Bottom} className="opacity-0" />
        </div>
    );
}
