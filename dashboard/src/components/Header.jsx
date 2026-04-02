import React from 'react';
import { Menu, Bell, Shield } from 'lucide-react';
import useStore from '../store/useStore';

export default function Header() {
  const { roverState, unacknowledgedCount } = useStore();

  const stateColors = {
    IDLE: 'bg-neutral-900 text-neutral-400 border-neutral-800',
    NAVIGATING: 'bg-blue-900/30 text-blue-400 border-blue-800',
    PATROLLING: 'bg-forest-900/30 text-forest-400 border-forest-800',
    RETURNING: 'bg-amber-900/30 text-amber-400 border-amber-800',
    STUCK: 'bg-red-900/30 text-red-500 border-red-800',
    CHARGING: 'bg-green-900/30 text-green-400 border-green-800',
    EMERGENCY: 'bg-neutral-100 text-neutral-900 border-neutral-100',
  };

  return (
    <header className="bg-surface/80 backdrop-blur-xl border-b border-border px-10 py-6 flex items-center justify-between z-10 relative">
      <div className="flex items-center gap-6">
        <button className="md:hidden p-3 rounded-2xl hover:bg-surface-hover text-text-secondary transition-colors border border-border">
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:block">
          <h2 className="text-xs font-black tracking-[0.4em] uppercase text-accent flex items-center gap-3 italic">
            <span className="w-8 h-px bg-accent/30"></span>
            Nexus_Ground_Control
          </h2>
        </div>
      </div>

      <div className="flex items-center gap-10">
        {/* State Badges */}
        <div className="hidden md:flex items-center gap-4 border-r border-border pr-10">
          <span className={`px-5 py-2 rounded-full text-[10px] font-black uppercase tracking-[0.2em] shadow-lg border ${stateColors[roverState.state] || stateColors.IDLE}`}>
            {roverState.state || 'IDLE'}
          </span>
          {roverState.is_charging && (
            <div className="px-5 py-2 rounded-full text-[10px] font-black uppercase tracking-[0.2em] bg-accent/10 text-accent border border-accent/20 flex items-center gap-3">
              <Zap className="w-3 h-3 animate-pulse" />
              SOLAR_SYNC
            </div>
          )}
        </div>

        {/* Action Icons */}
        <div className="flex items-center gap-6">
          <button className="p-3 rounded-2xl bg-surface-hover/50 hover:bg-accent hover:text-bg transition-all relative text-text-secondary border border-border shadow-inner group">
            <Bell className="w-5 h-5 group-hover:rotate-12 transition-transform" />
            {unacknowledgedCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-alert-red text-white text-[8px] font-black w-5 h-5 flex items-center justify-center rounded-full border-2 border-surface shadow-xl">
                {unacknowledgedCount}
              </span>
            )}
          </button>
          
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-accent to-accent-dim flex items-center justify-center text-bg text-sm font-black shadow-lg cursor-pointer hover:scale-110 transition-transform active:scale-95">
            KA
          </div>
        </div>
      </div>
    </header>
  );
}
