import { useState } from 'react'
import { useAOStore } from './store/aoStore'
import { LiveDashboard } from './components/Dashboard/LiveDashboard'
import { motion } from 'framer-motion'
import { Play, Sparkles } from 'lucide-react'

export default function App() {
  const { activeSessionId, connectWebSocket } = useAOStore()
  const [loading, setLoading] = useState(false)
  const [sessionName, setSessionName] = useState("Observatory Run " + new Date().toLocaleTimeString())

  async function handleStartSession() {
    setLoading(true)
    try {
      const resp = await fetch("http://localhost:8000/api/v1/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: sessionName,
          description: "Lab turbulence screen run",
          target_name: "Sirius",
          frame_rate_hz: 20.0
        })
      });
      const data = await resp.json()
      if (data && data.id) {
        connectWebSocket(data.id)
      }
    } catch (err) {
      console.error("Failed to start session:", err)
      alert("Backend server is not running. Please make sure to run the simulation script first!")
    } finally {
      setLoading(false)
    }
  }

  // If session is active, render dashboard
  if (activeSessionId) {
    return <LiveDashboard />
  }

  return (
    <div className="h-screen w-screen bg-black text-white flex items-center justify-center font-sans overflow-hidden relative">
      {/* Background Starscape decoration */}
      <div className="absolute inset-0 bg-radial-at-c from-bg-card via-black to-black opacity-60" />
      <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:24px_24px] opacity-25" />
      
      {/* Cinematic grid element */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-[600px] h-[600px] rounded-full border border-accent-blue/10 animate-spin-slow absolute" />
        <div className="w-[800px] h-[800px] rounded-full border border-accent-purple/5 animate-spin-reverse absolute" />
      </div>

      <motion.div 
        className="z-10 flex flex-col items-center text-center max-w-lg px-6"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1.0, ease: "easeOut" }}
      >
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-accent-blue via-blue-600 to-accent-purple flex items-center justify-center border border-accent-blue/20 shadow-2xl shadow-accent-blue/30 mb-8 relative">
          <Sparkles className="w-10 h-10 text-white animate-pulse" />
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-accent-orange animate-ping" />
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-accent-orange flex items-center justify-center">
            <Sparkles className="w-2 h-2 text-white" />
          </div>
        </div>

        <motion.h1 
          className="text-4xl font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-100 to-accent-blue"
          initial={{ letterSpacing: "0.1em" }}
          animate={{ letterSpacing: "0.2em" }}
          transition={{ duration: 1.5 }}
        >
          ASTROAO
        </motion.h1>
        
        <p className="text-xs font-mono tracking-widest text-slate-500 uppercase mt-2">
          Adaptive Optics Intelligence Platform
        </p>

        <p className="text-sm text-slate-400 mt-6 leading-relaxed">
          Atmospheric turbulence distorts incoming wavefronts. AstroAO centroiding and least-squares modal reconstruction engines correct optical distortions in real-time.
        </p>

        <div className="mt-10 flex flex-col gap-3 w-full">
          <input 
            type="text"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            className="px-4 py-2.5 rounded-lg bg-bg-card border border-border-subtle text-slate-200 text-sm font-mono text-center focus:outline-none focus:border-accent-blue/50 transition-all shadow-inner"
            placeholder="Session Name"
          />

          <button
            onClick={handleStartSession}
            disabled={loading}
            className="w-full py-3 px-6 rounded-lg bg-gradient-to-r from-accent-blue to-blue-600 hover:from-blue-600 hover:to-accent-purple text-white text-sm font-mono font-semibold tracking-wider flex items-center justify-center gap-2 transition-all shadow-lg shadow-accent-blue/20 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
          >
            {loading ? (
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Start Observatory Loop</span>
              </>
            )}
          </button>
        </div>

        <div className="mt-8 text-[10px] font-mono text-slate-600">
          <span>Target MLA Layout: 16x16 Grid</span>
          <span className="mx-2">•</span>
          <span>Target DM Geometry: Fried 17x17 Grid</span>
        </div>
      </motion.div>
    </div>
  )
}
