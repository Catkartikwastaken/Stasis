import React from 'react';

export default function BatteryGauge({ voltage = 0, percent = 0, isCharging = false }) {
  const getColor = () => {
    if (percent > 60) return '#40916C';
    if (percent > 30) return '#D97706';
    return '#DC2626';
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-16 h-32">
        {/* Battery outline */}
        <div className="absolute inset-0 border-2 border-gray-300 rounded-lg">
          {/* Terminal */}
          <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-6 h-2 bg-gray-300 rounded-t-sm" />
          {/* Fill */}
          <div
            className="absolute bottom-0 left-0 right-0 rounded-b-md transition-all duration-500"
            style={{
              height: `${Math.max(2, percent)}%`,
              backgroundColor: getColor(),
              opacity: isCharging ? undefined : 0.8,
            }}
          />
          {isCharging && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-white text-lg font-bold drop-shadow-md animate-pulse">⚡</span>
            </div>
          )}
        </div>
      </div>
      <div className="text-center">
        <p className="text-lg font-bold font-mono" style={{ color: getColor() }}>{percent}%</p>
        <p className="text-xs text-gray-400 font-mono">{voltage.toFixed(1)}V</p>
      </div>
    </div>
  );
}
