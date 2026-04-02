import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence, useScroll, useTransform } from 'framer-motion';
import { Cpu, Radio, Camera, Workflow, Server, Zap, Shield, ChevronDown, Leaf, Trees } from 'lucide-react';

const HardwareCard = ({ title, icon: Icon, chip, specs }) => (
  <motion.div 
    whileHover={{ y: -10 }}
    className="bg-surface/40 p-10 rounded-main border border-border backdrop-blur-xl group transition-all hover:bg-surface-hover hover:border-accent/40"
  >
    <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-8 shadow-[0_0_20px_rgba(74,222,128,0.1)] group-hover:scale-110 transition-transform">
       <Icon className="w-8 h-8 text-accent" />
    </div>
    <div className="text-[10px] font-bold text-accent tracking-[0.4em] uppercase mb-2">{chip}</div>
    <h3 className="text-3xl font-bold text-white mb-6 uppercase tracking-tight">{title}</h3>
    <ul className="space-y-4">
       {specs.map((s, i) => (
         <li key={i} className="flex items-center gap-3 text-text-secondary text-sm">
            <div className="w-1.5 h-1.5 rounded-full bg-accent/30 group-hover:bg-accent transition-colors"></div>
            {s}
         </li>
       ))}
    </ul>
  </motion.div>
);

const SectionHeader = ({ title, subtitle }) => (
  <div className="mb-24 text-center">
     <motion.div 
       initial={{ opacity: 0, scale: 0.8 }}
       whileInView={{ opacity: 1, scale: 1 }}
       className="w-12 h-1 bg-accent/30 mx-auto mb-8 rounded-full"
     ></motion.div>
     <h2 className="text-5xl md:text-7xl font-black text-white uppercase tracking-tighter mb-4 italic italic">{title}</h2>
     <p className="text-xl text-text-dim max-w-2xl mx-auto font-light leading-relaxed">{subtitle}</p>
  </div>
);

export default function Landing({ onLogin }) {
  const [showLogin, setShowLogin] = useState(false);
  const { scrollYProgress } = useScroll();
  const heroY = useTransform(scrollYProgress, [0, 0.2], [0, -50]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    setIsAuthenticating(true);
    setTimeout(() => onLogin(), 1500);
  };

  return (
    <div className="min-h-screen bg-bg text-text-primary selection:bg-accent selection:text-bg overflow-x-hidden font-sans">
      
      {/* Background Ambience */}
      <div className="fixed inset-0 pointer-events-none z-0">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(74,222,128,0.05),transparent_60%)]"></div>
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,rgba(22,101,52,0.1),transparent_70%)]"></div>
      </div>

      {/* 1. Hero Section */}
      <motion.section 
        style={{ y: heroY, opacity: heroOpacity }}
        className="relative h-screen flex flex-col items-center justify-center text-center px-12 z-10"
      >
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          className="p-12 mb-12 rounded-full bg-accent/5 border border-accent/10 backdrop-blur-3xl shadow-2xl relative"
        >
          {/* Animated Glow Halo */}
          <div className="absolute inset-0 rounded-full border-4 border-accent animate-ping opacity-10 blur-xl"></div>
          <Trees className="w-24 h-24 text-accent/80" />
        </motion.div>

        <motion.h1 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="text-[120px] md:text-[200px] font-black lowercase leading-none tracking-[-0.08em] mb-12 text-white italic"
        >
          stasis.
        </motion.h1>

        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="flex flex-col items-center gap-12"
        >
          <p className="max-w-2xl text-2xl text-text-dim font-light leading-relaxed tracking-wide">
            Autonomous forest patrol systems driven by machine intelligence. 
            Merging extreme hardware resilience with high-performance telemetry.
          </p>
          
          <div className="flex gap-6">
             <button 
               onClick={() => setShowLogin(true)}
               className="group relative px-12 py-5 bg-accent text-bg font-black rounded-full text-base flex items-center gap-4 transition-all hover:scale-105 active:scale-95 shadow-[0_10px_30px_rgba(74,222,128,0.3)]"
             >
               Initialize System
               <Workflow className="w-4 h-4 group-hover:rotate-180 transition-transform duration-500" />
             </button>
             <button className="px-12 py-5 rounded-full border border-border bg-surface/40 backdrop-blur-md text-white font-bold hover:bg-surface transition-colors flex items-center gap-4">
               View Stack
               <ChevronDown className="w-4 h-4 animate-bounce" />
             </button>
          </div>
        </motion.div>
      </motion.section>

      {/* 2. Features Grid */}
      <section className="relative z-10 py-48 px-12 max-w-7xl mx-auto">
        <SectionHeader 
          title="Autonomous_Utility" 
          subtitle="Our ecosystem is designed for deep forest operational safety, providing a rock-solid telemetry link even in dense canopies."
        />
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
           <div className="p-16 rounded-main bg-gradient-to-br from-surface to-bg border border-border group hover:border-accent/40 transition-colors">
              <Zap className="w-12 h-12 text-accent mb-12" />
              <h4 className="text-4xl font-bold text-white mb-6 uppercase tracking-tight">Mission_Continuity</h4>
              <p className="text-text-secondary text-lg leading-relaxed">Integrated solar management and optimized power profiles for the ESP32-S3 ensure the rover remains active for extended mission durations without operator intervention.</p>
           </div>
           <div className="p-16 rounded-main bg-gradient-to-br from-surface to-bg border border-border group hover:border-accent/40 transition-colors">
              <Shield className="w-12 h-12 text-accent mb-12" />
              <h4 className="text-4xl font-bold text-white mb-6 uppercase tracking-tight">Geofence_Locks</h4>
              <p className="text-text-secondary text-lg leading-relaxed">Real-time GPS boundary enforcement. If the signal is lost, the redundant C3 relay triggers an immediate Return-to-Launch sequence to secure the hardware.</p>
           </div>
        </div>
      </section>

      {/* 3. The Tech Stack Section */}
      <section className="relative z-10 py-48 px-12 bg-white/5 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto">
          <SectionHeader 
            title="Operational_Architecture" 
            subtitle="The STASIS stack bridges the gap between low-level firmware and high-frequency real-time web telemetry."
          />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-32">
             <HardwareCard 
               title="STASIS_CORE" 
               chip="ESP32-S3" 
               icon={Cpu}
               specs={[
                 "Autonomous Guidance Engine",
                 "Dual-Core 240MHz Powerhouse",
                 "RTOS-based Mission Logic",
                 "Integrated IMU/Compass Sync"
               ]}
             />
             <HardwareCard 
               title="BRIDGE_RELAY" 
               chip="ESP32-C3" 
               icon={Radio}
               specs={[
                 "Uplink/Downlink C3 Radio",
                 "Low-Power Signal Management",
                 "UDP/ESP-NOW Transmission",
                 "Redundant Failsafe Trigger"
               ]}
             />
             <HardwareCard 
               title="VISUAL_AI" 
               chip="ESP32-CAM" 
               icon={Camera}
               specs={[
                 "Edge AI Object Detection",
                 "JPEG Live Stream Encoder",
                 "Human Recognition Alpha",
                 "Incident Snapshot Capture"
               ]}
             />
          </div>

          {/* Software Tech Stack Visual */}
          <div className="bg-surface rounded-main border border-border p-16 flex flex-col md:flex-row items-center gap-16">
             <div className="flex-1">
                <div className="text-[10px] font-black text-accent tracking-[0.4em] uppercase mb-4 italic">Web_Nexus_Software</div>
                <h3 className="text-5xl font-black text-white mb-8 leading-tight uppercase italic">Built on a Modern, High-Frequency Backbone</h3>
                <p className="text-text-secondary text-lg leading-relaxed mb-12 italic">
                  Our dashboard leverages **Vite-powered React** for sub-millisecond UI updates. The backend is a robust **Python/Flask** engine using **SocketIO** to relay telemetry from the UART buffer to your browser in real-time.
                </p>
                <div className="flex flex-wrap gap-4">
                   {['React', 'Vite', 'Framer Motion', 'TailwindCSS', 'Python', 'Flask', 'Socket.io', 'Leaflet'].map(tech => (
                     <span key={tech} className="px-6 py-2 rounded-full border border-border bg-bg/50 text-text-primary text-xs font-bold font-mono tracking-widest">{tech}</span>
                   ))}
                </div>
             </div>
             <div className="w-full md:w-96 p-12 bg-bg/50 rounded-2xl border border-border shadow-inner">
                <Server className="w-20 h-20 text-accent/30 mx-auto mb-10" />
                <div className="space-y-6">
                   <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div animate={{ width: ["10%", "90%"] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }} className="h-full bg-accent" />
                   </div>
                   <div className="h-2 w-2/3 bg-white/5 rounded-full overflow-hidden">
                      <motion.div animate={{ width: ["10%", "60%"] }} transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }} className="h-full bg-accent/40" />
                   </div>
                   <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div animate={{ width: ["10%", "100%"] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }} className="h-full bg-accent/60" />
                   </div>
                </div>
             </div>
          </div>
        </div>
      </section>

      {/* 4. Contact/Final Section */}
      <section className="relative z-10 py-48 px-12 text-center overflow-hidden">
         <motion.div 
           initial={{ scale: 0.8, opacity: 0 }}
           whileInView={{ scale: 1, opacity: 1 }}
           className="p-32 rounded-main bg-surface/50 border border-border max-w-5xl mx-auto backdrop-blur-md relative"
         >
            <SectionHeader 
               title="Secure Operation" 
               subtitle="Access operational control of current forest mission units."
            />
            <button 
              onClick={() => setShowLogin(true)}
              className="px-20 py-8 bg-white text-bg font-black rounded-full text-xl hover:bg-accent transition-all hover:scale-110 shadow-2xl uppercase tracking-tighter"
            >
              Control Dashboard
            </button>
            <div className="absolute top-10 left-10"><Leaf className="w-8 h-8 text-accent/10 rotate-45" /></div>
            <div className="absolute bottom-10 right-10"><Trees className="w-12 h-12 text-accent/10" /></div>
         </motion.div>
      </section>

      {/* Login Portal (Soothing Overlay) */}
      <AnimatePresence>
        {showLogin && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-12 bg-bg/80 backdrop-blur-2xl"
          >
            <motion.div 
              initial={{ y: 50, scale: 0.9 }}
              animate={{ y: 0, scale: 1 }}
              exit={{ y: 50, scale: 0.9 }}
              className="w-full max-w-lg bg-surface p-12 rounded-main border border-border shadow-[0_30px_100px_rgba(0,0,0,0.5)] relative overflow-hidden"
            >
              {/* Visual forest patterns */}
              <div className="absolute -top-10 -right-10 opacity-10"><Trees className="w-40 h-40 text-accent" /></div>
              
              <div className="flex flex-col items-center mb-12">
                 <div className="w-20 h-20 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center mb-6">
                    <Shield className="w-10 h-10 text-accent" />
                 </div>
                 <h2 className="text-4xl font-bold tracking-tight text-white lowercase italic">operational entry.</h2>
                 <p className="text-text-secondary mt-2 text-sm">Provision access to STASIS dashboard link.</p>
              </div>

              <form onSubmit={handleLogin} className="space-y-8">
                 <div className="space-y-3">
                    <label className="text-[10px] font-black text-text-dim uppercase tracking-[0.3em] block ml-2">Operator ID</label>
                    <input 
                      type="text" 
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      className="w-full bg-accent/5 border border-border p-6 rounded-2xl text-white focus:outline-none focus:border-accent/40 placeholder:text-text-dim/50 italic"
                      placeholder="e.g. Cat_Kartik"
                    />
                 </div>
                 <div className="space-y-3">
                    <label className="text-[10px] font-black text-text-dim uppercase tracking-[0.3em] block ml-2">Clearance Token</label>
                    <input 
                      type="password" 
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-accent/5 border border-border p-6 rounded-2xl text-white focus:outline-none focus:border-accent/40 placeholder:text-text-dim/50"
                      placeholder="••••••••"
                    />
                 </div>
                 <button 
                   disabled={isAuthenticating}
                   className="w-full py-6 bg-accent text-bg font-black rounded-2xl text-lg hover:bg-white transition-all disabled:opacity-50 shadow-xl"
                 >
                   {isAuthenticating ? 'SYNCHRONIZING...' : 'Login to System'}
                 </button>
                 <button type="button" onClick={() => setShowLogin(false)} className="w-full text-xs text-text-dim hover:text-white transition-colors lowercase tracking-widest italic underline">
                   [ return to mission info ]
                 </button>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <footer className="relative z-10 py-12 px-12 border-t border-border flex flex-col md:flex-row items-center justify-between gap-12 text-[10px] font-black tracking-[0.3em] text-text-dim uppercase bg-black/20">
         <div className="flex gap-12 items-center italic">
            <span className="flex items-center gap-3"><div className="w-2 h-2 rounded-full bg-accent animate-pulse"></div> SIGNAL_UPLINK: ACTIVE</span>
            <span>SYSTEM_NOMINAL</span>
         </div>
         <div className="text-center italic">STASIS_GLOBAL // BUILT_ON_S3_C3_CAM_SOCKETIO_REACT // 2026</div>
         <div className="hover:text-accent cursor-pointer transition-colors transition-colors">STASIS_PROTOCOLS_SECURED</div>
      </footer>
    </div>
  );
}
