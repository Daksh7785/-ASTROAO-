import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

export function StarField({ count = 10000 }) {
  const pointsRef = useRef<THREE.Points>(null)
  
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3)
    
    for (let i = 0; i < count; i++) {
      // Place stars randomly on a large shell around the telescope
      const radius = 100 + Math.random() * 200
      const theta = Math.random() * 2.0 * Math.PI
      const phi = Math.acos(2.0 * Math.random() - 1.0)
      
      pos[i * 3]     = radius * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = radius * Math.cos(phi)
    }
    return pos
  }, [count])
  
  useFrame(({ clock }) => {
    if (!pointsRef.current) return
    const elapsed = clock.getElapsedTime()
    // Slow planetary rotation of the sky
    pointsRef.current.rotation.y = elapsed * 0.005
    pointsRef.current.rotation.x = elapsed * 0.002
  })
  
  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={1.0}
        color="#ffffff"
        sizeAttenuation={true}
        transparent
        opacity={0.8}
      />
    </points>
  )
}
