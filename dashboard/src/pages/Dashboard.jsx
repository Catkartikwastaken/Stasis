import React from 'react';
import { Battery, Thermometer, Satellite, Shield, StopCircle, RotateCcw, Play } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import TelemetryCard from '../components/TelemetryCard';
import useStore from '../store/useStore';
import { useTelemetry } from '../hooks/useTelemetry';
import { useAlerts } from '../hooks/useAlerts';
import { sendCommand } from '../hooks/useSocket';
import AlertBadge from '../components/AlertBadge';

export default function Dashboard() {
  const { roverState } = useTelemetry();
  const { alerts } = useAlerts();
  const telemetryHistory = useStore(s => s.telemetryHistory);

  const chartData = telemetryHistory.map((t, i) => ({
    idx: i,
    battery: t.battery || 0,
    temp: t.temp || t.temperature || 0,
  }));

  const recentAlerts = alerts.slice(0, 3);

  const handleCommand = (cmd) => {
    if (confirm(`Send ${cmd.toUpperCase()} command?`)) {
      sendCommand(cmd);
    }
  };

  return (
    <div className="space-y-10 animate-fade-in max-w-7xl mx-auto pb-24">
      <div className="flex items-center justify-between mb-4">
        <div className="flex flex-col">
           <div className="text-[10px] font-black tracking-[0.5em] text-accent uppercase mb-2 italic">Operation_Serenity</div>
           <h2 className="text-5xl font-black text-white lowercase italic tracking-tighter">forest.monitor</h2>
        </div>
        <div className="flex items-center gap-4 bg-surface/40 p-4 rounded-2xl border border-border backdrop-blur-md">
           <div className="w-3 h-3 rounded-full bg-accent animate-pulse shadow-[0_0_15px_var(--color-accent)]"></div>
           <span className="text-xs font-bold text-text-primary lowercase italic">uplink_synchronized</span>
        </div>
      </div>

      {/* Telemetry Overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
        <TelemetryCard
          title="System_Power"
          value={`${roverState.battery_percent || 0}`}
          unit="%"
          subtitle={`${roverState.battery_voltage?.toFixed(1) || '0.0'}V_DC`}
          icon={Zap}
          color="accent"
        />
        <TelemetryCard
          title="Ambient_Thermal"
          value={`${roverState.temperature?.toFixed(1) || '0.0'}`}
          unit="°C"
          icon={Thermometer}
          color="text-secondary"
        />
        <TelemetryCard
          title="Global_Fix"
          value={roverState.lat ? 'FIXED' : 'SCANNING'}
          subtitle={`${roverState.lat?.toFixed(4) || '-'}, ${roverState.lon?.toFixed(4) || '-'}`}
          icon={Trees}
          color="accent"
        />
        <TelemetryCard
          title="Heartbeat"
          value={roverState.state || 'IDLE'}
          icon={Leaf}
          color="text-secondary"
        />
      </div>

      {/* Data Visualization */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Map Card */}
        <div className="bg-surface/60 rounded-main border border-border overflow-hidden shadow-2xl flex flex-col group transition-all hover:bg-surface/80 hover:border-accent/40 relative">
          <div className="p-8 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-4">
               <div className="w-10 h-10 rounded-2xl bg-accent/10 flex items-center justify-center">
                  <Map className="w-5 h-5 text-accent" />
               </div>
               <h3 className="font-black text-xs uppercase tracking-[0.3em] text-white italic">Tactical_Forest_Map</h3>
            </div>
          </div>
          <div className="flex-1 min-h-[400px] relative">
            <div className="absolute inset-0 pointer-events-none border-[20px] border-surface/40 z-[400] rounded-main"></div>
            <MapContainer
              center={[roverState.lat || 0, roverState.lon || 0]}
              zoom={15}
              className="w-full h-full"
              scrollWheelZoom={false}
            >
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" className="grayscale invert contrast-[1.1] brightness-[0.7] opacity-60 hue-rotate-[90deg] saturate-[0.5]" />
              {roverState.lat && (
                <Marker position={[roverState.lat, roverState.lon]}>
                  <Popup>STASIS_MOBILE_UNIT</Popup>
                </Marker>
              )}
            </MapContainer>
          </div>
        </div>

        {/* Telemetry Stream */}
        <div className="bg-surface/60 rounded-main border border-border p-10 shadow-2xl relative overflow-hidden group hover:bg-surface/80 transition-all hover:border-accent/40">
          <div className="flex items-center justify-between mb-12">
             <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-2xl bg-accent/10 flex items-center justify-center">
                   <Activity className="w-5 h-5 text-accent" />
                </div>
                <h3 className="font-black text-xs uppercase tracking-[0.3em] text-white italic">Live_Uplink_Data</h3>
             </div>
             <span className="text-[10px] font-bold text-accent/60 uppercase tracking-widest italic animate-pulse group-hover:text-accent">60hz_sync</span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="5 5" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="idx" hide />
              <YAxis yAxisId="left" hide domain={[3.0, 4.5]} />
              <YAxis yAxisId="right" hide />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: '1rem', color: '#fff' }}
                itemStyle={{ color: '#fff' }}
              />
              <Line yAxisId="left" type="monotone" dataKey="battery" stroke="var(--color-text-primary)" strokeWidth={4} dot={false} isAnimationActive={false} />
              <Line yAxisId="right" type="monotone" dataKey="temp" stroke="var(--color-accent)" strokeWidth={4} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Operations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Missions Logs */}
        <div className="bg-surface/60 rounded-main border border-border p-10 shadow-2xl relative">
          <div className="flex items-center justify-between mb-10">
            <h3 className="font-black text-xs uppercase tracking-[0.3em] text-white italic">Mission_Journal</h3>
            <a href="#/alerts" className="text-xs font-black text-accent hover:text-white transition-all underline underline-offset-8">explore_all</a>
          </div>
          {recentAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 bg-bg/20 rounded-2xl border border-dashed border-border border-accent/20">
              <Sparkles className="w-10 h-10 text-accent/20 mb-4" />
              <span className="text-xs font-black text-text-dim uppercase tracking-[0.4em] italic">Forest_Quiet</span>
            </div>
          ) : (
            <div className="space-y-6">
              {recentAlerts.map((alert, i) => (
                <div key={i} className="flex items-center justify-between p-6 rounded-2xl border border-border bg-bg/30 hover:bg-surface-hover hover:border-accent/40 hover:scale-[1.02] transition-all group cursor-pointer">
                  <div className="flex items-center gap-6">
                    <AlertBadge type={alert.type} small />
                    <div className="flex flex-col">
                       <span className="text-sm font-bold text-text-primary group-hover:text-white transition-colors lowercase italic tracking-tight">
                         Detection @ {alert.lat?.toFixed(3)}, {alert.lon?.toFixed(3)}
                       </span>
                       <span className="text-[10px] text-text-dim uppercase font-black tracking-widest mt-1">Confirmed_Anomaly</span>
                    </div>
                  </div>
                  <span className="text-xs font-black text-accent/40 group-hover:text-accent transition-colors">{alert.timestamp?.slice(11, 16)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Command Overrides */}
        <div className="bg-surface/60 rounded-main border border-border p-10 shadow-2xl relative group">
          <h3 className="font-black text-xs uppercase tracking-[0.3em] text-white mb-10 italic">Force_Overrides</h3>
          <div className="grid grid-cols-3 gap-8">
            <button
              onClick={() => handleCommand('stop')}
              className="group flex flex-col items-center gap-6 p-10 rounded-2xl border border-border bg-bg/30 hover:bg-alert-red hover:text-white transition-all active:scale-95"
            >
              <StopCircle className="w-10 h-10 transition-transform group-hover:scale-125" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">Abort</span>
            </button>
            <button
              onClick={() => handleCommand('return')}
              className="group flex flex-col items-center gap-6 p-10 rounded-2xl border border-border bg-bg/30 hover:bg-accent hover:text-bg transition-all active:scale-95"
            >
              <RotateCcw className="w-10 h-10 transition-transform group-hover:scale-125" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">Return</span>
            </button>
            <button
              onClick={() => handleCommand('resume')}
              className="group flex flex-col items-center gap-6 p-10 rounded-2xl border border-border bg-bg/30 hover:bg-white hover:text-bg transition-all active:scale-95"
            >
              <Play className="w-10 h-10 transition-transform group-hover:scale-125" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">Resume</span>
            </button>
          </div>
          {/* Decorative Corner Icon */}
          <div className="absolute bottom-6 right-6 opacity-5 group-hover:opacity-20 transition-opacity"><Leaf className="w-16 h-16 text-accent" /></div>
        </div>
      </div>
    </div>
  );
}
