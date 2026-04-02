import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trees, Leaf, Sparkles } from 'lucide-react';

const SoothingRoverSVG = () => (
  <svg viewBox="0 0 100 60" className="w-20 h-12 fill-accent stroke-bg" strokeWidth="0.5">
    <rect x="20" y="20" width="60" height="25" rx="8" />
    <circle cx="35" cy="48" r="8" className="fill-accent-dim" />
    <circle cx="65" cy="48" r="8" className="fill-accent-dim" />
    <path d="M40 25h20v4h-20z" className="fill-bg/20" />
    <circle cx="75" cy="22" r="2" className="fill-accent animate-pulse" />
  </svg>
);

export default function LoadingScreen({ onComplete }) {
  const [step, setStep] = useState(0);
  const messages = ["Connecting to Forest Uplink...", "Synchronizing S3 Core...", "Calibrating Cameras...", "System Serene."];

  useEffect(() => {
    const interval = setInterval(() => {
      setStep(prev => (prev < messages.length - 1 ? prev + 1 : prev));
    }, 800);
    const timer = setTimeout(() => {
      onComplete?.();
    }, 4000);
    return () => {
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, [onComplete]);

  return (
    <div className="fixed inset-0 z-[100] bg-bg flex flex-col items-center justify-center overflow-hidden font-sans">
      {/* Soft Ambient Forest Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,var(--color-accent)_0,transparent_100%)] opacity-[0.03] animate-pulse"></div>
      
      {/* Mist Layers */}
      <motion.div 
        animate={{ x: [-20, 20], opacity: [0.1, 0.2, 0.1] }}
        transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
        className="absolute top-1/4 left-0 w-full h-32 bg-accent/5 blur-3xl"
      />
      <motion.div 
        animate={{ x: [20, -20], opacity: [0.05, 0.15, 0.05] }}
        transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
        className="absolute bottom-1/4 left-0 w-full h-32 bg-accent/5 blur-3xl"
      />

      <div className="relative w-full max-w-3xl h-64 h- flex items-center justify-between px-32">
         {/* Base Station */}
         <div className="flex flex-col items-center gap-4 z-10">
            <div className="w-20 h-20 rounded-full bg-accent/5 border border-accent/20 flex items-center justify-center shadow-xl backdrop-blur-md">
               <Leaf className="w-10 h-10 text-accent/60" />
            </div>
            <span className="text-[10px] font-bold tracking-[0.4em] text-text-dim uppercase">Base_Origin</span>
         </div>

         {/* Leafy Path Animation */}
         <div className="absolute left-64 right-64 top-1/2 -translate-y-1/2 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent"></div>
         
         <motion.div
           initial={{ x: 0, opacity: 0 }}
           animate={{ x: "280%", opacity: 1 }}
           transition={{ duration: 3.5, ease: "easeInOut" }}
           className="absolute left-[200px] top-[100px] z-20"
         >
           <SoothingRoverSVG />
           <motion.div 
             animate={{ opacity: [0.1, 0.3, 0.1], scale: [0.8, 1.1, 0.8] }}
             transition={{ duration: 2, repeat: Infinity }}
             className="absolute -bottom-8 left-1/2 -translate-x-1/2"
           >
              <Sparkles className="w-4 h-4 text-accent/50" />
           </motion.div>
         </motion.div>

         {/* Forest Objective */}
         <div className="flex flex-col items-center gap-4 z-10">
            <div className="w-20 h-20 rounded-full bg-accent/5 border border-accent/20 flex items-center justify-center shadow-xl backdrop-blur-md">
               <Trees className="w-10 h-10 text-accent" />
            </div>
            <span className="text-[10px] font-bold tracking-[0.4em] text-text-dim uppercase">Forest_Heart</span>
         </div>
      </div>

      <div className="mt-20 flex flex-col items-center gap-6">
         <motion.div
           key={step}
           initial={{ opacity: 0, y: 10 }}
           animate={{ opacity: 1, y: 0 }}
           className="text-xl font-light italic text-text-primary tracking-wide text-center"
         >
           {messages[step]}
         </motion.div>
         
         <div className="w-64 h-1 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: "100%" }}
              transition={{ duration: 4, ease: "linear" }}
              className="h-full bg-accent/30 shadow-[0_0_20px_var(--color-accent)]"
            />
         </div>
      </div>

      {/* Decorative Floating Leaves */}
      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          animate={{ 
            y: [-20, 20], 
            x: [-10, 10], 
            rotate: [0, 360],
            opacity: [0.1, 0.3, 0.1]
          }}
          transition={{ 
            duration: 5 + i, 
            repeat: Infinity, 
            ease: "easeInOut",
            delay: i * 0.5 
          }}
          className="absolute pointer-events-none"
          style={{ 
            top: `${20 + (i * 15)}%`, 
            left: `${10 + (i * 15)}%` 
          }}
        >
          <Leaf className="w-4 h-4 text-accent/20" />
        </motion.div>
      ))}
    </div>
  );
}
