import React, { useState, useRef, useEffect } from 'react';
import { Send, StopCircle, RotateCcw, Play, MapPin, Bot, User } from 'lucide-react';
import useStore from '../store/useStore';
import { sendCommand } from '../hooks/useSocket';

const quickCommands = [
  { label: 'STOP', cmd: 'stop', icon: StopCircle, color: 'red' },
  { label: 'RETURN TO BASE', cmd: 'return', icon: RotateCcw, color: 'amber' },
  { label: 'RESUME PATROL', cmd: 'resume', icon: Play, color: 'green' },
];

export default function Chat() {
  const { chatMessages, addChatMessage } = useStore();
  const [input, setInput] = useState('');
  const [showGotoDialog, setShowGotoDialog] = useState(false);
  const [gotoLat, setGotoLat] = useState('');
  const [gotoLon, setGotoLon] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleQuickCommand = (cmd) => {
    sendCommand(cmd);
    addChatMessage({ type: 'command', text: `Sent command: ${cmd.toUpperCase()}` });
  };

  const handleGoto = () => {
    const lat = parseFloat(gotoLat);
    const lon = parseFloat(gotoLon);
    if (!isNaN(lat) && !isNaN(lon)) {
      sendCommand('goto', { lat, lon });
      addChatMessage({ type: 'command', text: `Navigate to (${lat.toFixed(4)}, ${lon.toFixed(4)})` });
      setShowGotoDialog(false);
      setGotoLat('');
      setGotoLon('');
    }
  };

  const handleInput = () => {
    if (!input.trim()) return;
    const lower = input.toLowerCase().trim();
    if (lower === 'stop') handleQuickCommand('stop');
    else if (lower === 'return' || lower === 'return to base') handleQuickCommand('return');
    else if (lower === 'resume' || lower === 'resume patrol') handleQuickCommand('resume');
    else addChatMessage({ type: 'command', text: input });
    setInput('');
  };

  const getMsgStyle = (type) => {
    switch (type) {
      case 'command': return 'ml-auto bg-forest-600 text-white';
      case 'alert': return 'mr-auto bg-red-100 text-red-800 border border-red-200';
      case 'state': return 'mr-auto bg-blue-50 text-blue-800 border border-blue-200';
      case 'system': return 'mx-auto bg-gray-100 text-gray-500 text-xs';
      default: return 'mr-auto bg-white border border-gray-200';
    }
  };

  return (
    <div className="flex flex-col h-full animate-fade-in">
      <h2 className="text-xl font-bold text-forest-800 mb-4">Command Log</h2>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto bg-white rounded-xl border border-gray-200 p-4 mb-4 space-y-3">
        {chatMessages.length === 0 && (
          <p className="text-center text-gray-400 text-sm py-8">No messages yet. Use commands below to control the rover.</p>
        )}
        {chatMessages.map((msg) => (
          <div key={msg.id} className={`max-w-[80%] px-3 py-2 rounded-xl text-sm ${getMsgStyle(msg.type)}`}>
            <div className="flex items-center gap-1 mb-0.5">
              {msg.type === 'command' ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
              <span className="text-[10px] opacity-70">
                {new Date(msg.id).toLocaleTimeString()}
              </span>
            </div>
            {msg.text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Quick commands */}
      <div className="flex flex-wrap gap-2 mb-3">
        {quickCommands.map(({ label, cmd, icon: Icon, color }) => (
          <button
            key={cmd}
            onClick={() => handleQuickCommand(cmd)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
              bg-${color}-50 text-${color}-700 hover:bg-${color}-100 border border-${color}-200`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
        <button
          onClick={() => setShowGotoDialog(!showGotoDialog)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
        >
          <MapPin className="w-3.5 h-3.5" /> SEND TO [lat,lon]
        </button>
      </div>

      {/* Goto dialog */}
      {showGotoDialog && (
        <div className="flex gap-2 mb-3 p-3 bg-blue-50 rounded-lg border border-blue-200 animate-fade-in">
          <input type="number" step="any" value={gotoLat} onChange={e => setGotoLat(e.target.value)}
            placeholder="Latitude" className="flex-1 px-3 py-1.5 border rounded text-sm" />
          <input type="number" step="any" value={gotoLon} onChange={e => setGotoLon(e.target.value)}
            placeholder="Longitude" className="flex-1 px-3 py-1.5 border rounded text-sm" />
          <button onClick={handleGoto} className="px-4 py-1.5 bg-forest-600 text-white rounded text-sm hover:bg-forest-700">Go</button>
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleInput()}
          placeholder="Type a command (stop, return, resume)..."
          className="flex-1 px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-forest-500"
        />
        <button onClick={handleInput} className="p-2.5 bg-forest-600 text-white rounded-xl hover:bg-forest-700 transition-colors">
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
