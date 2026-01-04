import React, { useEffect, useState, useRef } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer 
} from 'recharts';
import { 
  Activity, Car, Zap, Play, Square, Leaf, 
  Cpu, Sliders, FileText
} from 'lucide-react';

import { WS_BASE_URL, ENDPOINTS } from '../../config';

interface TrafficData {
  step: number;
  total_queue: number;
  avg_speed: number;
  total_co2: number;
  total_waiting_time: number;
  cumulative_throughput: number;
}

const useTrafficSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [dataHistory, setDataHistory] = useState<TrafficData[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState({ 
    step: 0, total_queue: 0, avg_speed: 0, total_co2: 0, total_waiting_time: 0, cumulative_throughput: 0
  });
  
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // UPDATED: Using constant from config
    const socket = new WebSocket(WS_BASE_URL);
    ws.current = socket;

    socket.onopen = () => {
      console.log(' Connected to Dashboard API');
      setIsConnected(true);
    };

    socket.onclose = () => {
      console.log(' Disconnected from Dashboard API');
      setIsConnected(false);
    };

    socket.onmessage = (event) => {
      try {
        const response = JSON.parse(event.data);
        
        if (response.channel === 'gnn_metrics') {
          const data = response.data;
          
          setCurrentMetrics(prev => ({
            ...prev,
            ...data,
            cumulative_throughput: prev.cumulative_throughput + (data.throughput || 0)
          }));
          
          setDataHistory(prev => {
            const newH = [...prev, { ...data, cumulative_throughput: 0 }];
            return newH.length > 60 ? newH.slice(newH.length - 60) : newH;
          });
        }
      } catch (err) {
        console.error("Error parsing websocket message:", err);
      }
    };

    return () => {
      socket.close();
    };
  }, []);

  const sendCommand = async (action: 'start' | 'stop') => {
    try {
      // UPDATED: Using constant from config
      await fetch(ENDPOINTS.CONTROL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          action: action, 
          model: 'gnn' 
        })
      });
    } catch (e) {
      console.error(`Failed to send ${action} command`, e);
    }
  };

  return { 
    isConnected, 
    currentMetrics, 
    dataHistory, 
    handleStart: () => sendCommand('start'), 
    handleStop: () => sendCommand('stop') 
  };
};

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
        {typeof value === 'number' ? value.toFixed(1) : value} <span className="text-sm text-slate-500 font-normal ml-1">{unit}</span>
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
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
            itemStyle={{ color: '#e2e8f0' }}
            labelStyle={{ color: '#94a3b8' }}
          />
          <Area 
            type="monotone" 
            dataKey={dataKey} 
            stroke="currentColor" 
            strokeWidth={2} 
            fill={`url(#${fillId})`} 
            className={color} 
            isAnimationActive={false} 
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  </div>
);

const GNNConfigTab = () => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
    <div className="space-y-6">
      <div className="bg-slate-900 p-6 rounded-xl border border-slate-800">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Cpu size={18} className="text-indigo-400"/> Model Hyperparameters
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

const GNNMonitorTab = ({ socketData }: any) => {
  const { currentMetrics, dataHistory } = socketData;
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard title="Avg Queue" value={currentMetrics.total_queue} unit="veh" icon={<Car />} color="text-blue-500" />
        <StatCard title="Avg Speed" value={currentMetrics.avg_speed} unit="m/s" icon={<Zap />} color="text-amber-400" />
        <StatCard title="Emissions" value={currentMetrics.total_co2} unit="g/s" icon={<Leaf />} color="text-emerald-500" />
        <StatCard title="Throughput" value={currentMetrics.cumulative_throughput} unit="veh" icon={<Activity />} color="text-purple-500" />
      </div>

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
        {activeSubTab === 'monitor' && <GNNMonitorTab socketData={socketData} />}
        {activeSubTab === 'config' && <GNNConfigTab />}
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