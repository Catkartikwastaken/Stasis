import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Polygon, Popup, CircleMarker } from 'react-leaflet';
import { Navigation, Clock, Gauge } from 'lucide-react';
import useStore from '../store/useStore';
import api from '../services/api';

export default function LiveMap() {
  const { roverState, telemetryHistory, geofences, setGeofences } = useStore();
  const [trail, setTrail] = useState([]);

  useEffect(() => {
    const positions = telemetryHistory
      .filter(t => t.lat && t.lon)
      .map(t => [t.lat, t.lon]);
    setTrail(positions.slice(-200));
  }, [telemetryHistory]);

  useEffect(() => {
    api.get('/geofences').then(res => setGeofences(res.data)).catch(() => {});
  }, []);

  const center = roverState.lat && roverState.lon
    ? [roverState.lat, roverState.lon]
    : [0, 0];

  const activeGeofence = geofences.find(g => g.active);
  const gfPolygon = activeGeofence?.polygon?.map(p =>
    [p.lat || p[0], p.lon || p[1]]
  ) || [];

  const alerts = useStore(s => s.alerts);
  const humanAlerts = alerts.filter(a => a.type === 'HUMAN' && a.lat && a.lon);

  return (
    <div className="h-full flex flex-col gap-4 animate-fade-in">
      <h2 className="text-xl font-bold text-forest-800">Live Map</h2>

      <div className="flex-1 flex gap-4">
        {/* Map */}
        <div className="flex-1 rounded-xl overflow-hidden border border-gray-200 shadow-sm">
          <MapContainer center={center} zoom={16} className="w-full h-full" style={{ minHeight: '500px' }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; OpenStreetMap'
            />

            {/* Geofence polygon */}
            {gfPolygon.length >= 3 && (
              <Polygon
                positions={gfPolygon}
                pathOptions={{ color: '#2D6A4F', fillColor: '#74C69D', fillOpacity: 0.15, weight: 2 }}
              />
            )}

            {/* GPS trail */}
            {trail.length > 1 && (
              <Polyline
                positions={trail}
                pathOptions={{ color: '#40916C', weight: 2, opacity: 0.6, dashArray: '5,5' }}
              />
            )}

            {/* Rover marker */}
            {roverState.lat && (
              <Marker position={[roverState.lat, roverState.lon]}>
                <Popup>
                  <div className="text-sm">
                    <strong>STASIS Rover</strong><br />
                    State: {roverState.state}<br />
                    Battery: {roverState.battery_percent}%
                  </div>
                </Popup>
              </Marker>
            )}

            {/* Alert markers */}
            {humanAlerts.map((a, i) => (
              <CircleMarker
                key={i}
                center={[a.lat, a.lon]}
                radius={8}
                pathOptions={{ color: '#DC2626', fillColor: '#DC2626', fillOpacity: 0.6 }}
              >
                <Popup>
                  <div className="text-sm">
                    <strong className="text-red-600">⚠ Human Detected</strong><br />
                    {a.timestamp}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* Sidebar info */}
        <div className="hidden lg:flex flex-col w-64 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-700 mb-3">Position</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Latitude</span>
                <span className="font-mono">{roverState.lat?.toFixed(6) || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Longitude</span>
                <span className="font-mono">{roverState.lon?.toFixed(6) || '-'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Heading</span>
                <span className="font-mono">-°</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-700 mb-3">Status</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-gray-500">State</span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold
                  ${roverState.state === 'PATROLLING' ? 'bg-forest-100 text-forest-700' :
                    roverState.state === 'STUCK' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-600'}`}>
                  {roverState.state}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Trail Points</span>
                <span className="font-mono">{trail.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Geofence</span>
                <span className="text-xs">{activeGeofence?.name || 'None'}</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-700 mb-3">Alerts on Map</h3>
            <p className="text-2xl font-bold text-alert-red font-mono">
              {humanAlerts.length}
            </p>
            <p className="text-xs text-gray-400">human detections</p>
          </div>
        </div>
      </div>
    </div>
  );
}
