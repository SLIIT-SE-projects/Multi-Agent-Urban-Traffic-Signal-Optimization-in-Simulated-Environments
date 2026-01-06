import { useState } from 'react';
import { Activity, Sliders, FileText, Square, Play } from 'lucide-react';

import { useTrafficSocket } from './hooks/useTrafficSocket';
import GnnMonitorTab from './components/GnnMonitorTab';
import GnnConfigTab from './components/GnnConfigTab';

export default function GNNDashboard() {
  const [activeSubTab, setActiveSubTab] = useState('monitor');
  const socketData = useTrafficSocket();
  const [isRunning, setIsRunning] = useState(false);

  const toggleSim = async () => {
    if (isRunning) {
      await socketData.handleStop();
      setIsRunning(false);
    } else {
      await socketData.handleStart();
      setIsRunning(true);
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            GNN Optimizer
            <span className={`text-xs px-2 py-0.5 rounded-full border ${socketData.isConnected ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
              {socketData.isConnected ? 'Online' : 'Offline'}
            </span>
          </h1>
          <p className="text-slate-400 text-sm">Graph Neural Network Model Inference & Control</p>
        </div>
        <button 
          onClick={toggleSim}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${
            isRunning 
              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20' 
              : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-500/20'
          }`}
        >
          {isRunning ? <><Square size={16} fill="currentColor"/> Stop Agent</> : <><Play size={16} fill="currentColor"/> Start Agent</>}
        </button>
      </div>

      <div className="flex border-b border-slate-800 mb-6">
        {[
          { id: 'monitor', label: 'Real-time Monitor', icon: Activity },
          { id: 'config', label: 'Model Configuration', icon: Sliders },
          { id: 'logs', label: 'Training Logs', icon: FileText },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeSubTab === tab.id 
                ? 'border-indigo-500 text-indigo-400' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <tab.icon size={16} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent">
        {activeSubTab === 'monitor' && <GnnMonitorTab socketData={socketData} />}
        {activeSubTab === 'config' && <GnnConfigTab />}
        {activeSubTab === 'logs' && (
          <div className="text-slate-500 flex flex-col items-center justify-center h-64 border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/50">
            <FileText size={48} className="mb-4 opacity-50"/>
            <p>Training logs and tensorboard integration would appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
}