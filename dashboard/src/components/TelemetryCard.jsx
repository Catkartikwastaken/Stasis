import React from 'react';

export default function TelemetryCard({ title, value, unit, icon: Icon, color = 'forest-500', subtitle }) {
  return (
    <div className="bg-surface/60 backdrop-blur-md rounded-main border border-border p-8 shadow-2xl hover:bg-surface/80 hover:border-accent/40 transition-all animate-fade-in flex flex-col justify-between relative group overflow-hidden">
      <div className="flex items-center justify-between mb-8 relative z-10">
        <p className="text-[10px] font-black uppercase tracking-[0.3em] text-text-dim italic font-sans">{title}</p>
        {Icon && (
          <div className="w-12 h-12 rounded-2xl bg-accent/5 border border-accent/20 flex items-center justify-center group-hover:scale-110 transition-transform">
            <Icon className={`w-5 h-5 text-${color === 'accent' ? 'accent' : 'text-secondary'}`} />
          </div>
        )}
      </div>
      <div className="relative z-10">
        <p className="text-5xl font-black tracking-tight text-white italic">
          {value}
          {unit && <span className="text-sm font-bold tracking-normal text-text-dim ml-3 uppercase">{unit}</span>}
        </p>
        {subtitle && <p className="text-[10px] font-black text-accent mt-4 tracking-[0.2em] uppercase italic opacity-60 group-hover:opacity-100 transition-opacity">{subtitle}</p>}
      </div>
      {/* Soft Bottom Glow */}
      <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-accent/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
    </div>
  );
}
