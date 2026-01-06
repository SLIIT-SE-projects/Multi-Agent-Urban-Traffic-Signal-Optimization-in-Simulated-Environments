import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Cpu,
  Activity,
  Settings,
  Network,
  Search,
  Bell,
  ChevronRight
} from 'lucide-react';

// Assuming you have this component in a separate file
import GNNDashboard from './modules/gnn/GNNDashboard';
import { MPCDashboard } from './modules/mpc/MPCDashboard';

// --- 1. SIDEBAR COMPONENT (Ported from Code 1) ---
const Sidebar = () => (
  <aside className="w-64 border-r border-slate-800 bg-[#0B1120] flex flex-col h-screen sticky top-0">
    {/* Logo Section */}
    <div className="p-6 flex items-center gap-3">
      <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-violet-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-500/20">
        <Network size={20} className="text-white" />
      </div>
      <span className="font-bold text-lg tracking-tight text-slate-100">
        MultiAgent<span className="text-indigo-400">.ai</span>
      </span>
    </div>

    {/* Navigation Links */}
    <nav className="flex-1 px-3 space-y-1 mt-6 overflow-y-auto">
      <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
        Platform
      </p>

      <SidebarItem to="/overview" icon={<LayoutDashboard size={18} />} label="System Overview" />
      <SidebarItem to="/gnn" icon={<Cpu size={18} />} label="GNN Optimizer" />
      <SidebarItem to="/mpc" icon={<Activity size={18} />} label="MPC Control" />

      <p className="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mt-8 mb-2">
        Settings
      </p>
      <SidebarItem to="/config" icon={<Settings size={18} />} label="System Config" />
    </nav>
  </aside>
);

// --- 2. SIDEBAR ITEM (Adapted for React Router) ---
const SidebarItem = ({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${isActive
        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20'
        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
      }`
    }
  >
    {icon}
    {label}
  </NavLink>
);

// --- 3. TOP HEADER (Optional: To complete the look) ---
const TopHeader = () => (
  <header className="h-16 border-b border-slate-800 bg-[#0B1120]/50 backdrop-blur-sm flex items-center justify-between px-8 sticky top-0 z-10">
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <span>Platform</span>
      <ChevronRight size={14} />
      <span className="text-slate-200 font-medium capitalize">Dashboard</span>
    </div>
    <div className="flex items-center gap-4">
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search..."
          className="bg-slate-900 border border-slate-800 rounded-full pl-9 pr-4 py-1.5 text-xs focus:outline-none w-48 transition-all focus:border-indigo-500 text-slate-200"
        />
      </div>
      <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center hover:bg-slate-700 cursor-pointer transition-colors">
        <Bell size={16} className="text-slate-400" />
      </div>
    </div>
  </header>
);

// --- 4. MAIN APP LAYOUT ---
export default function App() {
  return (
    <BrowserRouter>
      {/* We use flex-row here. 
         Sidebar is flex-none (fixed width).
         Main is flex-1 (takes remaining space).
      */}
      <div className="flex h-screen bg-[#0B1120] text-slate-100 font-sans overflow-hidden">
        <Sidebar />

        <main className="flex-1 flex flex-col min-w-0">
          <TopHeader />

          <div className="flex-1 overflow-y-auto p-8">
            <Routes>
              <Route path="/" element={<Navigate to="/overview" />} />

              <Route path="/overview" element={
                <div className="p-10 border-2 border-dashed border-slate-800 rounded-2xl bg-slate-900/20 text-center">
                  <h1 className="text-2xl font-bold text-white">System Overview</h1>
                  <p className="text-slate-500 mt-2">Aggregated metrics would appear here.</p>
                </div>
              } />

              {/* IMPORTANT: Since App.tsx now handles the Sidebar, 
                  make sure GNNDashboard does NOT render its own Sidebar.
                  It should only render the content part.
              */}
              <Route path="/gnn/*" element={<GNNDashboard />} />

              <Route path="/mpc" element={<MPCDashboard />} />

              <Route path="/config" element={
                <div className="p-10 border-2 border-dashed border-slate-800 rounded-2xl bg-slate-900/20 text-center">
                  <h1 className="text-2xl font-bold text-white">System Configuration</h1>
                </div>
              } />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}