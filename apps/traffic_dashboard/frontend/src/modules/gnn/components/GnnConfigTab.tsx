import { Cpu } from 'lucide-react';

const GnnConfigTab = () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
        <div className="space-y-6">
            <div className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Cpu size={18} className="text-indigo-400" /> Model Hyperparameters
                </h3>
                <div className="space-y-4">
                    {['Learning Rate', 'Discount Factor (Gamma)', 'Batch Size', 'PPO Clip Range'].map((label) => (
                        <div key={label} className="grid grid-cols-3 items-center gap-4">
                            <label className="text-slate-400 text-sm col-span-1">{label}</label>
                            <input type="text" defaultValue="0.0003" className="col-span-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none transition-colors" />
                        </div>
                    ))}
                </div>
            </div>
        </div>

        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800">
            <h3 className="text-lg font-semibold text-white mb-4">Reward Function Weights</h3>
            <div className="space-y-6">
                <div>
                    <div className="flex justify-between text-sm text-slate-400 mb-2">
                        <span>Queue Length Penalty</span>
                        <span>0.8</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500 w-[80%]"></div>
                    </div>
                </div>
                <div>
                    <div className="flex justify-between text-sm text-slate-400 mb-2">
                        <span>Waiting Time Penalty</span>
                        <span>0.5</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 w-[50%]"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
);

export default GnnConfigTab;
