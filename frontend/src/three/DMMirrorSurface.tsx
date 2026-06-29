import { useRef, useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { useAOStore } from '../store/aoStore'

export function DMMirrorSurface() {
  const geomRef = useRef<THREE.BufferGeometry>(null)
  const actuatorsRef = useRef<THREE.Group>(null)
  const { currentFrame } = useAOStore()
  
  const actGridSize = 17 // 16x16 lenslets + 1 = 17x17 actuators
  
  // Mirror grid sheet size (higher resolution for smooth draping)
  const sheetResolution = 32
  const [positions, indices] = useMemo(() => {
    const posList = []
    const idxList = []
    
    for (let y = 0; y < sheetResolution; y++) {
      for (let x = 0; x < sheetResolution; x++) {
        const xp = (x - sheetResolution / 2.0) * 0.08
        const yp = (y - sheetResolution / 2.0) * 0.08
        posList.push(xp, yp, 0.0)
      }
    }
    
    for (let y = 0; y < sheetResolution - 1; y++) {
      for (let x = 0; x < sheetResolution - 1; x++) {
        const i0 = y * sheetResolution + x
        const i1 = i0 + 1
        const i2 = (y + 1) * sheetResolution + x
        const i3 = i2 + 1
        idxList.push(i0, i1, i2)
        idxList.push(i1, i3, i2)
      }
    }
    
    return [new Float32Array(posList), idxList]
  }, [])
  
  // Generate visual actuator markers (cylinders)
  const actuatorMarkers = useMemo(() => {
    const list = []
    for (let y = 0; y < actGridSize; y++) {
      for (let x = 0; x < actGridSize; x++) {
        const xp = (x - actGridSize / 2.0) * 0.16
        const yp = (y - actGridSize / 2.0) * 0.16
        list.push({ id: y * actGridSize + x, x: xp, y: yp })
      }
    }
    return list
  }, [])
  
  useEffect(() => {
    if (!currentFrame || !currentFrame.dm_strokes || !geomRef.current) return
    
    const geom = geomRef.current
    const posAttr = geom.getAttribute('position') as THREE.BufferAttribute
    const strokes = currentFrame.dm_strokes
    
    // 1. Update mirror sheet vertices using Gaussian interpolation of nearby actuators
    // stroke pitch relative to sheet dimensions
    for (let sy = 0; sy < sheetResolution; sy++) {
      for (let sx = 0; sx < sheetResolution; sx++) {
        const idx = sy * sheetResolution + sx
        const px = (sx - sheetResolution / 2.0) * 0.08
        const py = (sy - sheetResolution / 2.0) * 0.08
        
        let z_height = 0.0
        // Gaussian interpolation across all 17x17 actuators
        for (let ay = 0; ay < actGridSize; ay++) {
          for (let ax = 0; ax < actGridSize; ax++) {
            const actIdx = ay * actGridSize + ax
            const axp = (ax - actGridSize / 2.0) * 0.16
            const ayp = (ay - actGridSize / 2.0) * 0.16
            
            const stroke = strokes[actIdx] || 0.0
            const dist2 = (px - axp)**2 + (py - ayp)**2
            z_height += stroke * 0.08 * Math.exp(-dist2 / (2 * 0.15**2))
          }
        }
        
        posAttr.setZ(idx, z_height)
      }
    }
    posAttr.needsUpdate = true
    geom.computeVertexNormals()
    
    // 2. Move physical actuator cylinder markers underneath
    if (actuatorsRef.current) {
      const markers = actuatorsRef.current.children
      for (let i = 0; i < markers.length; i++) {
        const marker = markers[i] as THREE.Mesh
        const strokeVal = strokes[i] || 0.0
        // Move cylinder vertically
        marker.position.z = strokeVal * 0.08
        // Update emissive color based on voltage polarity
        const mat = marker.material as THREE.MeshStandardMaterial
        if (strokeVal > 0) {
          mat.emissive.setRGB(strokeVal * 0.15, strokeVal * 0.08, 0.0) // gold/orange glow
        } else {
          mat.emissive.setRGB(0.0, Math.abs(strokeVal) * 0.05, Math.abs(strokeVal) * 0.2) // purple/blue glow
        }
      }
    }
  }, [currentFrame])
  
  return (
    <group position={[1.5, 0, 0]} rotation={[-Math.PI / 3, 0, -0.2]}>
      {/* Reflection mirror sheet */}
      <mesh>
        <bufferGeometry ref={geomRef}>
          <bufferAttribute
            attach="attributes-position"
            args={[positions, 3]}
          />
          <bufferAttribute
            attach="index"
            args={[new Uint16Array(indices), 1]}
          />
        </bufferGeometry>
        <meshStandardMaterial
          color="#3e4555"
          roughness={0.05}
          metalness={0.9}
          roughnessMap={null}
          side={THREE.DoubleSide}
        />
      </mesh>
      
      {/* Actuators grid underneath */}
      <group ref={actuatorsRef} position={[0, 0, -0.15]}>
        {actuatorMarkers.map((act) => (
          <mesh key={act.id} position={[act.x, act.y, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.02, 0.02, 0.2, 8]} />
            <meshStandardMaterial
              color="#1a202c"
              emissive={new THREE.Color(0, 0, 0)}
              roughness={0.4}
              metalness={0.5}
            />
          </mesh>
        ))}
      </group>
      
      {/* Backplate base */}
      <mesh position={[0, 0, -0.25]}>
        <planeGeometry args={[2.7, 2.7]} />
        <meshStandardMaterial color="#0a0a0f" roughness={0.8} />
      </mesh>
    </group>
  )
}
