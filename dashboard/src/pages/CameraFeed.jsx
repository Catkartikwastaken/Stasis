import React, { useState, useEffect } from 'react';
import { Camera, Video, VideoOff, Download } from 'lucide-react';
import api from '../services/api';
import useStore from '../store/useStore';

export default function CameraFeed() {
  const [streamUrl, setStreamUrl] = useState('');
  const [isLive, setIsLive] = useState(false);
  const alerts = useStore(s => s.alerts);
  const detections = alerts.filter(a => a.type === 'HUMAN' && a.image_b64);

  useEffect(() => {
    api.get('/stream/url').then(res => {
      setStreamUrl(res.data.url);
      setIsLive(true);
    }).catch(() => setIsLive(false));
  }, []);

  const handleCapture = async () => {
    try {
      const res = await api.get('/stream/url');
      window.open(res.data.capture_url, '_blank');
    } catch (e) {
      console.error('Capture failed:', e);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-forest-800">Camera Feed</h2>
        <div className="flex items-center gap-2">
          <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold
            ${isLive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {isLive ? <Video className="w-3 h-3" /> : <VideoOff className="w-3 h-3" />}
            {isLive ? 'LIVE' : 'OFFLINE'}
          </span>
          <button
            onClick={handleCapture}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-forest-600 text-white rounded-lg text-sm hover:bg-forest-700 transition-colors"
          >
            <Camera className="w-4 h-4" /> Capture
          </button>
        </div>
      </div>

      {/* Live Stream */}
      <div className="bg-black rounded-xl overflow-hidden border border-gray-200 shadow-sm">
        {isLive && streamUrl ? (
          <img
            src={streamUrl}
            alt="Live camera feed"
            className="w-full h-auto max-h-[500px] object-contain"
            onError={() => setIsLive(false)}
          />
        ) : (
          <div className="flex items-center justify-center h-80 text-gray-500">
            <div className="text-center">
              <VideoOff className="w-12 h-12 mx-auto mb-3 text-gray-600" />
              <p className="text-sm">Camera stream unavailable</p>
              <p className="text-xs text-gray-600 mt-1">Check ESP32-CAM connection</p>
            </div>
          </div>
        )}
      </div>

      {/* Detection Gallery */}
      <div>
        <h3 className="font-semibold text-sm text-gray-700 mb-3">Detection Snapshots</h3>
        {detections.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
            <Camera className="w-8 h-8 mx-auto text-gray-300 mb-2" />
            <p className="text-sm text-gray-400">No detection snapshots yet</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {detections.slice(0, 12).map((det, i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                <img
                  src={`data:image/jpeg;base64,${det.image_b64}`}
                  alt={`Detection ${i + 1}`}
                  className="w-full h-32 object-cover"
                />
                <div className="p-2">
                  <p className="text-xs font-mono text-gray-500">
                    {det.timestamp?.slice(0, 19) || 'N/A'}
                  </p>
                  {det.confidence && (
                    <p className="text-xs text-forest-600 font-semibold">
                      {(det.confidence * 100).toFixed(0)}% confidence
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
