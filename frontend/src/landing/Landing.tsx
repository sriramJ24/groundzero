// Farm overview: the front door to the workspace. A real aerial photograph of each demo location is laid
// flat (this farmland is flat; no elevation is invented) and viewed from a slowly orbiting oblique camera.
import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { Component, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { BASE, PRODUCT_NAME } from '../config'
import { FIELD_LIST } from '../data/api'
import type { Field } from '../data/types'

const IMAGE_SPAN_M = 1500 // each aerial image covers a 1.5 km square centred on the field
const UNIT_M = 30 // one scene unit = one 30 m zone
const SPAN = IMAGE_SPAN_M / UNIT_M
const LETTERS = 'ABCDEFGHIJKL'
const ORBIT_SECONDS = 75
const HAZE = '#c6d0cc'
const imageFor = (f: Field) => `${BASE}landing/${f.id.toLowerCase()}.jpg`
const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const hasWebGL = () => { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false } }

export interface LandingProps { initialFieldId?: string | null; onOpen: (fieldId: string, zoneId?: string | null) => void }

export default function Landing({ initialFieldId, onOpen }: LandingProps) {
  const fields = FIELD_LIST
  const [index, setIndex] = useState(() => Math.max(0, fields.findIndex((f) => f.id === initialFieldId)))
  const [zone, setZone] = useState<string | null>(null)
  const [hoverZone, setHoverZone] = useState<string | null>(null)
  const [orbiting, setOrbiting] = useState(() => !reducedMotion())
  const [fade, setFade] = useState(false)
  const [loginOpen, setLoginOpen] = useState(false)
  const [webgl] = useState(hasWebGL)
  const [sceneFailed, setSceneFailed] = useState(false)
  const compass = useRef<HTMLDivElement>(null)
  const api = useRef<{ zoom: (dir: number) => void; reset: () => void } | null>(null)
  const field = fields[index]

  const go = useCallback((delta: number) => {
    if (fields.length < 2) return
    setFade(true)
    // short crossfade; the selection, label, boundary and button all change together when the index changes
    window.setTimeout(() => { setIndex((i) => (i + delta + fields.length) % fields.length); setZone(null); setHoverZone(null); window.setTimeout(() => setFade(false), 60) }, 180)
  }, [fields.length])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (loginOpen) { if (e.key === 'Escape') setLoginOpen(false); return }
      if (t && /INPUT|TEXTAREA|SELECT/.test(t.tagName)) return
      if (e.key === 'ArrowLeft') go(-1)
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'Escape') setZone(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, loginOpen])
  useEffect(() => { try { localStorage.setItem('gz:lastField', field.id) } catch { /* storage unavailable */ } }, [field.id])

  // swipe is only recognised on the bottom band, so dragging the map never changes field
  const touch = useRef<number | null>(null)
  const swipe = {
    onTouchStart: (e: React.TouchEvent) => { touch.current = e.touches[0].clientX },
    onTouchEnd: (e: React.TouchEvent) => { if (touch.current == null) return; const dx = e.changedTouches[0].clientX - touch.current; touch.current = null; if (Math.abs(dx) > 48) go(dx < 0 ? 1 : -1) },
  }

  if (!field) return <EmptyState />
  const live3d = webgl && !sceneFailed
  const motionPaused = !orbiting || loginOpen

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden" style={{ background: HAZE }}>
      {/* poster: shown immediately and behind the canvas, so the viewport is never empty */}
      <img src={imageFor(field)} alt="" aria-hidden className={`absolute inset-0 h-full w-full scale-110 object-cover blur-sm ${live3d ? 'opacity-60' : 'landing-pan opacity-100 blur-none'}`} />
      {live3d && (
        <SceneBoundary onFail={() => setSceneFailed(true)}>
          <Canvas dpr={[1, 2]} camera={{ position: [18, 12.5, 21], fov: 38, near: 0.5, far: 400 }} gl={{ antialias: true }} className="absolute inset-0" style={{ position: 'absolute', touchAction: 'none', filter: 'saturate(1.18) contrast(1.06)' }}>
            <color attach="background" args={[HAZE]} />
            <fog attach="fog" args={[HAZE, 60, 150]} />
            <Suspense fallback={null}>
              <Ground key={field.id} field={field} selected={zone} hovered={hoverZone} onHover={setHoverZone} onPick={(z) => setZone((cur) => (cur === z ? null : z))} />
            </Suspense>
            <Rig orbiting={!motionPaused} onInteract={() => setOrbiting(false)} compass={compass} apiRef={api} fieldId={field.id} />
          </Canvas>
        </SceneBoundary>
      )}
      <div className={`pointer-events-none absolute inset-0 bg-[#c6d0cc] transition-opacity duration-200 ${fade ? 'opacity-100' : 'opacity-0'}`} />
      {/* soft scrims only where text sits */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#0d1512]/55 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[46%] bg-gradient-to-t from-[#0d1512]/80 via-[#0d1512]/35 to-transparent" />

      <header className="absolute inset-x-0 top-0 flex items-center justify-between px-5 py-4 sm:px-8" style={{ paddingTop: 'max(1rem, env(safe-area-inset-top))' }}>
        <div className="flex items-center gap-2.5 text-[#f3efe4]">
          <svg width="24" height="24" viewBox="0 0 26 26" aria-hidden><rect x="1" y="1" width="24" height="24" rx="6" fill="#16241d" stroke="#8fb39a" /><path d="M6 17l4-4 3 3 7-8" fill="none" stroke="#b9d6bf" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <span className="text-[17px] font-semibold tracking-tight">{PRODUCT_NAME}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden rounded-full border border-[#e9c46a]/50 bg-[#1b1a12]/70 px-2.5 py-1 text-[10.5px] font-semibold tracking-wider text-[#f0d68a] sm:inline">DEMO FARM · NOT SIGNED IN</span>
          <button onClick={() => setLoginOpen(true)} className="rounded-full border border-[#f3efe4]/40 bg-[#0d1512]/55 px-4 py-2 text-[13px] font-medium text-[#f3efe4] backdrop-blur-sm transition-colors hover:bg-[#0d1512]/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#b9d6bf]">Log in</button>
        </div>
      </header>

      {fields.length > 1 && (
        <>
          <ArrowButton side="left" label={`Previous field: ${fields[(index - 1 + fields.length) % fields.length].name}`} onClick={() => go(-1)} />
          <ArrowButton side="right" label={`Next field: ${fields[(index + 1) % fields.length].name}`} onClick={() => go(1)} />
        </>
      )}

      {live3d && (
        <div className="absolute right-4 top-24 flex flex-col items-center gap-1.5 sm:right-8">
          <button onClick={() => api.current?.reset()} aria-label="Reset view, north up" title="Reset view" className="grid h-10 w-10 place-items-center rounded-full bg-[#0d1512]/55 text-[#f3efe4] backdrop-blur-sm hover:bg-[#0d1512]/80">
            <div ref={compass} className="relative h-6 w-6"><span className="absolute left-1/2 top-0 -translate-x-1/2 text-[9px] font-bold leading-none text-[#e98b6a]">N</span><span className="absolute bottom-0 left-1/2 h-3 w-px -translate-x-1/2 bg-[#f3efe4]/70" /></div>
          </button>
          <button onClick={() => api.current?.zoom(-1)} aria-label="Zoom in" className="grid h-9 w-9 place-items-center rounded-full bg-[#0d1512]/55 text-lg leading-none text-[#f3efe4] backdrop-blur-sm hover:bg-[#0d1512]/80">+</button>
          <button onClick={() => api.current?.zoom(1)} aria-label="Zoom out" className="grid h-9 w-9 place-items-center rounded-full bg-[#0d1512]/55 text-lg leading-none text-[#f3efe4] backdrop-blur-sm hover:bg-[#0d1512]/80">−</button>
          <button onClick={() => setOrbiting((o) => !o)} aria-pressed={!orbiting} aria-label={orbiting ? 'Pause camera motion' : 'Resume camera motion'} title={orbiting ? 'Pause motion' : 'Resume motion'} className="mt-1 grid h-9 w-9 place-items-center rounded-full bg-[#0d1512]/55 text-[#f3efe4] backdrop-blur-sm hover:bg-[#0d1512]/80">
            {orbiting ? <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><rect x="1.5" y="1" width="3" height="10" fill="currentColor" /><rect x="7.500" y="1" width="3" height="10" fill="currentColor" /></svg> : <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 1l9 5-9 5z" fill="currentColor" /></svg>}
          </button>
        </div>
      )}

      <section {...swipe} className="absolute inset-x-0 bottom-0 flex flex-col gap-4 px-5 pb-6 sm:flex-row sm:items-end sm:justify-between sm:px-8 sm:pb-8" style={{ paddingBottom: 'max(1.5rem, env(safe-area-inset-bottom))' }}>
        <div className="max-w-xl text-[#f3efe4]">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] text-[#f3efe4]/80">
            <span className="font-medium text-[#f3efe4]">{field.farm}</span>
            {fields.length > 1 && <span className="num rounded-full bg-[#0d1512]/55 px-2 py-0.5 text-[11px]" aria-label={`Field ${index + 1} of ${fields.length}`}>{index + 1} / {fields.length}</span>}
            {fields.length > 1 && (
              <span className="flex gap-1" aria-hidden>{fields.map((f, i) => <span key={f.id} className={`h-1.5 rounded-full transition-all ${i === index ? 'w-5 bg-[#b9d6bf]' : 'w-1.5 bg-[#f3efe4]/40'}`} />)}</span>
            )}
          </div>
          <h1 className="text-[34px] font-semibold leading-[1.05] tracking-tight sm:text-[46px]">Your farm, in view.</h1>
          <p className="mt-2 text-[15px] text-[#f3efe4]/85">Select a field or zone to open your workspace</p>
          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <button onClick={() => onOpen(field.id, null)} className="rounded-full bg-[#b9d6bf] px-6 py-3 text-[14.5px] font-semibold text-[#0f1a14] shadow-lg shadow-black/25 transition-colors hover:bg-[#cfe6d3] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f3efe4]">Open {field.name.replace('Demo ', '')}</button>
            {zone && <button onClick={() => onOpen(field.id, zone)} className="rounded-full border border-[#f3efe4]/50 bg-[#0d1512]/55 px-5 py-3 text-[14px] font-medium text-[#f3efe4] backdrop-blur-sm hover:bg-[#0d1512]/80">Open zone {zone}</button>}
            <span className="text-[12.5px] text-[#f3efe4]/75">{field.name} · {field.crop} · {field.area_acres} ac{hoverZone && !zone ? ` · zone ${hoverZone}` : ''}</span>
          </div>
        </div>
        <p className="max-w-[330px] text-[10.5px] leading-snug text-[#f3efe4]/70 sm:text-right">
          Imagery: USDA NAIP via USGS The National Map, public domain. Real aerial photo of a reference location in Yolo County, CA, shown flat. Field outlines, names and all field data are demo fixtures.
          {!live3d && ' 3D view unavailable on this device: showing a still image with a slow pan, not an orbit.'}
        </p>
      </section>

      {loginOpen && (
        <div className="absolute inset-0 z-20 grid place-items-center bg-[#0d1512]/60 p-5 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="login-title" onClick={() => setLoginOpen(false)}>
          <div className="w-full max-w-sm rounded-2xl bg-[#f3efe4] p-6 text-[#16241d] shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 id="login-title" className="text-lg font-semibold">Sign-in is not connected yet</h2>
            <p className="mt-2 text-[13.5px] leading-relaxed text-[#16241d]/80">This prototype has no account system, so there is nothing to log in to and no private farm data behind it. Everything you can open here is a public demo farm with simulated field data.</p>
            <p className="mt-2 text-[12.5px] leading-relaxed text-[#16241d]/65">To add real login: an identity provider, a server-side session, and farm records scoped to each account. The landing page reads its field list from one place, ready to be swapped for the signed-in user's fields.</p>
            <div className="mt-5 flex gap-2">
              <button autoFocus onClick={() => { setLoginOpen(false); onOpen(field.id, zone) }} className="rounded-full bg-[#2f5d43] px-5 py-2.5 text-[13.5px] font-semibold text-[#f3efe4] hover:bg-[#274d38]">Continue with the demo farm</button>
              <button onClick={() => setLoginOpen(false)} className="rounded-full px-4 py-2.5 text-[13.5px] font-medium text-[#16241d]/75 hover:bg-[#16241d]/10">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ArrowButton({ side, label, onClick }: { side: 'left' | 'right'; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} aria-label={label} title={label}
      className={`absolute top-1/2 grid h-14 w-14 -translate-y-1/2 place-items-center rounded-full bg-[#0d1512]/45 text-[#f3efe4] backdrop-blur-sm transition-colors hover:bg-[#0d1512]/75 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#b9d6bf] ${side === 'left' ? 'left-3 sm:left-6' : 'right-3 sm:right-6'}`}>
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={side === 'left' ? 'M12.5 4l-6 6 6 6' : 'M7.500 4l6 6-6 6'} /></svg>
    </button>
  )
}

function EmptyState() {
  return (
    <div className="grid h-[100dvh] place-items-center bg-[#16241d] p-8 text-center text-[#f3efe4]">
      <div><h1 className="text-2xl font-semibold">No fields yet</h1><p className="mt-2 max-w-sm text-[14px] text-[#f3efe4]/75">Add a field with its boundary to see it here. In this prototype, fields come from the demo fixtures in <code>frontend/src/data/demo</code>.</p></div>
    </div>
  )
}

class SceneBoundary extends Component<{ children: ReactNode; onFail: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onFail() }
  render() { return this.state.failed ? null : this.props.children }
}

// ---------------- 3D scene ----------------
function useAerial(url: string) {
  const [tex, setTex] = useState<THREE.Texture | null>(null)
  useEffect(() => {
    let alive = true
    const t = new THREE.TextureLoader().load(url, (loaded) => { if (!alive) { loaded.dispose(); return } loaded.colorSpace = THREE.SRGBColorSpace; loaded.anisotropy = 8; setTex(loaded) })
    return () => { alive = false; t.dispose() } // cancels stale loads after rapid switching and frees the old texture
  }, [url])
  return tex
}

function labelTexture(text: string) {
  const c = document.createElement('canvas'); c.width = 640; c.height = 112
  const ctx = c.getContext('2d')!
  ctx.fillStyle = 'rgba(13,21,18,0.82)'; ctx.beginPath(); ctx.roundRect(6, 16, 628, 80, 40); ctx.fill()
  ctx.fillStyle = '#f3efe4'; ctx.font = '600 38px ui-sans-serif, system-ui, -apple-system, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  ctx.fillText(text, 320, 58)
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace
  return t
}

function Ground({ field, selected, hovered, onHover, onPick }: { field: Field; selected: string | null; hovered: string | null; onHover: (z: string | null) => void; onPick: (z: string) => void }) {
  const tex = useAerial(imageFor(field))
  const half = (field.cols * 1) / 2
  const label = useMemo(() => labelTexture(`${field.name} · ${field.area_acres} ac`), [field])
  useEffect(() => () => label.dispose(), [label])
  const zoneAt = (p: THREE.Vector3) => {
    const c = Math.floor(p.x + half), r = Math.floor(p.z + half)
    return c >= 0 && c < field.cols && r >= 0 && r < field.rows ? `${LETTERS[c]}${r + 1}` : null
  }
  const zonePos = (id: string | null): [number, number, number] | null => {
    if (!id) return null
    const c = LETTERS.indexOf(id[0]), r = Number(id.slice(1)) - 1
    return [c - half + 0.5, 0.04, r - half + 0.5]
  }
  const hi = zonePos(selected) ?? zonePos(hovered)
  return (
    <group>
      {/* muted ground beyond the photo so the horizon fades into haze instead of ending in an edge */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]}><planeGeometry args={[600, 600]} /><meshBasicMaterial color="#a39b84" /></mesh>
      {tex && <mesh rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[SPAN, SPAN]} /><meshBasicMaterial map={tex} toneMapped={false} /></mesh>}
      {/* selected parcel: subtle sage tint, thin boundary */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}
        onPointerMove={(e: ThreeEvent<PointerEvent>) => onHover(zoneAt(e.point))} onPointerOut={() => onHover(null)}
        onClick={(e: ThreeEvent<MouseEvent>) => { if (e.delta > 5) return; const z = zoneAt(e.point); if (z) onPick(z) }}>
        <planeGeometry args={[field.cols, field.rows]} />
        <meshBasicMaterial color="#9fcfa9" transparent opacity={0.3} depthWrite={false} />
      </mesh>
      {/* boundary drawn as thin strips so it keeps a visible width at any zoom */}
      {[[0, -half, field.cols + 0.12, 0.12], [0, half, field.cols + 0.12, 0.12], [-half, 0, 0.12, field.rows + 0.12], [half, 0, 0.12, field.rows + 0.12]].map(([x, z, w, h], i) => (
        <mesh key={i} rotation={[-Math.PI / 2, 0, 0]} position={[x, 0.035, z]} raycast={() => null}><planeGeometry args={[w, h]} /><meshBasicMaterial color="#f3efe4" transparent opacity={0.92} /></mesh>
      ))}
      {hi && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={hi} raycast={() => null}>
          <planeGeometry args={[0.96, 0.96]} /><meshBasicMaterial color={selected ? '#f3efe4' : '#dfeee2'} transparent opacity={selected ? 0.55 : 0.32} depthWrite={false} />
        </mesh>
      )}
      <sprite position={[0, 3.2, -half - 0.5]} scale={[9, 1.575, 1]} raycast={() => null}><spriteMaterial map={label} transparent depthTest={false} /></sprite>
    </group>
  )
}

function Rig({ orbiting, onInteract, compass, apiRef, fieldId }: { orbiting: boolean; onInteract: () => void; compass: React.RefObject<HTMLDivElement | null>; apiRef: React.MutableRefObject<{ zoom: (d: number) => void; reset: () => void } | null>; fieldId: string }) {
  const controls = useRef<any>(null)
  const { camera } = useThree()
  useEffect(() => {
    apiRef.current = {
      zoom: (dir) => { const c = controls.current; if (!c) return; const v = camera.position.clone().sub(c.target); const d = THREE.MathUtils.clamp(v.length() * (dir > 0 ? 1.2 : 1 / 1.2), 12, 70); camera.position.copy(c.target).add(v.setLength(d)); c.update() },
      reset: () => { camera.position.set(0, 17, 27); controls.current?.update() },
    }
  }, [camera, apiRef])
  // each field starts from the same comfortable pose
  useEffect(() => { camera.position.set(18, 12.5, 21); controls.current?.update() }, [fieldId, camera])
  useFrame(() => { const c = controls.current; if (c && compass.current) compass.current.style.transform = `rotate(${c.getAzimuthalAngle()}rad)` })
  return (
    <OrbitControls ref={controls} makeDefault target={[0, 0, 0]} enablePan={false} enableDamping dampingFactor={0.08}
      autoRotate={orbiting} autoRotateSpeed={60 / ORBIT_SECONDS} minDistance={12} maxDistance={70} minPolarAngle={0.35} maxPolarAngle={1.25}
      onStart={onInteract} />
  )
}
