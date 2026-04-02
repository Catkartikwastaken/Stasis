import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Map, Camera, AlertTriangle, MessageSquare, Settings, Radio } from 'lucide-react';
import useStore from '../store/useStore';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/map', icon: Map, label: 'Live Map' },
  { path: '/camera', icon: Camera, label: 'Camera' },
  { path: '/alerts', icon: AlertTriangle, label: 'Alerts' },
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const { connected, unacknowledgedCount } = useStore();

  return (
    <aside className="hidden md:flex flex-col w-72 bg-surface/80 backdrop-blur-xl border-r border-border text-text-primary h-full transition-all duration-700">
      {/* Logo Area */}
      <div className="flex flex-col items-center gap-4 px-8 py-10 border-b border-border bg-gradient-to-b from-accent/5 to-transparent">
        <div className="w-16 h-16 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center shadow-[0_0_30px_rgba(74,222,128,0.1)] group">
          <Trees className="w-8 h-8 text-accent group-hover:scale-110 transition-transform" />
        </div>
        <div className="text-center">
          <h1 className="text-2xl font-black tracking-[-0.05em] text-white lowercase italic">stasis.</h1>
          <p className="text-[10px] uppercase font-bold text-accent tracking-[0.4em] mt-1 opacity-60 italic">Forest Uplink</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-10 px-6 space-y-3">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              `flex items-center gap-4 px-6 py-4 rounded-main font-bold text-sm tracking-wide lowercase italic transition-all duration-500
              ${isActive
                ? 'bg-accent text-bg shadow-[0_10px_20px_rgba(74,222,128,0.2)] scale-105'
                : 'text-text-secondary hover:bg-surface-hover hover:text-white border border-transparent'}`
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
            {label === 'Alerts' && unacknowledgedCount > 0 && (
              <span className="ml-auto bg-alert-red text-white text-[10px] font-black w-6 h-6 flex items-center justify-center rounded-full shadow-lg border border-white/20">
                {unacknowledgedCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Connection Info */}
      <div className="p-8 border-t border-border bg-black/10">
        <div className="p-6 rounded-2xl bg-bg/50 border border-border flex flex-col gap-3 group">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black text-text-dim uppercase tracking-widest italic">Signal_Status</span>
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-accent animate-pulse shadow-[0_0_10px_var(--color-accent)]' : 'bg-alert-red'}`} />
          </div>
          <p className="text-xs font-bold text-text-primary tracking-tight">
            {connected ? 'Syncing_S3_C3' : 'Link_Lost'}
          </p>
        </div>
      </div>
    </aside>
  );
}
