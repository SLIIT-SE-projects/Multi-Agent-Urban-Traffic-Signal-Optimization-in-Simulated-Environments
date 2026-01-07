import React from 'react';
import { Sliders } from 'lucide-react';

const MpcConfigTab = () => {
    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
                <h3 className="text-white text-lg font-semibold mb-4 flex items-center gap-2">
                    <Sliders size={20} className="text-indigo-400" />
                    MPC Parameters
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                        <label className="text-slate-400 text-sm font-medium">Prediction Horizon (N)</label>
                        <input
                            type="number"
                            defaultValue={10}
                            disabled
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2.5 px-3 text-slate-300 focus:outline-none focus:border-indigo-500 disabled:opacity-50 cursor-not-allowed"
                        />
                        <p className="text-xs text-slate-500">Number of steps to predict into the future.</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-slate-400 text-sm font-medium">Control Interval</label>
                        <input
                            type="number"
                            defaultValue={5}
                            disabled
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg py-2.5 px-3 text-slate-300 focus:outline-none focus:border-indigo-500 disabled:opacity-50 cursor-not-allowed"
                        />
                        <p className="text-xs text-slate-500">Steps between action updates.</p>
                    </div>
                </div>

                <div className="mt-6 p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                    <p className="text-sm text-yellow-500/80">⚠️ Configuration is currently read-only. Edit <code>config.py</code> to change parameters.</p>
                </div>
            </div>
        </div>
    );
};

export default MpcConfigTab;
