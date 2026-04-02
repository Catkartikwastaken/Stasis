import { useEffect } from 'react';
import useStore from '../store/useStore';
import api from '../services/api';

export function useAlerts() {
  const { alerts, setAlerts, unacknowledgedCount, setUnacknowledgedCount } = useStore();

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await api.get('/alerts');
        setAlerts(res.data);
        const unack = res.data.filter(a => !a.acknowledged).length;
        setUnacknowledgedCount(unack);
      } catch (e) {
        console.error('Failed to fetch alerts:', e);
      }
    };
    fetchAlerts();
  }, []);

  const acknowledgeAlert = async (id, notes = '') => {
    try {
      await api.post(`/alerts/${id}/ack`, { notes });
      setAlerts(alerts.map(a => a.id === id ? { ...a, acknowledged: 1 } : a));
      setUnacknowledgedCount(Math.max(0, unacknowledgedCount - 1));
    } catch (e) {
      console.error('Failed to ack alert:', e);
    }
  };

  return { alerts, unacknowledgedCount, acknowledgeAlert };
}
