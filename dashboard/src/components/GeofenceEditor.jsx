import React, { useState, useCallback } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, useMapEvents } from 'react-leaflet';
import { Save, Trash2, Plus } from 'lucide-react';
import api from '../services/api';
import useStore from '../store/useStore';

function ClickHandler({ onClick }) {
  useMapEvents({ click: (e) => onClick(e.latlng) });
  return null;
}

export default function GeofenceEditor({ center = [0, 0], zoom = 15 }) {
  const [vertices, setVertices] = useState([]);
  const [name, setName] = useState('');
  const [editing, setEditing] = useState(false);
  const { setGeofences } = useStore();

  const handleClick = useCallback((latlng) => {
    if (!editing) return;
    setVertices((v) => [...v, [latlng.lat, latlng.lng]]);
  }, [editing]);

  const handleSave = async () => {
    if (vertices.length < 3) return;
    const polygon = vertices.map(([lat, lng]) => ({ lat, lon: lng }));
    try {
      await api.post('/geofences', { name: name || 'Geofence', polygon });
      const res = await api.get('/geofences');
      setGeofences(res.data);
      setVertices([]);
      setName('');
      setEditing(false);
    } catch (e) {
      console.error('Save geofence failed:', e);
    }
  };

  const handleClear = () => {
    setVertices([]);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setEditing(!editing)}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
            ${editing ? 'bg-forest-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
        >
          <Plus className="w-4 h-4" />
          {editing ? 'Click map to add points' : 'Draw Geofence'}
        </button>
        {vertices.length > 0 && (
          <>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Geofence name"
              className="px-3 py-1.5 border rounded-lg text-sm flex-1"
            />
            <button onClick={handleSave}
              className="flex items-center gap-1 px-3 py-1.5 bg-forest-600 text-white rounded-lg text-sm hover:bg-forest-700">
              <Save className="w-4 h-4" /> Save
            </button>
            <button onClick={handleClear}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-100 text-red-600 rounded-lg text-sm hover:bg-red-200">
              <Trash2 className="w-4 h-4" /> Clear
            </button>
          </>
        )}
      </div>
      <div className="h-64 rounded-xl overflow-hidden border border-gray-200">
        <MapContainer center={center} zoom={zoom} className="w-full h-full">
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <ClickHandler onClick={handleClick} />
          {vertices.length >= 3 && (
            <Polygon positions={vertices} pathOptions={{ color: '#2D6A4F', fillColor: '#74C69D', fillOpacity: 0.3 }} />
          )}
          {vertices.map((v, i) => (
            <Marker key={i} position={v} />
          ))}
        </MapContainer>
      </div>
      <p className="text-xs text-gray-400">{vertices.length} vertices defined</p>
    </div>
  );
}
