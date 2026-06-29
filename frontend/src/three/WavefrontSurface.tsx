import { useRef, useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { useAOStore } from '../store/aoStore'

// Helper function to map a phase value to a colormap (Turbo-like)
function getPhaseColor(value: number, maxVal: number): THREE.Color {
  const norm = Math.max(0, Math.min(1, (value / (maxVal || 1.0)) * 0.5 + 0.5))
  // Simple RGB interpolation
  let r = 0, g = 0, b = 0
  if (norm < 0.25) {
    b = 1.0
    g = norm * 4.0
  } else if (norm < 0.5) {
    g = 1.0
    b = 1.0 - (norm - 0.25) * 4.0
  } else if (norm < 0.75) {
    r = (norm - 0.5) * 4.0
    g = 1.0
  } else {
    r = 1.0
    g = 1.0 - (norm - 0.75) * 4.0
  }
  return new THREE.Color(r, g, b)
}

export function WavefrontSurface() {
  const geomRef = useRef<THREE.BufferGeometry>(null)
  const meshRef = useRef<THREE.Mesh>(null)
  const { currentFrame } = useAOStore()
  
  const gridSize = 64
  
  // Precompute grid vertices
  const [positions, colors, indices] = useMemo(() => {
    const posList = []
    const colList = []
    const idxList = []
    
    // Create grid centered at origin
    for (let y = 0; y < gridSize; y++) {
      for (let x = 0; x < gridSize; x++) {
        const xp = (x - gridSize / 2.0) * 0.08
        const yp = (y - gridSize / 2.0) * 0.08
        posList.push(xp, yp, 0.0) // start flat
        colList.push(0.0, 0.0, 0.5) // dark blue
      }
    }
    
    // Build triangle index arrays
    for (let y = 0; y < gridSize - 1; y++) {
      for (let x = 0; x < gridSize - 1; x++) {
        const i0 = y * gridSize + x
        const i1 = i0 + 1
        const i2 = (y + 1) * gridSize + x
        const i3 = i2 + 1
        
        idxList.push(i0, i1, i2)
        idxList.push(i1, i3, i2)
      }
    }
    
    return [
      new Float32Array(posList),
      new Float32Array(colList),
      idxList
    ]
  }, [])
  
  // Synchronize incoming frame map with geometry attributes
  useEffect(() => {
    if (!currentFrame || !currentFrame.wavefront_map || !geomRef.current) return
    
    const geom = geomRef.current
    const posAttr = geom.getAttribute('position') as THREE.BufferAttribute
    const colAttr = geom.getAttribute('color') as THREE.BufferAttribute
    
    const wfMap = currentFrame.wavefront_map
    
    // Find maximum absolute value for color normalization
    let maxAbs = 0.001
    for (let y = 0; y < gridSize; y++) {
      for (let x = 0; x < gridSize; x++) {
        const val = Math.abs(wfMap[y][x])
        if (val > maxAbs) maxAbs = val
      }
    }
    
    for (let y = 0; y < gridSize; y++) {
      for (let x = 0; x < gridSize; x++) {
        const idx = y * gridSize + x
        const val = wfMap[y][x]
        
        // Displace height (z axis)
        posAttr.setZ(idx, val * 0.1) // scale displacement
        
        // Map color
        const col = getPhaseColor(val, maxAbs)
        colAttr.setXYZ(idx, col.r, col.g, col.b)
      }
    }
    
    posAttr.needsUpdate = true
    colAttr.needsUpdate = true
    geom.computeVertexNormals()
  }, [currentFrame])
  
  return (
    <group position={[-1.5, 0, 0]} rotation={[-Math.PI / 3, 0, 0.2]}>
      <mesh ref={meshRef}>
        <bufferGeometry ref={geomRef}>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
          <bufferAttribute
            attach="attributes-color"
            args={[colors, 3]}
          />
          <bufferAttribute
            attach="index"
            args={[new Uint16Array(indices), 1]}
          />
        </bufferGeometry>
        <meshStandardMaterial
          vertexColors
          roughness={0.2}
          metalness={0.1}
          side={THREE.DoubleSide}
          flatShading={false}
          wireframe={false}
        />
      </mesh>
      {/* Wireframe overlay to emphasize surface contour */}
      <mesh position={[0, 0, 0.002]}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
          <bufferAttribute
            attach="index"
            args={[new Uint16Array(indices), 1]}
          />
        </bufferGeometry>
        <meshBasicMaterial
          color="#0ea5e9"
          wireframe
          transparent
          opacity={0.06}
        />
      </mesh>
    </group>
  )
}
