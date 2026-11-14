// Stylised 3D digital twin of the field. This is an illustration built from zone data,
// not a photogrammetric reconstruction.
import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useStore } from '../store'
import { LAYERS, layerValue, rampColor } from '../data/scoring'
import type { Zone } from '../data/types'

const CELL = 1
const GAP = 0.06
const LETTERS = 'ABCDEFGHIJKL'
const PLANTS = 3 // plants per zone side
const LABEL_COLOR: Record<string, string> = { healthy: '#63d394', discoloration: '#f0a93b', wilting: '#ef5a4c' }

const zx = (z: { col: number }, cols: number) => (z.col - (cols - 1) / 2) * CELL
const zz = (z: { row: number }, rows: number) => (z.row - (rows - 1) / 2) * CELL

function useTargets() {
  const zones = useStore((s) => s.zones)
  const risks = useStore((s) => s.risks)
  const layer = useStore((s) => s.layer)
  const ndvi = useStore((s) => s.ndvi)
  const extrude = useStore((s) => s.extrude)
  return useMemo(() => {
    const def = LAYERS.find((l) => l.id === layer)!
    const maxWater = Math.max(1, ...zones.map((z) => z.water.applied_mm_7d))
    return zones.map((z) => {
      const lv = layerValue(layer, z, risks[z.id], ndvi, maxWater)
      const color = lv.missing ? ([0.16, 0.2, 0.23] as [number, number, number]) : rampColor(def.ramp, lv.v)
      const terrain = z.elevation * 0.55
      const height = 0.22 + terrain + (extrude ? lv.v * 1.15 : 0)
      return { color, height, v: lv.v }
    })
  }, [zones, risks, layer, ndvi, extrude])
}

function Zones() {
  const zones = useStore((s) => s.zones)
  const field = useStore((s) => s.field)!
  const targets = useTargets()
  const tiles = useRef<THREE.InstancedMesh>(null!)
  const plants = useRef<THREE.InstancedMesh>(null!)
  const outline = useRef<THREE.Mesh>(null!)
  const pinRing = useRef<THREE.Mesh>(null!)
  const cur = useRef<{ h: Float32Array; c: Float32Array } | null>(null)
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const col = useMemo(() => new THREE.Color(), [])
  const heights = useRef(new Float32Array(zones.length))
  heightsRef.current = heights.current

  useLayoutEffect(() => {
    cur.current = { h: new Float32Array(zones.length).fill(0.05), c: new Float32Array(zones.length * 3).fill(0.1) }
  }, [zones.length])

  useFrame((_, dt) => {
    const st = cur.current
    if (!st) return
    const k = 1 - Math.exp(-dt * 7)
    const { hovered, pinned } = useStore.getState()
    for (let i = 0; i < zones.length; i++) {
      const z = zones[i], t = targets[i]
      const active = z.id === hovered || z.id === pinned
      const th = t.height + (active ? 0.18 : 0)
      st.h[i] += (th - st.h[i]) * k
      for (let j = 0; j < 3; j++) st.c[i * 3 + j] += (t.color[j] - st.c[i * 3 + j]) * k
      const h = st.h[i]
      heights.current[i] = h
      const x = zx(z, field.cols), zc = zz(z, field.rows)
      dummy.position.set(x, h / 2, zc)
      dummy.scale.set(CELL - GAP, h, CELL - GAP)
      dummy.rotation.set(0, 0, 0)
      dummy.updateMatrix()
      tiles.current.setMatrixAt(i, dummy.matrix)
      const boost = active ? 1.25 : 1
      col.setRGB(st.c[i * 3] * boost, st.c[i * 3 + 1] * boost, st.c[i * 3 + 2] * boost, THREE.SRGBColorSpace)
      tiles.current.setColorAt(i, col)
      // crop rows: plant size follows the simulated health score
      const hs = 0.35 + 0.65 * (z.health.score / 100)
      for (let p = 0; p < PLANTS * PLANTS; p++) {
        const px = ((p % PLANTS) + 0.5) / PLANTS - 0.5, pz = (Math.floor(p / PLANTS) + 0.5) / PLANTS - 0.5
        dummy.position.set(x + px * (CELL - 0.2), h + 0.11 * hs, zc + pz * (CELL - 0.2))
        dummy.scale.set(0.9 * hs, hs, 0.9 * hs)
        dummy.rotation.set(z.health.last_label === 'wilting' ? 0.5 : 0, p * 1.3, 0)
        dummy.updateMatrix()
        plants.current.setMatrixAt(i * PLANTS * PLANTS + p, dummy.matrix)
        const g = z.health.score / 100
        col.setRGB(0.45 - 0.3 * g, 0.38 + 0.3 * g, 0.12 + 0.1 * g, THREE.SRGBColorSpace)
        plants.current.setColorAt(i * PLANTS * PLANTS + p, col)
      }
    }
    tiles.current.instanceMatrix.needsUpdate = true
    if (tiles.current.instanceColor) tiles.current.instanceColor.needsUpdate = true
    plants.current.instanceMatrix.needsUpdate = true
    if (plants.current.instanceColor) plants.current.instanceColor.needsUpdate = true

    const place = (mesh: THREE.Mesh, id: string | null) => {
      const i = id ? zones.findIndex((z) => z.id === id) : -1
      mesh.visible = i >= 0
      if (i < 0) return
      const z = zones[i]
      mesh.position.set(zx(z, field.cols), st.h[i] + 0.012, zz(z, field.rows))
    }
    place(outline.current, hovered && hovered !== pinned ? hovered : null)
    place(pinRing.current, pinned)
  })

  const onMove = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation()
    if (e.instanceId != null) useStore.getState().setHovered(zones[e.instanceId].id)
  }
  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation()
    if (e.delta > 4) return // it was a drag (orbit), not a click
    if (e.instanceId != null) useStore.getState().togglePin(zones[e.instanceId].id)
  }

  return (
    <group>
      <instancedMesh ref={tiles} args={[undefined, undefined, zones.length]} onPointerMove={onMove} onPointerOut={() => useStore.getState().setHovered(null)} onClick={onClick} castShadow receiveShadow>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.78} metalness={0.05} />
      </instancedMesh>
      <instancedMesh ref={plants} args={[undefined, undefined, zones.length * PLANTS * PLANTS]} raycast={() => null} castShadow>
        <coneGeometry args={[0.07, 0.24, 5]} />
        <meshStandardMaterial roughness={0.9} />
      </instancedMesh>
      <mesh ref={outline} rotation={[-Math.PI / 2, 0, 0]} visible={false} raycast={() => null}>
        <ringGeometry args={[0.6, 0.67, 4, 1, Math.PI / 4]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.9} depthTest={false} />
      </mesh>
      <mesh ref={pinRing} rotation={[-Math.PI / 2, 0, 0]} visible={false} raycast={() => null}>
        <ringGeometry args={[0.58, 0.69, 4, 1, Math.PI / 4]} />
        <meshBasicMaterial color="#63d394" transparent opacity={1} depthTest={false} />
      </mesh>
    </group>
  )
}

// shared between Zones (writer) and Machine/Pins (readers) so everything sits on top of animated tiles
const heightsRef: { current: Float32Array } = { current: new Float32Array(0) }

function Machine() {
  const field = useStore((s) => s.field)!
  const zones = useStore((s) => s.zones)
  const machine = useStore((s) => s.machine)!
  const group = useRef<THREE.Group>(null!)
  const boomL = useRef<THREE.Mesh>(null!)
  const trail = useRef<THREE.InstancedMesh>(null!)
  const idx = useMemo(() => Object.fromEntries(zones.map((z, i) => [z.id, i])), [zones])
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const acc = useRef(0)
  const clock = useRef(useStore.getState().replayT)
  const pos = useRef(new THREE.Vector3())

  useFrame((_, dt) => {
    const s = useStore.getState()
    // local clock; the store copy is refreshed at ~8 Hz so React subscribers (slider) stay cheap
    if (Math.abs(clock.current - s.replayT) > 1.5) clock.current = s.replayT // scrubbed from the slider
    if (s.playing && !s.liveZone) {
      clock.current = (clock.current + dt * 6) % machine.duration_s
      acc.current += dt
      if (acc.current > 0.12) { acc.current = 0; useStore.setState({ replayT: clock.current }) }
    }
    const t = clock.current
    const step = machine.step_s
    const f = Math.min(machine.path.length - 1, t / step)
    const i0 = Math.floor(f), i1 = Math.min(machine.path.length - 1, i0 + 1), u = f - i0
    const a = zones[idx[machine.path[i0].zone_id]], b = zones[idx[machine.path[i1].zone_id]]
    let x = zx(a, field.cols) * (1 - u) + zx(b, field.cols) * u
    let z = zz(a, field.rows) * (1 - u) + zz(b, field.rows) * u
    let y = (heightsRef.current[idx[a.id]] ?? 0.5) * (1 - u) + (heightsRef.current[idx[b.id]] ?? 0.5) * u
    let heading = Math.atan2(zx(b, field.cols) - zx(a, field.cols), zz(b, field.rows) - zz(a, field.rows))
    if (s.liveZone && idx[s.liveZone] != null) {
      const lz = zones[idx[s.liveZone]]
      x = zx(lz, field.cols); z = zz(lz, field.rows); y = heightsRef.current[idx[lz.id]] ?? 0.5; heading = group.current.rotation.y
    }
    pos.current.lerp(new THREE.Vector3(x, y, z), s.liveZone ? 1 - Math.exp(-dt * 4) : 1)
    group.current.position.copy(pos.current)
    if (a !== b && !s.liveZone) group.current.rotation.y = heading
    boomL.current.scale.x = 1

    // scan trail: thin plates on every zone already passed
    const passed = s.liveZone ? machine.path.length : i0 + 1
    for (let i = 0; i < machine.path.length; i++) {
      const zi = idx[machine.path[i].zone_id], zn = zones[zi]
      const on = i < passed
      dummy.position.set(zx(zn, field.cols), (heightsRef.current[zi] ?? 0.4) + 0.006, zz(zn, field.rows))
      dummy.scale.set(on ? CELL - GAP - 0.5 : 0.0001, 1, on ? CELL - GAP - 0.5 : 0.0001)
      dummy.rotation.set(-Math.PI / 2, 0, 0)
      dummy.updateMatrix()
      trail.current.setMatrixAt(i, dummy.matrix)
    }
    trail.current.instanceMatrix.needsUpdate = true
  })

  return (
    <>
      <instancedMesh ref={trail} args={[undefined, undefined, machine.path.length]} raycast={() => null}>
        <circleGeometry args={[0.5, 4]} />
        <meshBasicMaterial color="#e8eef1" transparent opacity={0.42} depthWrite={false} />
      </instancedMesh>
      <group ref={group}>
        <group position={[0, 0.2, 0]} scale={0.9}>
          <mesh castShadow position={[0, 0.16, 0]}><boxGeometry args={[0.3, 0.16, 0.5]} /><meshStandardMaterial color="#f2c230" roughness={0.5} metalness={0.2} /></mesh>
          <mesh castShadow position={[0, 0.3, -0.06]}><boxGeometry args={[0.24, 0.16, 0.22]} /><meshStandardMaterial color="#1b2831" roughness={0.3} metalness={0.4} /></mesh>
          <mesh ref={boomL} position={[0, 0.12, -0.3]}><boxGeometry args={[1.5, 0.025, 0.035]} /><meshStandardMaterial color="#c9d5db" metalness={0.6} roughness={0.4} /></mesh>
          {[[-0.17, 0.2], [0.17, 0.2], [-0.17, -0.18], [0.17, -0.18]].map(([wx, wz], i) => (
            <mesh key={i} castShadow position={[wx, 0.07, wz]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.09, 0.09, 0.06, 14]} /><meshStandardMaterial color="#0b1116" roughness={0.9} /></mesh>
          ))}
          <mesh position={[0, 0.5, 0]}><sphereGeometry args={[0.045, 12, 12]} /><meshBasicMaterial color="#63d394" /></mesh>
          <pointLight position={[0, 0.5, 0]} color="#63d394" intensity={0.8} distance={2.5} />
        </group>
      </group>
    </>
  )
}

function Pins() {
  const field = useStore((s) => s.field)!
  const zones = useStore((s) => s.zones)
  const captures = useStore((s) => s.captures)
  const replayT = useStore((s) => Math.floor(s.replayT / 4))
  const liveZone = useStore((s) => s.liveZone)
  const machine = useStore((s) => s.machine)!
  const idx = useMemo(() => Object.fromEntries(zones.map((z, i) => [z.id, i])), [zones])
  // one pin per zone: the newest visible capture
  const pins = useMemo(() => {
    const t = liveZone ? machine.duration_s : replayT * 4 + 4
    const byZone = new Map<string, (typeof captures)[number]>()
    for (const c of [...captures].reverse()) { if (c.live || (c.t ?? 0) <= t) byZone.set(c.zone_id, c) }
    return [...byZone.values()]
  }, [captures, replayT, liveZone, machine.duration_s])
  const groups = useRef<(THREE.Group | null)[]>([])
  useFrame(({ clock }) => {
    pins.forEach((c, i) => {
      const g = groups.current[i]; const zi = idx[c.zone_id]
      if (!g || zi == null) return
      g.position.y = (heightsRef.current[zi] ?? 0.5) + (c.live ? 0.06 * Math.sin(clock.elapsedTime * 4) : 0)
    })
  })
  return (
    <>
      {pins.map((c, i) => {
        const z: Zone | undefined = zones[idx[c.zone_id]]
        if (!z) return null
        const color = LABEL_COLOR[c.edge_prediction.label] ?? '#a3b5bf'
        return (
          <group key={c.id} ref={(g) => { groups.current[i] = g }} position={[zx(z, field.cols) + 0.28, 0.5, zz(z, field.rows) - 0.28]}
            onClick={(e) => { e.stopPropagation(); useStore.setState({ modalCapture: c.id }) }}>
            <mesh position={[0, 0.2, 0]}><cylinderGeometry args={[0.008, 0.008, 0.4, 6]} /><meshBasicMaterial color={color} /></mesh>
            <mesh position={[0, 0.42, 0]}><sphereGeometry args={[c.live ? 0.085 : 0.055, 14, 14]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={c.live ? 1.4 : 0.6} /></mesh>
          </group>
        )
      })}
    </>
  )
}

function AxisLabels() {
  const field = useStore((s) => s.field)!
  const half = (field.cols * CELL) / 2
  const cls = 'pointer-events-none select-none text-[10px] font-semibold tracking-wider text-mist-400'
  return (
    <>
      {[...Array(field.cols)].map((_, c) => (
        <Html key={`c${c}`} position={[(c - (field.cols - 1) / 2) * CELL, 0, -half - 0.45]} center zIndexRange={[5, 0]}><span className={cls}>{LETTERS[c]}</span></Html>
      ))}
      {[...Array(field.rows)].map((_, r) => (
        <Html key={`r${r}`} position={[-half - 0.45, 0, (r - (field.rows - 1) / 2) * CELL]} center zIndexRange={[5, 0]}><span className={cls}>{r + 1}</span></Html>
      ))}
      <Html position={[0, 0, -half - 1.15]} center zIndexRange={[5, 0]}><span className="pointer-events-none select-none text-[10px] font-bold tracking-[0.2em] text-leaf-400">N ↑</span></Html>
    </>
  )
}

function HoverTip() {
  const hovered = useStore((s) => s.hovered)
  const zone = useStore((s) => (s.hovered ? s.zoneById[s.hovered] : null))
  const field = useStore((s) => s.field)!
  if (!hovered || !zone) return null
  return (
    <Html position={[zx(zone, field.cols), 2.6, zz(zone, field.rows)]} center zIndexRange={[20, 10]}>
      <div className="pointer-events-none whitespace-nowrap rounded-md border border-ink-600 bg-ink-900/95 px-2 py-1 text-[11px] font-semibold text-mist-100 shadow-lg">Zone {hovered}</div>
    </Html>
  )
}

export default function FieldScene() {
  const controls = useRef<any>(null)
  const resetTick = useStore((s) => s.resetTick)
  useEffect(() => { controls.current?.reset() }, [resetTick])
  return (
    <Canvas shadows dpr={[1, 2]} camera={{ position: [11.5, 12.5, 16.5], fov: 36, near: 0.1, far: 200 }} onPointerMissed={(e) => { if (e.type === 'click') useStore.setState({ pinned: null, liveZone: null }) }}
      gl={{ antialias: true }} style={{ touchAction: 'none' }}>
      <color attach="background" args={['#070b0e']} />
      <fog attach="fog" args={['#070b0e', 26, 55]} />
      <hemisphereLight args={['#bcd7e6', '#0b1116', 0.75]} />
      <directionalLight position={[8, 14, 6]} intensity={2.1} castShadow shadow-mapSize={[2048, 2048]} shadow-camera-left={-10} shadow-camera-right={10} shadow-camera-top={10} shadow-camera-bottom={-10} shadow-bias={-0.0004} />
      <directionalLight position={[-9, 6, -8]} intensity={0.45} color="#6fb7ff" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]} receiveShadow>
        <planeGeometry args={[14.4, 14.4]} />
        <meshStandardMaterial color="#0d151a" roughness={1} />
      </mesh>
      <gridHelper args={[60, 60, '#16222a', '#101a20']} position={[0, -0.02, 0]} />
      <Zones />
      <Machine />
      <Pins />
      <AxisLabels />
      <HoverTip />
      <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.08} minDistance={7} maxDistance={34} maxPolarAngle={Math.PI / 2.15} target={[0, 0.4, 0]} />
    </Canvas>
  )
}
