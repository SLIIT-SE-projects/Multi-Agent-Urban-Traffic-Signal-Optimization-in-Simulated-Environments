import React, { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer 
} from 'recharts';
import { 
  Activity, Car, Zap, Play, Square, Leaf, 
  LayoutDashboard, Settings, Network, Map as MapIcon,
  Cpu, Sliders, FileText, Search, Bell, ChevronRight
} from 'lucide-react';

// --- 1. HOOKS & UTILS ---

interface TrafficData {
  step: number;
  total_queue: number;
  avg_speed: number;
  total_co2: number;
  total_waiting_time: number;
  cumulative_throughput: number;
}

// Simulated Hook (Replace with your real socket logic)
const useTrafficSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [dataHistory, setDataHistory] = useState<TrafficData[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState({ 
    step: 0, total_queue: 0, avg_speed: 0, total_co2: 0, total_waiting_time: 0, cumulative_throughput: 0
  });

  useEffect(() => {
    const socket = io('http://localhost:5001');
    socket.on('connect', () => setIsConnected(true));
    socket.on('disconnect', () => setIsConnected(false));
    
    socket.on('traffic_update', (data: any) => {
       // ... (Keep your existing data parsing logic here)
       // For demo purposes, I'm passing the data through as-is or mocking if backend is off
       setCurrentMetrics(prev => ({
         ...prev,
         ...data,
         cumulative_throughput: prev.cumulative_throughput + (data.throughput || 0)
       }));
       
       setDataHistory(prev => {
         const newH = [...prev, { ...data, cumulative_throughput: 0 }]; // Simplified for demo
         return newH.length > 60 ? newH.slice(newH.length - 60) : newH;
       });
    });

    return () => { socket.disconnect(); };
  }, []);

  const handleStart = async () => fetch('http://localhost:5001/api/start', { method: 'POST' });
  const handleStop = async () => fetch('http://localhost:5001/api/stop', { method: 'POST' });

  return { isConnected, currentMetrics, dataHistory, handleStart, handleStop };
};

// --- 2. SHARED UI COMPONENTS ---

const StatCard = ({ title, value, unit, icon, color }: any) => (
  <div className="relative overflow-hidden bg-slate-900 border border-slate-800 rounded-xl p-5 group hover:border-slate-700 transition-all">
    <div className="flex justify-between items-start mb-4">
      <div className={`p-2 rounded-lg bg-slate-800/50 ${color} text-white`}>
        {React.cloneElement(icon, { size: 20 })}
      </div>
    </div>
    <div>
      <p className="text-slate-400 text-xs font-medium uppercase tracking-wider">{title}</p>
      <h4 className="text-2xl font-bold text-white mt-1">
        {value} <span className="text-sm text-slate-500 font-normal ml-1">{unit}</span>
      </h4>
    </div>
  </div>
);

const ChartCard = ({ title, data, dataKey, color, fillId, height = "h-80" }: any) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-xl p-5 ${height} flex flex-col`}>
    <h3 className="text-slate-200 font-semibold mb-4 flex items-center gap-2 text-sm">
      <div className={`w-1.5 h-4 rounded-full ${color.replace('text', 'bg')}`} />
      {title}
    </h3>
    <div className="flex-1 w-full min-h-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="currentColor" stopOpacity={0.3} className={color} />
              <stop offset="95%" stopColor="currentColor" stopOpacity={0} className={color} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis dataKey="step" hide />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
          <Area type="monotone" dataKey={dataKey} stroke="currentColor" strokeWidth={2} fill={`url(#${fillId})`} className={color} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  </div>
);

// --- 3. SUB-FEATURE: GNN CONFIGURATION TAB ---
const GNNConfigTab = () => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-4xl">
    <div className="space-y-6">
      <div className="bg-slate-900 p-6 rounded-xl border border-slate-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Cpu size={18} className="text-indigo-400"/> Model Hyperparameters
        </h3>
        <div className="space-y-4">
          {['Learning Rate', 'Discount Factor (Gamma)', 'Batch Size', 'PPO Clip Range'].map((label) => (
            <div key={label} className="grid grid-cols-3 items-center gap-4">
              <label className="text-slate-400 text-sm col-span-1">{label}</label>
              <input type="text" defaultValue="0.0003" className="col-span-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none" />
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

// --- 4. MAIN FEATURE: GNN MONITOR TAB (The Dashboard) ---
const GNNMonitorTab = ({ socketData }: any) => {
  const { currentMetrics, dataHistory } = socketData;
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard title="Avg Queue" value={currentMetrics.total_queue} unit="veh" icon={<Car />} color="text-blue-500" />
        <StatCard title="Avg Speed" value={currentMetrics.avg_speed} unit="m/s" icon={<Zap />} color="text-amber-400" />
        <StatCard title="Emissions" value={currentMetrics.total_co2} unit="g/s" icon={<Leaf />} color="text-emerald-500" />
        <StatCard title="Throughput" value={currentMetrics.cumulative_throughput} unit="veh" icon={<Activity />} color="text-purple-500" />
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Queue Length (Congestion)" data={dataHistory} dataKey="total_queue" color="text-blue-500" fillId="qGrad" />
        <ChartCard title="Network Speed Flow" data={dataHistory} dataKey="avg_speed" color="text-amber-400" fillId="sGrad" />
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
           <ChartCard title="CO2 Impact" data={dataHistory} dataKey="total_co2" color="text-emerald-500" fillId="cGrad" height="h-64" />
        </div>
        <div className="lg:col-span-2">
           <ChartCard title="Waiting Time Distribution" data={dataHistory} dataKey="total_waiting_time" color="text-rose-500" fillId="wGrad" height="h-64" />
        </div>
      </div>
    </div>
  );
};

// --- 5. PAGE CONTAINER: GNN OPTIMIZER ROOT ---
const GNNOptimizerPage = () => {
  // Inner Tab State for GNN Optimizer
  const [activeSubTab, setActiveSubTab] = useState('monitor');
  const socketData = useTrafficSocket();
  const [isRunning, setIsRunning] = useState(false);

  const toggleSim = () => {
    if(isRunning) socketData.handleStop();
    else socketData.handleStart();
    setIsRunning(!isRunning);
  }

  return (
    <div className="h-full flex flex-col">
      {/* Page Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">GNN Optimizer</h1>
          <p className="text-slate-400 text-sm">Graph Neural Network Model Inference & Control</p>
        </div>
        <button 
          onClick={toggleSim}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
            isRunning ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50' : 'bg-indigo-600 text-white hover:bg-indigo-500'
          }`}
        >
          {isRunning ? <><Square size={16}/> Stop Agent</> : <><Play size={16}/> Start Agent</>}
        </button>
      </div>

      {/* Internal Tabs Navigation */}
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

      {/* Tab Content Render */}
      <div className="flex-1 overflow-y-auto pr-2">
        {activeSubTab === 'monitor' && <GNNMonitorTab socketData={socketData} />}
        {activeSubTab === 'config' && <GNNConfigTab />}
        {activeSubTab === 'logs' && (
          <div className="text-slate-500 flex flex-col items-center justify-center h-64 border-2 border-dashed border-slate-800 rounded-xl">
            <FileText size={48} className="mb-4 opacity-50"/>
            <p>Training logs and tensorboard integration would appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

// --- 6. MAIN APP SHELL ---
export default function App() {
  const [activeMainTab, setActiveMainTab] = useState('gnn');

  return (
    <div className="flex h-screen bg-[#0B1120] text-slate-100 font-sans">
      
      {/* GLOBAL SIDEBAR */}
      <aside className="w-64 border-r border-slate-800 bg-[#0B1120] flex flex-col">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-violet-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Network size={20} className="text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-slate-100">MultiAgent<span className="text-indigo-400">.ai</span></span>
        </div>
        
        <nav className="flex-1 px-3 space-y-1 mt-6">
          <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Platform</p>
          
          <SidebarItem 
            icon={<LayoutDashboard size={18} />} 
            label="System Overview" 
            active={activeMainTab === 'overview'} 
            onClick={() => setActiveMainTab('overview')}
          />
          <SidebarItem 
            icon={<Cpu size={18} />} 
            label="GNN Optimizer" 
            active={activeMainTab === 'gnn'} 
            onClick={() => setActiveMainTab('gnn')}
          />
          <SidebarItem 
            icon={<MapIcon size={18} />} 
            label="SUMO Map View" 
            active={activeMainTab === 'map'} 
            onClick={() => setActiveMainTab('map')}
          />
          
          <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-2">Settings</p>
          <SidebarItem icon={<Settings size={18} />} label="System Config" />
        </nav>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-16 border-b border-slate-800 bg-[#0B1120]/50 backdrop-blur-sm flex items-center justify-between px-8">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span>Platform</span>
            <ChevronRight size={14} />
            <span className="text-slate-200 font-medium capitalize">{activeMainTab.replace('-', ' ')}</span>
          </div>
          <div className="flex items-center gap-4">
             <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input type="text" placeholder="Search..." className="bg-slate-900 border border-slate-800 rounded-full pl-9 pr-4 py-1.5 text-xs focus:outline-none w-48 transition-all focus:border-indigo-500" />
             </div>
             <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 cursor-pointer transition-colors">
                <Bell size={16} className="text-slate-400" />
             </div>
          </div>
        </header>

        {/* Dynamic Page Content */}
        <div className="flex-1 p-8 overflow-hidden">
          {activeMainTab === 'gnn' ? (
            <GNNOptimizerPage />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-2xl bg-slate-900/20">
              <div className="p-4 bg-slate-800 rounded-full mb-4">
                <Network size={32} className="text-indigo-500 opacity-50"/>
              </div>
              <h2 className="text-xl font-semibold text-slate-300">Work in Progress</h2>
              <p className="mt-2">The <span className="text-indigo-400 font-mono">{activeMainTab}</span> module is under development.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

// Helper for Sidebar
const SidebarItem = ({ icon, label, active, onClick }: any) => (
  <button 
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
      active 
        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20' 
        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
    }`}
  >
    {icon}
    {label}
  </button>
);