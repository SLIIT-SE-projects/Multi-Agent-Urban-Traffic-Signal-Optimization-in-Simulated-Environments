import { Cpu, PlayCircle, StopCircle } from 'lucide-react';
import { useState } from 'react';
import { DASHBOARD_API_URL } from '../../../config';

const GnnConfigTab = () => {
    const [isRecording, setIsRecording] = useState(false);
    const [statusMsg, setStatusMsg] = useState("");

    const handleToggleRecord = async () => {
        try {
            if (!isRecording) {
                setStatusMsg("Starting Recording...");
                await fetch(`${DASHBOARD_API_URL}/api/baseline/record`, { method: 'POST' });
                setIsRecording(true);
                setStatusMsg("Recording... Check SUMO Window");
            } else {
                setStatusMsg("Saving Data...");
                await fetch(`${DASHBOARD_API_URL}/api/baseline/stop`, { method: 'POST' });
                setIsRecording(false);
                setStatusMsg("Saved Baseline Data");
                setTimeout(() => setStatusMsg(""), 3000);
            }
        } catch (error) {
            console.error("Error toggling record:", error);
            setStatusMsg("Error connecting to backend");
        }
    };

    return (
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

                {/* Baseline Recording Control */}
                <div className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <PlayCircle size={18} className="text-emerald-400" /> Baseline Benchmarking
                    </h3>
                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleToggleRecord}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${isRecording
                                    ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20'
                                    : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/20'
                                }`}
                        >
                            {isRecording ? <><StopCircle size={18} /> Stop & Save</> : <><PlayCircle size={18} /> Record Baseline Traffic</>}
                        </button>
                        {statusMsg && <span className="text-sm text-slate-400 animate-pulse">{statusMsg}</span>}
                    </div>
                    <p className="text-xs text-slate-500 mt-3">
                        Records traffic metrics without AI intervention to establish a baseline for comparison.
                    </p>
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
};

export default GnnConfigTab;
