import { useEffect } from 'react';
import useStore from '../store/useStore';
import api from '../services/api';

export function useTelemetry() {
  const { telemetryHistory, roverState } = useStore();

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await api.get('/telemetry?limit=60');
        const data = res.data.reverse();
        data.forEach((t) => useStore.getState().addTelemetry(t));
      } catch (e) {
        console.error('Failed to fetch telemetry:', e);
      }
    };
    fetchHistory();
  }, []);

  return { telemetryHistory, roverState };
}
