"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import type { Points } from "three";

const PARTICLE_COUNT = 180;

function ParticleField() {
  const points = useRef<Points>(null);
  const positions = useMemo(() => {
    const values = new Float32Array(PARTICLE_COUNT * 3);
    // Deterministic distribution: visual polish must not cause hydration flicker.
    let seed = 1701;
    const random = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    for (let index = 0; index < PARTICLE_COUNT; index += 1) {
      const offset = index * 3;
      values[offset] = (random() - 0.5) * 8;
      values[offset + 1] = (random() - 0.5) * 6;
      values[offset + 2] = (random() - 0.5) * 2;
    }
    return values;
  }, []);

  useFrame((state) => {
    if (!points.current) return;
    points.current.rotation.y = state.clock.elapsedTime * 0.025;
    points.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.12) * 0.035;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#61aaff" size={0.045} sizeAttenuation transparent opacity={0.88} />
    </points>
  );
}

export function AuthScene() {
  return (
    <div className="auth-scene" aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 4.5], fov: 48 }} dpr={[1, 1.5]}>
        <ParticleField />
      </Canvas>
      <span className="auth-scene-orb auth-scene-orb-one" />
      <span className="auth-scene-orb auth-scene-orb-two" />
    </div>
  );
}
