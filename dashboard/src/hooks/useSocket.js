import { useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import useStore from '../store/useStore';

let socket = null;

export function useSocket() {
  const { setConnected, setRoverState, addTelemetry, addAlert,
          setActiveAlert, addChatMessage, setUnacknowledgedCount } = useStore();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const isLocalFile = window.location.protocol === 'file:';
    const serverUrl = isLocalFile ? 'http://localhost:5000' : window.location.origin;

    socket = io(serverUrl, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
      reconnectionDelay: 2000,
    });

    socket.on('connect', () => {
      setConnected(true);
      addChatMessage({ type: 'system', text: 'Connected to STASIS server' });
    });

    socket.on('disconnect', () => {
      setConnected(false);
      addChatMessage({ type: 'system', text: 'Disconnected from server' });
    });

    socket.on('telemetry', (data) => {
      setRoverState(data);
      addTelemetry(data);
    });

    socket.on('alert', (data) => {
      addAlert(data);
      if (data.alert_type === 1 || data.type === 'HUMAN') {
        setActiveAlert(data);
        // Browser notification
        if (Notification.permission === 'granted') {
          new Notification('⚠ STASIS ALERT', {
            body: 'Human detected in patrol zone!',
            icon: '/stasis-logo.svg'
          });
        }
      }
      addChatMessage({
        type: 'alert',
        text: `Alert: ${data.type || 'UNKNOWN'} at (${data.lat?.toFixed(4)}, ${data.lon?.toFixed(4)})`
      });
    });

    socket.on('rover_state', (data) => {
      setRoverState(data);
      addChatMessage({
        type: 'state',
        text: `Rover state: ${data.state || 'UNKNOWN'}`
      });
    });

    socket.on('connection', (data) => {
      addChatMessage({
        type: 'system',
        text: `Rover connection: ${data.status}`
      });
    });

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      if (socket) socket.disconnect();
    };
  }, []);
}

export function sendCommand(command, data = {}) {
  if (socket && socket.connected) {
    socket.emit('command', { command, ...data });
  }
}

export function ackAlert(id, notes = '') {
  if (socket && socket.connected) {
    socket.emit('ack_alert', { id, notes });
  }
}
