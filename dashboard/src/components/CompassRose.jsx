import React from 'react';

export default function CompassRose({ heading = 0, size = 100 }) {
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const r = size / 2 - 12;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background circle */}
        <circle cx={size/2} cy={size/2} r={size/2-2} fill="#1A2E22" stroke="#40916C" strokeWidth="1.5" />

        {/* Direction labels */}
        {directions.map((dir, i) => {
          const angle = (i * 45 - 90) * Math.PI / 180;
          const x = size/2 + (r - 4) * Math.cos(angle);
          const y = size/2 + (r - 4) * Math.sin(angle);
          return (
            <text key={dir} x={x} y={y}
              textAnchor="middle" dominantBaseline="central"
              fill={dir === 'N' ? '#DC2626' : '#74C69D'}
              fontSize={dir.length === 1 ? '10' : '7'}
              fontWeight={dir === 'N' ? 'bold' : 'normal'}
              fontFamily="Inter, sans-serif">
              {dir}
            </text>
          );
        })}

        {/* Tick marks */}
        {Array.from({ length: 36 }).map((_, i) => {
          const angle = (i * 10 - 90) * Math.PI / 180;
          const isMain = i % 9 === 0;
          const r1 = r - (isMain ? 18 : 14);
          const r2 = r - 10;
          return (
            <line key={i}
              x1={size/2 + r1 * Math.cos(angle)} y1={size/2 + r1 * Math.sin(angle)}
              x2={size/2 + r2 * Math.cos(angle)} y2={size/2 + r2 * Math.sin(angle)}
              stroke={isMain ? '#74C69D' : '#2D6A4F'} strokeWidth={isMain ? 1.5 : 0.5} />
          );
        })}

        {/* Heading arrow */}
        <g transform={`rotate(${heading}, ${size/2}, ${size/2})`}>
          <polygon
            points={`${size/2},${size/2 - r + 20} ${size/2 - 6},${size/2 + 5} ${size/2 + 6},${size/2 + 5}`}
            fill="#DC2626" opacity="0.9" />
          <polygon
            points={`${size/2},${size/2 + r - 20} ${size/2 - 4},${size/2 - 3} ${size/2 + 4},${size/2 - 3}`}
            fill="#FFFFFF" opacity="0.4" />
        </g>

        {/* Center dot */}
        <circle cx={size/2} cy={size/2} r="3" fill="#74C69D" />
      </svg>
      <p className="text-xs text-gray-400 font-mono">{heading.toFixed(0)}°</p>
    </div>
  );
}
