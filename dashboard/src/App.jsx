import React, { useState } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import StatusBar from './components/StatusBar';
import AlertModal from './components/AlertModal';
import Dashboard from './pages/Dashboard';
import LiveMap from './pages/LiveMap';
import CameraFeed from './pages/CameraFeed';
import Alerts from './pages/Alerts';
import Chat from './pages/Chat';
import Settings from './pages/Settings';
import Landing from './pages/Landing';
import LoadingScreen from './components/LoadingScreen';
import useStore from './store/useStore';
import { useSocket } from './hooks/useSocket';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { activeAlert } = useStore();
  useSocket();

  if (isLoading) {
    return <LoadingScreen onComplete={() => setIsLoading(false)} />;
  }

  if (!isAuthenticated) {
    return <Landing onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <HashRouter>
      <div className="flex h-screen bg-bg text-text-primary overflow-hidden font-sans selection:bg-accent selection:text-bg">
        <Sidebar />
        <div className="flex-1 flex flex-col relative overflow-hidden">
          {/* Soft Ambient Forest Glows */}
          <div className="absolute inset-0 pointer-events-none z-0">
             <div className="absolute top-0 right-0 w-1/2 h-1/2 bg-accent/5 blur-[120px]"></div>
             <div className="absolute bottom-0 left-0 w-1/3 h-1/3 bg-accent-dim/10 blur-[100px]"></div>
          </div>
          
          <Header />
          <main className="flex-1 overflow-y-auto p-4 md:p-8 relative z-10 scrollbar-hide">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/map" element={<LiveMap />} />
              <Route path="/camera" element={<CameraFeed />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </main>
          <StatusBar />
          {activeAlert && <AlertModal />}
        </div>
      </div>
    </HashRouter>
  );
}
