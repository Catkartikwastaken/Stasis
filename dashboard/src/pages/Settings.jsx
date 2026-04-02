import React, { useState, useEffect } from 'react';
import { Save, Trash2, Download, Wifi, Cpu, Shield, Battery, Clock, Camera } from 'lucide-react';
import api from '../services/api';
import useStore from '../store/useStore';
import GeofenceEditor from '../components/GeofenceEditor';

export default function Settings() {
  const { settings, setSettings, geofences, setGeofences, roverState } = useStore();
  const [localSettings, setLocalSettings] = useState({
    motor_speed: '80',
    detection_confidence: '72',
    motion_sensitivity: '3',
    stuck_timeout: '5',
    charging_voltage: '3.6',
    charge_start: '02:00',
    charge_end: '06:00',
    auto_return: 'true',
    report_time: '23:55',
    cam_ip: '192.168.4.2',
    wifi_password: 'stasis2024',
  });

  useEffect(() => {
    api.get('/settings').then(res => {
      setSettings(res.data);
      setLocalSettings(s => ({ ...s, ...res.data }));
    }).catch(() => {});

    api.get('/geofences').then(res => setGeofences(res.data)).catch(() => {});
  }, []);

  const handleSave = async (section) => {
    try {
      await api.post('/settings', localSettings);
      setSettings(localSettings);
      alert('Settings saved!');
    } catch (e) {
      console.error('Save failed:', e);
    }
  };

  const deleteGeofence = async (id) => {
    if (!confirm('Delete this geofence?')) return;
    try {
      await api.delete(`/geofences/${id}`);
      const res = await api.get('/geofences');
      setGeofences(res.data);
    } catch (e) {
      console.error('Delete failed:', e);
    }
  };

  const updateField = (key, value) => {
    setLocalSettings(s => ({ ...s, [key]: value }));
  };

  const Section = ({ title, icon: Icon, children }) => (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5 text-forest-600" />
        <h3 className="font-semibold text-gray-800">{title}</h3>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );

  const Field = ({ label, type = 'text', value, onChange, suffix }) => (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-gray-600 whitespace-nowrap">{label}</label>
      <div className="flex items-center gap-1.5">
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-28 px-3 py-1.5 border border-gray-200 rounded-lg text-sm text-right font-mono focus:outline-none focus:ring-2 focus:ring-forest-400"
        />
        {suffix && <span className="text-xs text-gray-400">{suffix}</span>}
      </div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-3xl animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-forest-800">Settings</h2>
        <button onClick={handleSave}
          className="flex items-center gap-1.5 px-4 py-2 bg-forest-600 text-white rounded-lg text-sm hover:bg-forest-700 transition-colors">
          <Save className="w-4 h-4" /> Save All
        </button>
      </div>

      <Section title="Rover" icon={Cpu}>
        <Field label="Motor Speed" type="number" value={localSettings.motor_speed}
          onChange={v => updateField('motor_speed', v)} suffix="%" />
        <Field label="Detection Confidence" type="number" value={localSettings.detection_confidence}
          onChange={v => updateField('detection_confidence', v)} suffix="%" />
        <Field label="Motion Sensitivity" type="number" value={localSettings.motion_sensitivity}
          onChange={v => updateField('motion_sensitivity', v)} suffix="%" />
        <Field label="Stuck Timeout" type="number" value={localSettings.stuck_timeout}
          onChange={v => updateField('stuck_timeout', v)} suffix="min" />
      </Section>

      <Section title="Geofence" icon={Shield}>
        <GeofenceEditor center={[roverState.lat || 0, roverState.lon || 0]} />
        {geofences.length > 0 && (
          <div className="mt-4 space-y-2">
            <p className="text-sm font-medium text-gray-700">Saved Geofences</p>
            {geofences.map(gf => (
              <div key={gf.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div>
                  <span className="text-sm font-medium">{gf.name}</span>
                  <span className={`ml-2 text-xs ${gf.active ? 'text-green-600' : 'text-gray-400'}`}>
                    {gf.active ? '● Active' : '○ Inactive'}
                  </span>
                </div>
                <button onClick={() => deleteGeofence(gf.id)} className="p-1 text-red-500 hover:bg-red-50 rounded">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Charging" icon={Battery}>
        <Field label="Low Voltage Threshold" type="number" value={localSettings.charging_voltage}
          onChange={v => updateField('charging_voltage', v)} suffix="V" />
        <Field label="Schedule Start" type="time" value={localSettings.charge_start}
          onChange={v => updateField('charge_start', v)} />
        <Field label="Schedule End" type="time" value={localSettings.charge_end}
          onChange={v => updateField('charge_end', v)} />
        <div className="flex items-center justify-between">
          <label className="text-sm text-gray-600">Auto Return</label>
          <label className="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" checked={localSettings.auto_return === 'true'}
              onChange={e => updateField('auto_return', e.target.checked ? 'true' : 'false')}
              className="sr-only peer" />
            <div className="w-11 h-6 bg-gray-200 peer-focus:ring-2 peer-focus:ring-forest-400 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-forest-600" />
          </label>
        </div>
      </Section>

      <Section title="Reports" icon={Clock}>
        <Field label="Report Time" type="time" value={localSettings.report_time}
          onChange={v => updateField('report_time', v)} />
        <button className="text-sm text-forest-600 hover:underline">Download all reports as ZIP →</button>
      </Section>

      <Section title="Network" icon={Wifi}>
        <Field label="ESP32-CAM IP" value={localSettings.cam_ip}
          onChange={v => updateField('cam_ip', v)} />
        <Field label="WiFi AP Password" value={localSettings.wifi_password}
          onChange={v => updateField('wifi_password', v)} />
      </Section>

      <Section title="About" icon={Camera}>
        <div className="space-y-1 text-sm text-gray-600">
          <p>Firmware: <span className="font-mono">v1.0.0</span></p>
          <p>Server: <span className="font-mono">v1.0.0</span></p>
          <p>Dashboard: <span className="font-mono">v1.0.0</span></p>
          <p>Rover State: <span className="font-mono">{roverState.state}</span></p>
        </div>
      </Section>
    </div>
  );
}
