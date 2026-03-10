import React, { useState } from 'react';
import { Lock, User, ArrowRight, Network } from 'lucide-react';

interface LoginPageProps {
    onLogin: () => void;
}

export default function LoginPage({ onLogin }: LoginPageProps) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (username === 'admin' && password === 'admin') {
            setError('');
            onLogin();
        } else {
            setError('Invalid username or password');
        }
    };

    return (
        <div className="min-h-screen bg-[#0B1120] flex flex-col justify-center items-center p-4 relative overflow-hidden font-sans">
            {/* Background decorations */}
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl -z-10"></div>
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl -z-10"></div>

            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-xl shadow-indigo-900/20 p-8 backdrop-blur-sm relative z-10">
                <div className="flex flex-col items-center mb-8">
                    <div className="w-12 h-12 bg-gradient-to-br from-indigo-600 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/20 mb-4">
                        <Network size={28} className="text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Welcome Back</h1>
                    <p className="text-slate-400 text-sm mt-1">Sign in to MultiAgent.ai platform</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Username</label>
                        <div className="relative">
                            <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder-slate-600"
                                placeholder="Enter username"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Password</label>
                        <div className="relative">
                            <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder-slate-600"
                                placeholder="Enter password"
                                required
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="text-red-400 text-sm text-center bg-red-400/10 py-2 rounded-lg border border-red-500/20">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium py-3 rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-500/25 active:scale-[0.98]"
                    >
                        Sign In
                        <ArrowRight size={18} />
                    </button>
                </form>

                <div className="mt-6 text-center text-xs text-slate-500">
                    <p>Secure Agent Control Dashboard</p>
                    <div className="mt-2 text-slate-700">Hint: admin / admin</div>
                </div>
            </div>
        </div>
    );
}
