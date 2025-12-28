import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Activity, Car, Zap, Play, Square, Clock, Leaf } from 'lucide-react';

// Connect to Python Backend
const socket = io('http://localhost:5000');

// 1. Update Types (Removed Uncertainty)
interface TrafficData {
  step: number;
  total_queue: number;
  avg_speed: number;
  total_co2: number;
  total_waiting_time: number;
}

interface TrafficResponse {
  step: number;
  total_queue: number;
  avg_speed: number;
  total_co2: number;
  total_waiting_time: number;
  intersections: Record<string, string>;
}

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [dataHistory, setDataHistory] = useState<TrafficData[]>([]);
  
  // Initialize with zeros (Removed Uncertainty)
  const [currentMetrics, setCurrentMetrics] = useState<TrafficData>({ 
    step: 0, 
    total_queue: 0, 
    avg_speed: 0,
    total_co2: 0,
    total_waiting_time: 0
  });

  useEffect(() => {
    socket.on('connect', () => setIsConnected(true));
    socket.on('disconnect', () => setIsConnected(false));

    socket.on('traffic_update', (data: TrafficResponse) => {
      // 2. Parse new values from Backend (Removed Uncertainty)
      const newData = {
        step: data.step,
        total_queue: parseFloat(data.total_queue.toFixed(2)),
        avg_speed: parseFloat(data.avg_speed.toFixed(2)),
        total_co2: parseFloat((data.total_co2 / 1000).toFixed(2)), // Convert mg to Grams for readability
        total_waiting_time: parseFloat(data.total_waiting_time.toFixed(2))
      };

      setCurrentMetrics(newData);
      
      setDataHistory(prev => {
        const newHistory = [...prev, newData];
        // Keep last 60 points (approx 1 minute of history at 1s/step)
        if (newHistory.length > 60) return newHistory.slice(newHistory.length - 60);
        return newHistory;
      });
    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('traffic_update');
    };
  }, []);

  const handleStart = async () => {
    await fetch('http://localhost:5000/api/start', { method: 'POST' });
    setIsRunning(true);
  };

  const handleStop = async () => {
    await fetch('http://localhost:5000/api/stop', { method: 'POST' });
    setIsRunning(false);
  };

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto bg-slate-900 text-slate-100">
      {/* Header */}
      <header className="flex justify-between items-center mb-8 border-b border-slate-700 pb-4">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
            GNN Traffic Optimizer
          </h1>
          <p className="text-slate-400 mt-1">Real-time MARL Inference & Analytics</p>
        </div>
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${isConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
            {isConnected ? 'Backend Connected' : 'Disconnected'}
          </div>
        </div>
      </header>

      {/* Control Panel */}
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 mb-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-200">Simulation Control</h2>
          <p className="text-slate-400 text-sm">Start/Stop the SUMO environment backend.</p>
        </div>
        <div className="flex gap-4 w-full md:w-auto">
            <button 
              onClick={handleStart}
              disabled={isRunning}
              className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg transition-colors font-medium"
            >
              <Play size={18} /> Start Simulation
            </button>
            <button 
              onClick={handleStop}
              disabled={!isRunning}
              className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg transition-colors font-medium"
            >
              <Square size={18} /> Stop
            </button>
        </div>
      </div>

      {/* 3. Metric Cards Grid (Removed Uncertainty Card) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <MetricCard 
          title="Total Queue Length" 
          value={currentMetrics.total_queue} 
          unit="veh" 
          icon={<Car className="text-blue-400" />} 
        />
        <MetricCard 
          title="Avg Network Speed" 
          value={currentMetrics.avg_speed} 
          unit="m/s" 
          icon={<Zap className="text-yellow-400" />} 
        />
        <MetricCard 
          title="Total Waiting Time" 
          value={currentMetrics.total_waiting_time} 
          unit="s" 
          icon={<Clock className="text-red-400" />} 
        />
        <MetricCard 
          title="CO2 Emissions (Inst.)" 
          value={currentMetrics.total_co2} 
          unit="g/s" 
          icon={<Leaf className="text-green-400" />} 
        />
        <MetricCard 
          title="Simulation Step" 
          value={currentMetrics.step} 
          unit="t" 
          icon={<Activity className="text-purple-400" />} 
        />
      </div>

      {/* 4. Charts Grid (2x2) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Congestion (Queue Length)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dataHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} itemStyle={{ color: '#f8fafc' }} />
              <Line type="monotone" dataKey="total_queue" stroke="#60a5fa" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Traffic Flow (Speed)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dataHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} itemStyle={{ color: '#f8fafc' }} />
              <Line type="monotone" dataKey="avg_speed" stroke="#facc15" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Total Waiting Time (Delays)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dataHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} itemStyle={{ color: '#f8fafc' }} />
              <Line type="monotone" dataKey="total_waiting_time" stroke="#f87171" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Environmental Impact (CO2)">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dataHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155' }} itemStyle={{ color: '#f8fafc' }} />
              <Line type="monotone" dataKey="total_co2" stroke="#4ade80" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

// Sub-components with Types

interface MetricCardProps {
  title: string;
  value: number | string;
  unit: string;
  icon: React.ReactNode;
}

const MetricCard = ({ title, value, unit, icon }: MetricCardProps) => (
  <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 flex items-center justify-between hover:border-slate-500 transition-colors">
    <div>
      <p className="text-slate-400 text-sm font-medium uppercase tracking-wider">{title}</p>
      <p className="text-2xl font-bold mt-2">
        {value} <span className="text-slate-500 text-sm font-normal ml-1">{unit}</span>
      </p>
    </div>
    <div className="p-3 bg-slate-700/50 rounded-lg">
      {icon}
    </div>
  </div>
);

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
}

const ChartCard = ({ title, children }: ChartCardProps) => (
  <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 h-80 flex flex-col">
    <h3 className="text-slate-200 font-semibold mb-4">{title}</h3>
    <div className="flex-1 min-h-0 w-full">
      {children}
    </div>
  </div>
);

export default App;