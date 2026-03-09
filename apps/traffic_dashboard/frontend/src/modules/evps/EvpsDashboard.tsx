import { useState, useEffect } from 'react';
import { useEvpsSocket } from './hooks/useEvpsSocket';
import { Activity, Zap, Car, AlertTriangle, CheckCircle, Play, Square, MapPin, Sun, Moon, Shuffle } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

const createMarkerIcon = (color: string) => {
    return L.divIcon({
        className: 'custom-icon',
        html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.5);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
};

const startIcon = createMarkerIcon('#10b981'); // Emerald
const endIcon = createMarkerIcon('#f43f5e'); // Rose

const MapClickHandler = ({ onMapClick }: { onMapClick: (lat: number, lon: number) => void }) => {
    useMapEvents({
        click(e) {
            onMapClick(e.latlng.lat, e.latlng.lng);
        }
    });
    return null;
};

// Using the same API base as SystemOverview for the toggle fetch
const BASE_URL = '/api';

export default function EvpsDashboard() {
    const { isConnected, metrics } = useEvpsSocket();
    const [toast, setToast] = useState<{ type: 'error' | 'success', message: string } | null>(null);
    const [startCoords, setStartCoords] = useState<{ lat: number, lon: number } | null>(null);
    const [endCoords, setEndCoords] = useState<{ lat: number, lon: number } | null>(null);
    const [isDispatching, setIsDispatching] = useState(false);
    const [networkGeoJson, setNetworkGeoJson] = useState<any>(null);
    const [customEvId, setCustomEvId] = useState('');
    const [customRandomEvId, setCustomRandomEvId] = useState('');
    const [isDispatchingRandom, setIsDispatchingRandom] = useState(false);
    const [isMapDark, setIsMapDark] = useState(true);

    // Fetch network topology GeoJSON on mount
    useEffect(() => {
        const fetchNetworkGeojson = async () => {
            try {
                const response = await fetch(`${BASE_URL}/network/geojson`);
                if (response.ok) {
                    const data = await response.json();
                    setNetworkGeoJson(data);
                } else {
                    console.error('Failed to fetch network GeoJSON:', response.statusText);
                }
            } catch (error) {
                console.error('Error fetching network GeoJSON:', error);
            }
        };

        fetchNetworkGeojson();
    }, []);

    // Clear toasts after 5 seconds
    useEffect(() => {
        if (toast) {
            const timer = setTimeout(() => setToast(null), 5000);
            return () => clearTimeout(timer);
        }
    }, [toast]);

    const { active_evs = 0, override_junctions = [], evps_status = 'Idle', fleet = [] } = metrics;

    const isSystemActive = evps_status === 'Active';

    // Default Map center
    const centerLat = metrics.lat || 7.173;
    const centerLon = metrics.lon || 79.885;

    const handleMapClick = (lat: number, lon: number) => {
        if (!startCoords) {
            setStartCoords({ lat, lon });
        } else if (!endCoords) {
            setEndCoords({ lat, lon });
        } else {
            setStartCoords({ lat, lon });
            setEndCoords(null);
        }
    };

    const handleDispatch = async () => {
        if (!startCoords || !endCoords) return;
        setIsDispatching(true);
        try {
            const response = await fetch(`${BASE_URL}/evps/spawn_geo`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_lat: startCoords.lat,
                    start_lon: startCoords.lon,
                    end_lat: endCoords.lat,
                    end_lon: endCoords.lon,
                    ev_id: customEvId.trim() || undefined
                })
            });
            const result = await response.json();
            if (result.status === 'success') {
                setStartCoords(null);
                setEndCoords(null);
                setCustomEvId('');
                setToast({ type: 'success', message: result.message || 'Successfully dispatched EV.' });
            } else {
                console.error("Failed to spawn EV:", result.message);
                setToast({ type: 'error', message: "Dispatch failed: " + result.message });
            }
        } catch (e) {
            console.error("API error spawning EV:", e);
        } finally {
            setIsDispatching(false);
        }
    };

    const handleRandomDispatch = async () => {
        setIsDispatchingRandom(true);
        try {
            const response = await fetch(`${BASE_URL}/evps/spawn_random`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ev_id: customRandomEvId.trim() || undefined
                })
            });
            const result = await response.json();
            if (result.status === 'success') {
                setCustomRandomEvId('');
                setToast({ type: 'success', message: result.message || 'Successfully dispatched random EV.' });
            } else {
                console.error("Failed to spawn random EV:", result.message);
                setToast({ type: 'error', message: "Quick dispatch failed: " + result.message });
            }
        } catch (e) {
            console.error("API error spawning random EV:", e);
        } finally {
            setIsDispatchingRandom(false);
        }
    };

    // Toggle function mapping to the real-time isSystemActive state
    const toggleEvps = async () => {
        try {
            const newState = !isSystemActive;
            await fetch(`${BASE_URL}/evps/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enable: newState })
            });
            // State will automatically update on next websocket tick
        } catch (e) {
            console.error("Failed to toggle EVPS", e);
        }
    };

    // Metric Component Helper
    const StatCard = ({ title, value, unit, icon, color, subtext }: any) => (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex items-start justify-between">
            <div>
                <p className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">{title}</p>
                <h3 className="text-2xl font-bold text-white">
                    {value} {unit && <span className="text-sm font-normal text-slate-500">{unit}</span>}
                </h3>
                {subtext && <p className="text-xs text-slate-500 mt-2">{subtext}</p>}
            </div>
            <div className={`p-2.5 rounded-lg bg-slate-800/50 ${color} text-white`}>
                {icon}
            </div>
        </div>
    );

    return (
        <div className="space-y-6 animate-in fade-in duration-500 relative">
            {/* Custom Toast Notification */}
            {toast && (
                <div className={`fixed top-4 right-4 z-50 p-4 rounded-xl shadow-2xl flex items-center gap-3 transition-all duration-300 transform translate-y-0 opacity-100 ${toast.type === 'error' ? 'bg-rose-500/90 text-white' : 'bg-emerald-500/90 text-white'}`}>
                    {toast.type === 'error' ? <AlertTriangle size={20} /> : <CheckCircle size={20} />}
                    <p className="font-medium">{toast.message}</p>
                    <button onClick={() => setToast(null)} className="ml-2 hover:opacity-75">
                        <Square size={16} className="fill-current" />
                    </button>
                </div>
            )}

            {/* Header / Status */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
                        EVPS Dashboard
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${isConnected ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' : 'border-rose-500/50 text-rose-400 bg-rose-500/10'}`}>
                            {isConnected ? 'Online' : 'Offline'}
                        </span>
                    </h1>
                    <p className="text-slate-400 text-sm">Emergency Vehicle Preemption System Metrics & Fleet Status</p>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={toggleEvps}
                        disabled={!isConnected}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg ${isSystemActive
                            ? 'bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20'
                            : 'bg-emerald-600 text-white hover:bg-emerald-500 shadow-emerald-500/20'
                            } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                        {isSystemActive ? <><Square size={16} fill="currentColor" /> Stop EVPS</> : <><Play size={16} fill="currentColor" /> Start EVPS</>}
                    </button>
                </div>
            </div>

            {/* Top Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <StatCard
                    title="Active Emergency Vehicles"
                    value={active_evs}
                    icon={<Car size={18} />}
                    color="text-amber-500"
                    subtext="EVs currently requesting priority"
                />
                <StatCard
                    title="Active Green Waves"
                    value={override_junctions.length}
                    icon={<Zap size={18} />}
                    color="text-emerald-500"
                    subtext="Signals overridden for EVs"
                />
                <StatCard
                    title="System Status"
                    value={evps_status}
                    icon={<Activity size={18} />}
                    color={isSystemActive ? "text-emerald-500" : "text-slate-500"}
                    subtext="Overall EVPS operational state"
                />
            </div>

            {/* Live Fleet Telemetry Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mt-8">
                <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                    <h3 className="text-white font-semibold flex items-center gap-2">
                        <AlertTriangle size={18} className="text-amber-500" />
                        Live Fleet Telemetry
                    </h3>
                </div>

                {fleet.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">
                        <Car className="mx-auto h-12 w-12 text-slate-700 mb-3 opacity-50" />
                        <p>No emergency vehicles currently active in the simulation.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto border-t-0">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-slate-400 uppercase bg-slate-800/50 border-b border-slate-800">
                                <tr>
                                    <th className="px-6 py-4 font-medium">Vehicle ID</th>
                                    <th className="px-6 py-4 font-medium text-right">Current Speed</th>
                                    <th className="px-6 py-4 font-medium text-center">Dispatch Priority</th>
                                    <th className="px-6 py-4 font-medium text-center">Safety Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {fleet.map((ev, idx) => (
                                    <tr key={ev.id || idx} className="border-b border-slate-800 hover:bg-slate-800/30 transition-colors">
                                        <td className="px-6 py-4 font-medium text-white flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                                                <Car size={14} className="text-indigo-400" />
                                            </div>
                                            {ev.id}
                                        </td>
                                        <td className="px-6 py-4 text-slate-300 text-right font-mono">
                                            {(ev.speed || 0).toFixed(1)} <span className="text-slate-500 text-xs ml-1">km/h</span>
                                        </td>
                                        <td className="px-6 py-4 text-center border-l-transparent">
                                            <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                                Level {ev.priority || 1}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex justify-center">
                                                {ev.safety_blocked ? (
                                                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                                        <AlertTriangle size={14} />
                                                        BLOCKED / DENIED
                                                    </span>
                                                ) : (
                                                    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                        <CheckCircle size={14} />
                                                        SECURE / PROCEEDING
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-1 text-slate-400 text-xs">
                                                <MapPin size={12} />
                                                {(ev as any).lat?.toFixed(4)}, {(ev as any).lon?.toFixed(4)}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>


            {/* Quick Dispatch */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mt-8">
                <div className="p-5 flex items-center justify-between">
                    <div>
                        <h3 className="text-white font-semibold flex items-center gap-2">
                            <Shuffle size={18} className="text-indigo-400" />
                            Quick Dispatch (Random Route)
                        </h3>
                        <p className="text-sm text-slate-400 mt-1">
                            Instantly inject a new Emergency Vehicle on a random valid route.
                        </p>
                    </div>
                    <div className="flex gap-3 items-center">
                        <input
                            type="text"
                            placeholder="Custom EV ID (Optional)"
                            value={customRandomEvId}
                            onChange={(e) => setCustomRandomEvId(e.target.value)}
                            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors w-48"
                        />
                        <button
                            onClick={handleRandomDispatch}
                            disabled={isDispatchingRandom}
                            className="px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            <Zap size={16} />
                            {isDispatchingRandom ? 'Dispatching...' : 'Dispatch Random EV'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Dynamic EV Spawner Map */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden mt-8">
                <div className="p-5 border-b border-slate-800 flex items-center justify-between">
                    <div>
                        <h3 className="text-white font-semibold flex items-center gap-2">
                            <MapPin size={18} className="text-indigo-400" />
                            Dynamic EV Dispatch
                        </h3>
                        <p className="text-sm text-slate-400 mt-1">
                            Click on the map to set Start (Green) and Destination (Red) points for a new Emergency Vehicle.
                        </p>
                    </div>
                    <div className="flex gap-3 items-center">
                        <button
                            onClick={() => setIsMapDark(!isMapDark)}
                            className="p-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-400 hover:text-white hover:border-slate-500 transition-colors flex items-center justify-center"
                            title={isMapDark ? "Switch to Light Map" : "Switch to Dark Map"}
                        >
                            {isMapDark ? <Moon size={20} /> : <Sun size={20} />}
                        </button>
                        <input
                            type="text"
                            placeholder="Custom EV ID (Optional)"
                            value={customEvId}
                            onChange={(e) => setCustomEvId(e.target.value)}
                            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors w-48"
                        />
                        {(startCoords || endCoords) && (
                            <button
                                onClick={() => { setStartCoords(null); setEndCoords(null); }}
                                className="px-4 py-2 rounded-lg font-semibold text-sm transition-all text-slate-400 hover:text-white hover:bg-slate-800"
                            >
                                Clear
                            </button>
                        )}
                        <button
                            onClick={handleDispatch}
                            disabled={!startCoords || !endCoords || isDispatching}
                            className="px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isDispatching ? 'Dispatching...' : 'Dispatch EV'}
                        </button>
                    </div>
                </div>
                <div className="h-[400px] w-full relative z-0">
                    <MapContainer center={[centerLat, centerLon]} zoom={13} style={{ height: '100%', width: '100%' }}>
                        <TileLayer
                            url={isMapDark ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png' : 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'}
                            attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
                        />
                        <MapClickHandler onMapClick={handleMapClick} />
                        {startCoords && (
                            <Marker position={[startCoords.lat, startCoords.lon]} icon={startIcon}>
                                <Popup>Start Location</Popup>
                            </Marker>
                        )}
                        {endCoords && (
                            <Marker position={[endCoords.lat, endCoords.lon]} icon={endIcon}>
                                <Popup>Destination</Popup>
                            </Marker>
                        )}
                        {networkGeoJson && (
                            <GeoJSON
                                data={networkGeoJson}
                                style={{ color: '#00e5ff', weight: 3, opacity: 0.8 }}
                            />
                        )}
                    </MapContainer>
                </div>
            </div>

        </div>
    );
}
