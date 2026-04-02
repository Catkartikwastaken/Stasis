import React, { useState } from 'react';
import { Filter, Check, Download, ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import AlertBadge from '../components/AlertBadge';
import { useAlerts } from '../hooks/useAlerts';

const ALERT_TYPES = ['All', 'HUMAN', 'STUCK', 'LOW_BATTERY', 'TILT'];

export default function Alerts() {
  const { alerts, unacknowledgedCount, acknowledgeAlert } = useAlerts();
  const [filter, setFilter] = useState('All');
  const [expandedId, setExpandedId] = useState(null);

  const filtered = filter === 'All' ? alerts : alerts.filter(a => a.type === filter);
  const todayCount = alerts.filter(a => {
    const today = new Date().toISOString().slice(0, 10);
    return a.timestamp?.startsWith(today);
  }).length;

  const exportCSV = () => {
    const headers = 'ID,Timestamp,Type,Lat,Lon,Acknowledged,Notes\n';
    const rows = alerts.map(a =>
      `${a.id},"${a.timestamp}","${a.type}",${a.lat},${a.lon},${a.acknowledged},"${a.notes || ''}"`
    ).join('\n');
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `stasis-alerts-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-forest-800">Alerts</h2>
        <button onClick={exportCSV} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200">
          <Download className="w-4 h-4" /> Export CSV
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex gap-4">
        <div className="bg-white rounded-lg border px-4 py-2 text-center">
          <p className="text-2xl font-bold font-mono text-forest-600">{todayCount}</p>
          <p className="text-xs text-gray-400">Today</p>
        </div>
        <div className="bg-white rounded-lg border px-4 py-2 text-center">
          <p className="text-2xl font-bold font-mono text-alert-red">{unacknowledgedCount}</p>
          <p className="text-xs text-gray-400">Unacknowledged</p>
        </div>
        <div className="bg-white rounded-lg border px-4 py-2 text-center">
          <p className="text-2xl font-bold font-mono text-gray-600">{alerts.length}</p>
          <p className="text-xs text-gray-400">Total</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {ALERT_TYPES.map(type => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
              ${filter === type ? 'bg-forest-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        {filtered.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No alerts matching filter</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map(alert => (
              <div key={alert.id} className="hover:bg-gray-50 transition-colors">
                <div
                  className="flex items-center justify-between px-4 py-3 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === alert.id ? null : alert.id)}
                >
                  <div className="flex items-center gap-3">
                    <AlertBadge type={alert.type} />
                    <span className="text-xs text-gray-400">{alert.timestamp?.slice(0, 19)}</span>
                    <span className="text-xs font-mono text-gray-500 hidden md:inline">
                      <MapPin className="w-3 h-3 inline" /> {alert.lat?.toFixed(4)}, {alert.lon?.toFixed(4)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {alert.acknowledged ? (
                      <span className="text-green-500"><Check className="w-4 h-4" /></span>
                    ) : (
                      <button
                        onClick={(e) => { e.stopPropagation(); acknowledgeAlert(alert.id); }}
                        className="px-2 py-1 bg-forest-600 text-white rounded text-xs hover:bg-forest-700"
                      >
                        ACK
                      </button>
                    )}
                    {expandedId === alert.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </div>
                </div>
                {expandedId === alert.id && (
                  <div className="px-4 pb-4 bg-gray-50 animate-fade-in">
                    <div className="flex gap-4">
                      {alert.image_b64 && (
                        <img
                          src={`data:image/jpeg;base64,${alert.image_b64}`}
                          alt="Alert snapshot"
                          className="w-48 h-32 object-cover rounded-lg border"
                        />
                      )}
                      <div className="flex-1 space-y-2 text-sm">
                        <p><strong>GPS:</strong> <span className="font-mono">{alert.lat?.toFixed(6)}, {alert.lon?.toFixed(6)}</span></p>
                        <p><strong>Time:</strong> {alert.timestamp}</p>
                        <p><strong>Status:</strong> {alert.acknowledged ? '✅ Acknowledged' : '❌ Pending'}</p>
                        {alert.notes && <p><strong>Notes:</strong> {alert.notes}</p>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
