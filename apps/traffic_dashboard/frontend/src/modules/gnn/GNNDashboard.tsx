import { useState } from 'react';
import { Activity, Sliders, FileText, Square, Play, Share2, Layers } from 'lucide-react';

import { useGnnContext } from './context/GnnContext';
import GnnMonitorTab from './components/GnnMonitorTab';
import GnnConfigTab from './components/GnnConfigTab';
import GnnGraphTab from './components/GnnGraphTab';
import GnnGraphStateTab from './components/GnnGraphStateTab';
import GnnMessagePassingTab from './components/GnnMessagePassingTab';
import SystemHealthFooter from './components/SystemHealthFooter';

export default function GNNDashboard() {
  const { isConnected, isRunning, currentMetrics, dataHistory, handleStart, handleStop } = useGnnContext();
  const [activeSubTab, setActiveSubTab] = useState('monitor');

  // Package for existing child components that expect a socketData prop
  const socketData = {
    isConnected,
    currentMetrics,
    dataHistory,
    handleStart,
    handleStop,
  };

  const toggleSim = async () => {
    if (isRunning) {
      await handleStop();
    } else {
      await handleStart();
    }
  };

  const liveDataTabs = ['monitor', 'passing', 'state', 'graph'];

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            GNN Optimizer
            <span className={`text-xs px-2 py-0.5 rounded-full border ${isConnected ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
              {isConnected ? 'Online' : 'Offline'}
            </span>
          </h1>
          <p className="text-slate-400 text-sm">Graph Neural Network Model Inference & Control</p>
        </div>
        <button
          onClick={toggleSim}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${isRunning
            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20'
            : 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-500/20'
            }`}
        >
          {isRunning ? <><Square size={16} fill="currentColor" /> Stop Agent</> : <><Play size={16} fill="currentColor" /> Start Agent</>}
        </button>
      </div>

      <div className="flex border-b border-slate-800 mb-6">
        {[
          { id: 'monitor', label: 'Real-time Monitor', icon: Activity },
          { id: 'passing', label: 'Message Passing', icon: Layers },
          { id: 'state', label: 'Graph State', icon: FileText },
          { id: 'graph', label: 'Network Graph', icon: Share2 },
          { id: 'config', label: 'Model Configuration', icon: Sliders },
          { id: 'logs', label: 'Training Logs', icon: FileText },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={`flex items-center gap-2 px-6 py-3 text-sm font-medium border-b-2 transition-colors ${activeSubTab === tab.id
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
          >
            <tab.icon size={16} /> {tab.label}
          </button>
        ))}
      </div>

      <div className={`flex-1 pr-2 scrollbar-thin scrollbar-thumb-slate-800 scrollbar-track-transparent ${activeSubTab === 'graph' ? 'overflow-hidden' : 'overflow-y-auto'}`}>
        {liveDataTabs.includes(activeSubTab) && !isRunning ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
            <Activity size={48} className="opacity-20" />
            <h2 className="text-xl font-medium text-slate-400">Agent is Offline</h2>
            <p className="text-sm">Start the GNN Agent to view real-time metrics and spatial telemetry.</p>
          </div>
        ) : (
          <>
            {activeSubTab === 'monitor' && <GnnMonitorTab socketData={socketData} isRunning={isRunning} />}
            {activeSubTab === 'passing' && <GnnMessagePassingTab socketData={socketData} />}
            {activeSubTab === 'state' && <GnnGraphStateTab socketData={socketData} />}
            {activeSubTab === 'graph' && <GnnGraphTab socketData={socketData} />}
            {activeSubTab === 'config' && <GnnConfigTab />}
            {activeSubTab === 'logs' && (
              <div className="text-slate-500 flex flex-col items-center justify-center h-64 border-2 border-dashed border-slate-800 rounded-xl bg-slate-900/50">
                <FileText size={48} className="mb-4 opacity-50" />
                <p>Training logs and tensorboard integration would appear here.</p>
              </div>
            )}
          </>
        )}
      </div>

      <SystemHealthFooter socketConnected={isConnected} />
    </div>
  );
}