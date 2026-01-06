import React from 'react';

interface StatCardProps {
    title: string;
    value: number | string;
    unit: string;
    icon: React.ReactElement;
    color: string;
}

const GnnStatCard: React.FC<StatCardProps> = ({ title, value, unit, icon, color }) => (
    <div className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-xl p-5 group hover:border-slate-700 transition-all">
        <div className="flex justify-between items-start mb-4">
            <div className={`p-2 rounded-lg bg-slate-800/50 ${color} text-white`}>
                {React.cloneElement(icon as React.ReactElement<any>, { size: 20 })}
            </div>
        </div>
        <div>
            <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">{title}</p>
            <h4 className="text-2xl font-bold text-white mt-1">
                {typeof value === 'number' ? value.toFixed(1) : value} <span className="text-sm text-slate-500 font-normal ml-1">{unit}</span>
            </h4>
        </div>
    </div>
);

export default GnnStatCard;
