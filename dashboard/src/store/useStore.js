import { create } from 'zustand';

const useStore = create((set, get) => ({
  // Connection
  connected: false,
  setConnected: (val) => set({ connected: val }),

  // Rover State
  roverState: {
    state: 'IDLE',
    state_code: 0,
    lat: 0,
    lon: 0,
    battery_voltage: 0,
    battery_percent: 0,
    temperature: 0,
    is_charging: false,
    battery_low: false,
    connected: false,
  },
  setRoverState: (state) => set({ roverState: { ...get().roverState, ...state } }),

  // Telemetry History
  telemetryHistory: [],
  addTelemetry: (data) => set((s) => ({
    telemetryHistory: [...s.telemetryHistory.slice(-59), data]
  })),

  // Alerts
  alerts: [],
  setAlerts: (alerts) => set({ alerts }),
  addAlert: (alert) => set((s) => ({ alerts: [alert, ...s.alerts] })),
  unacknowledgedCount: 0,
  setUnacknowledgedCount: (count) => set({ unacknowledgedCount: count }),

  // Active Alert Modal
  activeAlert: null,
  setActiveAlert: (alert) => set({ activeAlert: alert }),
  clearActiveAlert: () => set({ activeAlert: null }),

  // Chat Log
  chatMessages: [],
  addChatMessage: (msg) => set((s) => ({
    chatMessages: [...s.chatMessages, { ...msg, id: Date.now() }]
  })),

  // Geofences
  geofences: [],
  setGeofences: (gf) => set({ geofences: gf }),

  // Settings
  settings: {},
  setSettings: (settings) => set({ settings }),
}));

export default useStore;
