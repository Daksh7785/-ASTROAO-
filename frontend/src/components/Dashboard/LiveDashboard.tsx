import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Suspense, useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { StarField } from '../../three/StarField'
import { WavefrontSurface } from '../../three/WavefrontSurface'
import { DMMirrorSurface } from '../../three/DMMirrorSurface'
import { useAOStore } from '../../store/aoStore'
import { Zap, AlertTriangle, CloudRain, ShieldCheck, RefreshCw, Layers } from 'lucide-react'

// Zernike mode names mapping
const ZERNIKE_NAMES = [
  "Tip X", "Tilt Y", "Defocus", "Astig 45°", "Astig 0°", 
  "Coma X", "Coma Y", "Trefoil X", "Trefoil Y", "Spherical",
  "Sec Astig 0°", "Sec Astig 45°", "Mode 14", "Mode 15", "Mode 16",
  "Mode 17", "Mode 18", "Mode 19", "Mode 20", "Mode 21", "Mode 22"
]

export function LiveDashboard() {
  const { isConnected, loopRate, processingLatency, currentFrame, anomalies, disconnectWebSocket } = useAOStore()
  const [activeTab, setActiveTab] = useState<'3d' | 'stats' | 'psf'>('3d')
  
  const r0_cm = currentFrame ? currentFrame.r0_meters * 100.0 : 15.0
  const tau0 = currentFrame ? currentFrame.tau0_ms : 10.0
  const strehl = currentFrame ? currentFrame.strehl_estimate * 100.0 : 80.0
  const greenwood = currentFrame ? 0.427 / (currentFrame.tau0_ms / 1000.0) : 42.7
  
  // Reshape dm_voltages array to 2D for grid view (17x17 actuators)
  const actGridSize = 17
  const dmVoltages2D = useMemo(() => {
    if (!currentFrame || !currentFrame.dm_voltages) return []
    const grid = []
    for (let i = 0; i < actGridSize; i++) {
      grid.push(currentFrame.dm_voltages.slice(i * actGridSize, (i + 1) * actGridSize))
    }
    return grid
  }, [currentFrame])

  function getVoltageColor(v: number) {
    if (v > 0) {
      const alpha = Math.min(1, v / 1.0)
      return `rgba(249, 115, 22, ${alpha})` // orange
    } else {
      const alpha = Math.min(1, Math.abs(v) / 1.0)
      return `rgba(168, 85, 247, ${alpha})` // purple
    }
  }

  return (
    <div className="h-screen w-screen bg-bg-secondary text-text-primary flex flex-col font-sans select-none">
      {/* Cinematic Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-black/85 border-b border-border-subtle backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-accent-blue to-accent-purple flex items-center justify-center border border-accent-blue/30 shadow-lg shadow-accent-blue/20">
            <Layers className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-accent-blue">ASTROAO</h1>
            <p className="text-[10px] text-slate-500 font-mono tracking-widest uppercase">Adaptive Optics Intelligence</p>
          </div>
        </div>
        
        {/* Real-time loop stats */}
        <div className="flex items-center gap-8">
          <div className="flex flex-col items-center">
            <span className="text-[9px] font-mono text-slate-500 uppercase">Loop Status</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-accent-green animate-pulse' : 'bg-accent-red'}`} />
              <span className="text-xs font-mono font-semibold uppercase">{isConnected ? "Closed-Loop" : "Open-Loop"}</span>
            </div>
          </div>
          <div className="w-px h-8 bg-border-subtle" />
          <div className="flex flex-col">
            <span className="text-[9px] font-mono text-slate-500 uppercase">Loop Rate</span>
            <span className="text-sm font-mono font-bold text-accent-green">{loopRate.toFixed(1)} Hz</span>
          </div>
          <div className="w-px h-8 bg-border-subtle" />
          <div className="flex flex-col">
            <span className="text-[9px] font-mono text-slate-500 uppercase">Processing Latency</span>
            <span className="text-sm font-mono font-bold text-accent-blue">{processingLatency.toFixed(2)} ms</span>
          </div>
          <button 
            onClick={disconnectWebSocket}
            className="px-4 py-1.5 rounded-md border border-accent-red/30 hover:bg-accent-red/10 text-accent-red text-xs font-mono transition-all"
          >
            Disconnect
          </button>
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="flex-1 grid grid-cols-12 gap-4 p-4 overflow-hidden">
        {/* Left Side: 3D Live Feed Scene */}
        <div className="col-span-8 flex flex-col border border-border-subtle rounded-xl bg-black/40 overflow-hidden relative">
          <div className="absolute top-4 left-4 z-10 flex gap-2">
            <button 
              onClick={() => setActiveTab('3d')}
              className={`px-3 py-1 text-xs font-mono rounded-md border transition-all ${activeTab === '3d' ? 'bg-accent-blue/20 border-accent-blue text-accent-blue' : 'border-border-subtle bg-slate-950/80 text-slate-400 hover:text-white'}`}
            >
              3D Hologram
            </button>
            <button 
              onClick={() => setActiveTab('stats')}
              className={`px-3 py-1 text-xs font-mono rounded-md border transition-all ${activeTab === 'stats' ? 'bg-accent-blue/20 border-accent-blue text-accent-blue' : 'border-border-subtle bg-slate-950/80 text-slate-400 hover:text-white'}`}
            >
              DM Voltage Grid
            </button>
            <button 
              onClick={() => setActiveTab('psf')}
              className={`px-3 py-1 text-xs font-mono rounded-md border transition-all ${activeTab === 'psf' ? 'bg-accent-blue/20 border-accent-blue text-accent-blue' : 'border-border-subtle bg-slate-950/80 text-slate-400 hover:text-white'}`}
            >
              PSF Simulator
            </button>
          </div>
          
          <div className="absolute top-4 right-4 z-10 font-mono text-[10px] text-slate-500 bg-slate-950/85 px-3 py-1.5 rounded border border-border-subtle flex gap-4">
            {activeTab === 'psf' ? (
              <span>Diffraction-Limited Spot profile</span>
            ) : (
              <>
                <span>[Left] Wavefront W(x,y)</span>
                <span>[Right] Deformable Mirror A(x,y)</span>
              </>
            )}
          </div>

          {activeTab === '3d' && (
            <div className="flex-1 relative">
              <Canvas camera={{ position: [0, 1.8, 4.2], fov: 45 }}>
                <ambientLight intensity={0.2} />
                <directionalLight position={[2, 4, 3]} intensity={1.5} color="#5786f5" />
                <pointLight position={[-2, -3, -2]} intensity={0.5} color="#a855f7" />
                <Suspense fallback={null}>
                  <StarField count={10000} />
                  <WavefrontSurface />
                  <DMMirrorSurface />
                </Suspense>
                <OrbitControls enablePan={false} minDistance={2} maxDistance={10} />
              </Canvas>
            </div>
          )}

          {activeTab === 'stats' && (
            <div className="flex-1 flex items-center justify-center p-8 bg-bg-card/40">
              <div className="flex flex-col items-center bg-black/60 p-6 rounded-xl border border-border-subtle">
                <span className="text-xs font-mono text-slate-400 mb-4 uppercase tracking-wider">Deformable Mirror Actuator Grid (17x17)</span>
                {dmVoltages2D.length > 0 ? (
                  <div className="grid gap-1 border border-border-subtle p-2 bg-slate-950 rounded-lg">
                    {dmVoltages2D.map((row, r_idx) => (
                      <div key={r_idx} className="flex gap-1">
                        {row.map((val, c_idx) => (
                          <div 
                            key={c_idx} 
                            style={{ backgroundColor: getVoltageColor(val) }}
                            className="w-3.5 h-3.5 rounded-sm border border-black/30 transition-colors duration-100 hover:scale-125"
                            title={`Actuator [${r_idx}, ${c_idx}]: ${val.toFixed(3)} V`}
                          />
                        ))}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-slate-500 font-mono text-xs py-16">Waiting for actuator command streaming...</div>
                )}
                <div className="flex gap-6 mt-4 text-[10px] font-mono text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded bg-purple-500" />
                    <span>Push (-1.0V)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded bg-slate-800" />
                    <span>Neutral (0.0V)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2.5 h-2.5 rounded bg-orange-500" />
                    <span>Pull (+1.0V)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'psf' && (
            <div className="flex-1 flex flex-col items-center justify-center p-8 bg-bg-card/40 relative">
              <div className="flex flex-col items-center bg-black/60 p-6 rounded-xl border border-border-subtle">
                <span className="text-xs font-mono text-slate-400 mb-4 uppercase tracking-wider">Point Spread Function (PSF) Simulation</span>
                {currentFrame && currentFrame.psf_map ? (
                  <PSFHeatmap data={currentFrame.psf_map} />
                ) : (
                  <div className="text-slate-500 font-mono text-xs py-24">Calculating PSF from wavefront diffraction...</div>
                )}
                <span className="text-[10px] font-mono text-slate-500 mt-4 text-center max-w-sm">
                  The PSF shows the optical quality of the telescope's focus. A narrow, circular central core (Airy disk) indicates high correction quality.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Observatory Telemetry Panels */}
        <div className="col-span-4 flex flex-col gap-4 overflow-hidden">
          
          {/* Panel 1: Atmospheric Turbulence Parameters */}
          <section className="bg-bg-card border border-border-subtle rounded-xl p-4 flex flex-col gap-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-border-subtle pb-2">
              <h2 className="text-xs font-mono font-bold tracking-wider text-accent-blue uppercase flex items-center gap-1.5">
                <CloudRain className="w-4 h-4" /> Atmospheric Seeing
              </h2>
              <span className="text-[10px] font-mono text-slate-500 font-semibold bg-slate-900 px-2 py-0.5 rounded border border-border-subtle">Real-Time</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              {/* Fried Parameter */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Fried Parameter (r0)</span>
                <span className="text-2xl font-mono font-bold text-white mt-1 group-hover:text-accent-blue transition-colors">
                  {r0_cm.toFixed(1)} <span className="text-xs text-slate-500">cm</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Coherence Diameter</span>
              </div>
              
              {/* Coherence Time */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Coherence Time (τ0)</span>
                <span className="text-2xl font-mono font-bold text-white mt-1 group-hover:text-accent-purple transition-colors">
                  {tau0.toFixed(1)} <span className="text-xs text-slate-500">ms</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Atmosphere Timescale</span>
              </div>

              {/* Strehl Ratio */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Strehl Ratio</span>
                <span className="text-2xl font-mono font-bold text-accent-green mt-1">
                  {strehl.toFixed(1)} <span className="text-xs text-slate-500">%</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Predicted Science Quality</span>
              </div>

              {/* Greenwood Frequency */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Greenwood Freq</span>
                <span className="text-2xl font-mono font-bold text-white mt-1">
                  {greenwood.toFixed(1)} <span className="text-xs text-slate-500">Hz</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Required DM Bandwidth</span>
              </div>

              {/* Wind Speed */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Wind Velocity</span>
                <span className="text-2xl font-mono font-bold text-white mt-1">
                  {(currentFrame?.wind_speed ?? 8.5).toFixed(1)} <span className="text-xs text-slate-500">m/s</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Atmospheric Advection</span>
              </div>

              {/* Wind Heading */}
              <div className="bg-black/45 p-3 rounded-lg border border-border-subtle/50 flex flex-col relative overflow-hidden group">
                <span className="text-[10px] font-mono text-slate-400 uppercase">Wind Heading</span>
                <span className="text-2xl font-mono font-bold text-white mt-1">
                  {(currentFrame?.wind_direction ?? 225.0).toFixed(0)}<span className="text-xs text-slate-500">°</span>
                </span>
                <span className="text-[8px] text-slate-500 font-mono mt-0.5">Advection Angle</span>
              </div>
            </div>
          </section>

          {/* Panel 2: Zernike Coefficients Waterfall Spectrum */}
          <section className="bg-bg-card border border-border-subtle rounded-xl p-4 flex-1 flex flex-col gap-3 overflow-hidden shadow-xl">
            <h2 className="text-xs font-mono font-bold tracking-wider text-accent-purple uppercase flex items-center gap-1.5 border-b border-border-subtle pb-2">
              <RefreshCw className="w-4 h-4 animate-spin-slow" /> Aberration Spectrum (Zernike)
            </h2>
            
            <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-1.5">
              {ZERNIKE_NAMES.map((name, idx) => {
                const coeff = currentFrame ? currentFrame.zernike_coeffs[idx] || 0.0 : 0.0
                const percent = Math.min(100, Math.abs(coeff) * 200) // Scale for visualization
                
                return (
                  <div key={idx} className="flex items-center text-[11px] font-mono hover:bg-black/20 py-0.5 px-1 rounded transition-colors">
                    <span className="w-5 text-slate-500 font-semibold">Z{idx+2}</span>
                    <span className="w-20 text-slate-300 truncate">{name}</span>
                    <div className="flex-1 mx-3 bg-slate-900 h-2.5 rounded-full overflow-hidden relative border border-border-subtle">
                      <motion.div 
                        animate={{ width: `${percent}%` }}
                        transition={{ duration: 0.1 }}
                        style={{ originX: 0 }}
                        className={`h-full rounded-full ${coeff > 0 ? 'bg-gradient-to-r from-accent-blue to-accent-purple' : 'bg-gradient-to-r from-accent-purple to-accent-orange'}`}
                      />
                    </div>
                    <span className="w-12 text-right font-bold tabular-nums text-slate-200">
                      {coeff.toFixed(3)}
                    </span>
                  </div>
                )
              })}
            </div>
          </section>

          {/* Panel 3: AI Anomaly & Saturation Feed */}
          <section className="bg-bg-card border border-border-subtle rounded-xl p-4 h-48 flex flex-col gap-2 overflow-hidden shadow-xl">
            <h2 className="text-xs font-mono font-bold tracking-wider text-accent-orange uppercase flex items-center gap-1.5 border-b border-border-subtle pb-2">
              <AlertTriangle className="w-4 h-4 text-accent-orange" /> Real-time Anomaly Feed
            </h2>
            
            <div className="flex-1 overflow-y-auto flex flex-col gap-2">
              <AnimatePresence>
                {anomalies.length > 0 ? (
                  anomalies.map((anom) => (
                    <motion.div 
                      key={anom.id}
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className={`p-2 rounded border text-xs font-mono flex items-start gap-2 ${anom.severity === 'critical' ? 'bg-accent-red/10 border-accent-red/20 text-accent-red' : 'bg-accent-orange/10 border-accent-orange/20 text-accent-orange'}`}
                    >
                      <Zap className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <div className="flex justify-between font-bold">
                          <span>{anom.anomaly_type.toUpperCase()}</span>
                          <span className="text-[10px] text-slate-500">Frame #{anom.frame_number}</span>
                        </div>
                        <p className="text-[11px] mt-0.5 text-slate-300 leading-normal">{anom.description}</p>
                      </div>
                    </motion.div>
                  ))
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-6 font-mono">
                    <ShieldCheck className="w-6 h-6 text-accent-green mb-1" />
                    <span>System nominal. No loop errors.</span>
                  </div>
                )}
              </AnimatePresence>
            </div>
          </section>
          
        </div>
      </main>
    </div>
  )
}

export function PSFHeatmap({ data }: { data: number[][] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  
  useEffect(() => {
    if (!data || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    const size = data.length
    const scale = canvas.width / size
    
    const imgData = ctx.createImageData(canvas.width, canvas.height)
    
    for (let y = 0; y < canvas.height; y++) {
      for (let x = 0; x < canvas.width; x++) {
        const dataX = Math.floor(x / scale)
        const dataY = Math.floor(y / scale)
        
        const val = data[dataY] && data[dataY][dataX] !== undefined ? data[dataY][dataX] : 0.0
        
        // Render a false-color glow: black -> dark purple -> blue -> cyan -> white
        const r = Math.floor(Math.pow(val, 3) * 255)
        const g = Math.floor(Math.pow(val, 1.5) * 210)
        const b = Math.floor(val * 140 + Math.pow(val, 2) * 115)
        
        const pixelIdx = (y * canvas.width + x) * 4
        imgData.data[pixelIdx] = r
        imgData.data[pixelIdx + 1] = g
        imgData.data[pixelIdx + 2] = b
        imgData.data[pixelIdx + 3] = 255
      }
    }
    
    ctx.putImageData(imgData, 0, 0)
  }, [data])
  
  return (
    <canvas 
      ref={canvasRef} 
      width={256} 
      height={256} 
      className="rounded-lg border border-border-subtle shadow-2xl shadow-accent-blue/15 bg-black"
    />
  )
}
