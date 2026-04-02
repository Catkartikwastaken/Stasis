import React from 'react';
import { AlertTriangle, MapPin, X, Eye } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import useStore from '../store/useStore';
import { ackAlert } from '../hooks/useSocket';

export default function AlertModal() {
  const { activeAlert, clearActiveAlert } = useStore();
  const navigate = useNavigate();

  if (!activeAlert) return null;

  const handleAcknowledge = () => {
    if (activeAlert.id) {
      ackAlert(activeAlert.id);
    }
    clearActiveAlert();
  };

  const handleViewOnMap = () => {
    clearActiveAlert();
    navigate('/map');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg/60 backdrop-blur-3xl animate-fade-in relative overflow-hidden">
      {/* Background Ambience */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--color-alert-red)_0,transparent_100%)] opacity-[0.05] animate-pulse"></div>
      
      <div className="bg-surface border border-alert-red/20 rounded-main shadow-[0_40px_100px_rgba(251,113,133,0.15)] max-w-md w-full mx-4 overflow-hidden relative z-10">
        <div className="p-10 text-center border-b border-border bg-alert-red/5">
          <div className="w-20 h-20 rounded-full bg-alert-red/10 border border-alert-red/20 flex items-center justify-center mx-auto mb-6 shadow-glow-red">
             <AlertTriangle className="w-10 h-10 text-alert-red animate-pulse" />
          </div>
          <h2 className="text-3xl font-black text-white lowercase italic tracking-tight">anomaly.detected</h2>
          <div className="text-[10px] font-black text-alert-red tracking-[0.4em] uppercase mt-3 italic animate-bounce">Unauthorized_Human_Presence</div>
        </div>

        <div className="p-10">
          {/* Snapshot Container */}
          {activeAlert.image_b64 && (
            <div className="mb-8 rounded-2xl overflow-hidden border border-border shadow-inner relative group">
              <img
                src={`data:image/jpeg;base64,${activeAlert.image_b64}`}
                alt="Detection snapshot"
                className="w-full h-64 object-cover opacity-90 group-hover:scale-105 transition-transform duration-1000 grayscale-[30%] contrast-125"
              />
              <div className="absolute top-4 left-4 px-4 py-2 bg-alert-red text-white text-[9px] font-black tracking-widest uppercase rounded-full shadow-xl">
                 REC_UPLINK
              </div>
            </div>
          )}

          {/* Details */}
          <div className="grid grid-cols-2 gap-6 mb-10 border-y border-border py-8 italic font-bold">
            <div className="flex flex-col gap-2">
              <span className="text-[9px] text-text-dim uppercase tracking-[0.2em]">Coordinates</span>
              <div className="text-sm text-text-primary flex items-center gap-2">
                 <MapPin className="w-4 h-4 text-alert-red" />
                 {activeAlert.lat?.toFixed(5)}, {activeAlert.lon?.toFixed(5)}
              </div>
            </div>
            {activeAlert.confidence && (
              <div className="flex flex-col gap-2 border-l border-border pl-6">
                <span className="text-[9px] text-text-dim uppercase tracking-[0.2em]">Integrity</span>
                <div className="text-sm text-text-primary flex items-center gap-2">
                   <Eye className="w-4 h-4 text-alert-red" />
                   {(activeAlert.confidence * 100).toFixed(0)}%_UPLINK
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="space-y-4">
            <button
              onClick={handleAcknowledge}
              className="w-full bg-alert-red text-white py-6 rounded-2xl font-black tracking-[0.1em] uppercase text-sm hover:bg-white hover:text-alert-red transition-all shadow-[0_10px_30px_rgba(251,113,133,0.3)] active:scale-95"
            >
              Confirm_Acknowledgment
            </button>
            <button
              onClick={handleViewOnMap}
              className="w-full py-2 text-[10px] text-text-dim hover:text-white transition-colors uppercase tracking-[0.2em] italic underline underline-offset-4"
            >
              [ view_origin_map ]
            </button>
          </div>
        </div>
        
        {/* Decorative corner leaves */}
        <div className="absolute bottom-4 right-4 opacity-5"><Leaf className="w-12 h-12 text-alert-red shadow-glow-red" /></div>
      </div>
    </div>
  );
}
