import React from 'react';

const typeColors = {
  HUMAN: 'bg-red-100 text-red-700 border-red-200',
  STUCK: 'bg-amber-100 text-amber-700 border-amber-200',
  LOW_BATTERY: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  TILT: 'bg-orange-100 text-orange-700 border-orange-200',
};

export default function AlertBadge({ type, small = false }) {
  const colors = typeColors[type] || 'bg-gray-100 text-gray-600 border-gray-200';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full border font-semibold
      ${small ? 'text-[10px]' : 'text-xs'} ${colors}`}>
      {type || 'UNKNOWN'}
    </span>
  );
}
