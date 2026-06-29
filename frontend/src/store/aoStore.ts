import { create } from 'zustand'

export interface FrameTelemetry {
  frame_number: number;
  timestamp: number;
  wavefront_rms: number;
  wavefront_ptv: number;
  wavefront_map: number[][];
  psf_map?: number[][];
  dm_voltages: number[];
  dm_strokes: number[];
  zernike_coeffs: number[];
  r0_meters: number;
  tau0_ms: number;
  strehl_estimate: number;
  wind_speed?: number;
  wind_direction?: number;
  processing_time_ms: number;
}

export interface AnomalyLog {
  id: string;
  frame_number: number;
  anomaly_type: string;
  severity: string;
  description: string;
  detected_at: string;
}

interface AOState {
  isConnected: boolean;
  activeSessionId: string | null;
  currentFrame: FrameTelemetry | null;
  history: FrameTelemetry[];
  anomalies: AnomalyLog[];
  loopRate: number;
  processingLatency: number;
  socket: WebSocket | null;
  
  connectWebSocket: (sessionId: string) => void;
  disconnectWebSocket: () => void;
  addAnomaly: (anomaly: AnomalyLog) => void;
  clearHistory: () => void;
}

export const useAOStore = create<AOState>((set, get) => {
  let frameCount = 0;
  let lastFpsCalc = Date.now();

  return {
    isConnected: false,
    activeSessionId: null,
    currentFrame: null,
    history: [],
    anomalies: [],
    loopRate: 0.0,
    processingLatency: 0.0,
    socket: null,

    connectWebSocket: (sessionId: string) => {
      // Disconnect existing if any
      get().disconnectWebSocket();
      
      const wsUrl = `ws://${window.location.hostname}:8000/ws/stream/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        set({ isConnected: true, activeSessionId: sessionId, socket: ws });
        frameCount = 0;
        lastFpsCalc = Date.now();
        
        // Fetch historical session stats and anomalies from REST API
        fetch(`http://${window.location.hostname}:8000/api/v1/sessions/${sessionId}/stats`)
          .then(r => r.json())
          .then(res => {
            if (res.success && res.anomalies) {
              set({ anomalies: res.anomalies });
            }
          })
          .catch(err => console.error("Error loading session initial stats:", err));
      };
      
      ws.onmessage = (event) => {
        try {
          const frame: FrameTelemetry = JSON.parse(event.data);
          
          frameCount++;
          const now = Date.now();
          const timeDiff = now - lastFpsCalc;
          let currentLoopRate = get().loopRate;
          
          if (timeDiff >= 1000) {
            currentLoopRate = (frameCount * 1000) / timeDiff;
            frameCount = 0;
            lastFpsCalc = now;
          }

          set((state) => {
            // Keep recent history (last 100 frames)
            const newHistory = [...state.history, frame].slice(-100);
            
            // Check for new anomalies in payload
            const newAnomalies = [...state.anomalies];
            
            // Simple client-side alerts fallback if sat/spike is extreme
            if (frame.dm_strokes.some(s => Math.abs(s) > 4.75)) {
              const alreadyExists = newAnomalies.some(
                a => a.frame_number === frame.frame_number && a.anomaly_type === "dm_saturation"
              );
              if (!alreadyExists) {
                newAnomalies.unshift({
                  id: Math.random().toString(),
                  frame_number: frame.frame_number,
                  anomaly_type: "dm_saturation",
                  severity: "warning",
                  description: `Mirror actuator stroke limit reached (${Math.max(...frame.dm_strokes.map(Math.abs)).toFixed(2)} um)`,
                  detected_at: new Date().toISOString()
                });
              }
            }

            if (frame.r0_meters < 0.05) {
              const alreadyExists = newAnomalies.some(
                a => a.frame_number === frame.frame_number && a.anomaly_type === "turbulence_spike"
              );
              if (!alreadyExists) {
                newAnomalies.unshift({
                  id: Math.random().toString(),
                  frame_number: frame.frame_number,
                  anomaly_type: "turbulence_spike",
                  severity: "critical",
                  description: `Severe atmospheric seeing drop (r0 is ${ (frame.r0_meters*100).toFixed(1) } cm)`,
                  detected_at: new Date().toISOString()
                });
              }
            }

            return {
              currentFrame: frame,
              history: newHistory,
              loopRate: currentLoopRate,
              processingLatency: frame.processing_time_ms,
              anomalies: newAnomalies.slice(0, 50)  // Keep last 50 anomalies
            };
          });
        } catch (e) {
          console.error("Error parsing WebSocket frame message:", e);
        }
      };
      
      ws.onclose = () => {
        set({ isConnected: false, activeSessionId: null, socket: null });
      };
      
      ws.onerror = (err) => {
        console.error("WebSocket encountered an error:", err);
      };
    },

    disconnectWebSocket: () => {
      const { socket } = get();
      if (socket) {
        socket.close();
      }
      set({ isConnected: false, activeSessionId: null, socket: null });
    },

    addAnomaly: (anomaly: AnomalyLog) => {
      set((state) => ({
        anomalies: [anomaly, ...state.anomalies].slice(0, 50)
      }));
    },

    clearHistory: () => {
      set({ history: [], anomalies: [] });
    }
  };
});
