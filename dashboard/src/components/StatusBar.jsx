import React from 'react';
import { MapPin, Thermometer, Battery, Signal } from 'lucide-react';
import useStore from '../store/useStore';

export default function StatusBar() {
  const { roverState, connected } = useStore();

  return (
    <div className="bg-surface/80 backdrop-blur-md border-t border-border px-10 py-4 flex items-center justify-between text-[10px] font-black tracking-[0.3em] uppercase overflow-x-auto gap-12 relative z-20 italic">
      <div className="flex items-center gap-4 whitespace-nowrap">
        <MapPin className="w-4 h-4 text-accent" />
        <span className="text-text-primary">
          Loc_Sync: {roverState.lat?.toFixed(5)} / {roverState.lon?.toFixed(5)}
        </span>
      </div>
      <div className="flex items-center gap-4 whitespace-nowrap">
        <Zap className="w-4 h-4 text-accent" />
        <span className={roverState.battery_low ? 'text-alert-red animate-pulse' : 'text-text-primary'}>
          Power_Bus: {roverState.battery_voltage?.toFixed(1)}V [{roverState.battery_percent || 0}%]
        </span>
      </div>
      <div className="flex items-center gap-4 whitespace-nowrap">
        <Trees className="w-4 h-4 text-accent" />
        <span className="text-text-primary">Environ_Temp: {roverState.temperature?.toFixed(1)}°C</span>
      </div>
      <div className="flex items-center gap-4 whitespace-nowrap">
        <Leaf className={`w-4 h-4 ${connected ? 'text-accent animate-bounce' : 'text-alert-red'}`} />
        <span className={connected ? 'text-accent' : 'text-alert-red'}>
          {connected ? 'Uplink_Established' : 'Link_Secured_Offline'}
        </span>
      </div>
    </div>
  );
}
