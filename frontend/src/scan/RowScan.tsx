// Row Scan: a coarse 3D view of a real corn row, built only from photographs.
// Geometry = two-view stereo on real side-camera photos, fused into voxels (pipelines/crop_view).
// Colors are the median photo color of each voxel. Scale is arbitrary. Crop condition is not assessed.
import { Canvas, useThree, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls } from '@react-three/drei'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { BASE } from '../config'

type Voxel = [number, number, number, number, number, number, number, string | null] // x y z support r g b section
interface Photo { name: string; src: string; frame: number; time: string; sha256: string; aligned: boolean; position: number[] | null }
interface Section { id: string; label: string; x0: number; x1: number; photos: string[]; reconstructed: boolean; voxels: number; start: string; end: string }
interface Scan {
  title: string
  source: { dataset: string; authors: string; license: string; url: string; run: string; camera: string; changes: string }
  method: { method: string; pairs_tried: number; voxels_kept: number; min_pairs_per_voxel: number; runtime_s: number }
  voxel_size: number; ground_y: number; photos: Photo[]; sections: Section[]; voxels: Voxel[]
}
type ColorMode = 'photo' | 'support'

const fmtTime = (iso: string) => { const d = new Date(iso); return `${d.toISOString().slice(11, 21)} UTC` }
const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

export default function RowScan() {
  const [scan, setScan] = useState<Scan | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [mode, setMode] = useState<ColorMode>('photo')
  const [photo, setPhoto] = useState<Photo | null>(null)
  const [flags, setFlags] = useState<Record<string, boolean>>({})

  useEffect(() => {
    fetch(`${BASE}scan/scan.json`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))).then(setScan).catch((e) => setErr(String(e)))
  }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { if (photo) setPhoto(null); else setSelected(null) } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [photo])

  if (err) return <div className="grid h-full place-items-center text-mist-400">Could not load the row scan ({err}).</div>
  if (!scan) return <div className="grid h-full place-items-center text-mist-400">Loading row scan…</div>

  const focus = selected ?? hovered
  const sec = scan.sections.find((s) => s.id === selected) ?? null
  const first = scan.photos[0], last = scan.photos[scan.photos.length - 1]
  const seconds = (new Date(last.time).getTime() - new Date(first.time).getTime()) / 1000

  return (
    <div className="flex h-full min-w-[1100px] flex-col bg-ink-950">
      <header className="flex shrink-0 items-center gap-4 border-b border-ink-700 bg-ink-900 px-4 py-2.5">
        <button className="btn" onClick={() => { window.location.hash = '#/' }} aria-label="Back to farm overview">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12.5 4l-6 6 6 6" /></svg>
          Farm overview
        </button>
        <div className="leading-tight">
          <div className="text-[14px] font-semibold">{scan.title}</div>
          <div className="text-[11px] text-mist-400">{fmtDate(first.time)} · {scan.photos.length} photos over {seconds.toFixed(1)} s · one side camera</div>
        </div>
        <div className="flex-1" />
        <span className="chip chip-real">REAL PHOTOS</span>
        <span className="chip chip-pub">APPROXIMATE 3D · SCALE NOT MEASURED</span>
        <span className="chip">CONDITION NOT ASSESSED</span>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <Canvas camera={{ fov: 38, near: 0.5, far: 2000 }} dpr={[1, 2]} gl={{ antialias: true }}>
            <Scene scan={scan} focus={focus} selected={selected} mode={mode} onHover={setHovered} onSelect={(id) => setSelected((s) => (s === id ? null : id))} />
          </Canvas>
          <div className="pointer-events-none absolute left-4 top-4 flex flex-col gap-2">
            <div className="panel pointer-events-auto flex items-center gap-1 p-1" role="radiogroup" aria-label="Color the crop by">
              {([['photo', 'Photo color'], ['support', 'Evidence strength']] as [ColorMode, string][]).map(([id, name]) => (
                <button key={id} role="radio" aria-checked={mode === id} onClick={() => setMode(id)}
                  className={`rounded-md px-2.5 py-1 text-[12px] ${mode === id ? 'bg-ink-600 text-mist-100' : 'text-mist-300 hover:text-mist-100'}`}>{name}</button>
              ))}
            </div>
            {mode === 'support' && (
              <div className="panel pointer-events-auto w-[220px] p-2.5 text-[11px] text-mist-300">
                <div className="mb-1.5 h-2 rounded-full" style={{ background: 'linear-gradient(90deg,#5d7a8a,#2f8f5b,#9be8bb)' }} />
                <div className="flex justify-between"><span>3 photo pairs</span><span>20+</span></div>
                <p className="mt-1.5 leading-snug text-mist-400">How many independent photo pairs placed crop at that spot. Fewer pairs means a less certain shape.</p>
              </div>
            )}
          </div>
          <div className="pointer-events-none absolute right-4 top-4 max-w-[380px] text-right text-[11px] leading-snug text-mist-400">
            Drag to rotate, scroll to zoom. Click a section to see its photos. Blocks are a coarse shape estimated from the photos, not individual plants. Empty space was not seen, not empty field.
          </div>
        </div>

        <aside className="flex w-[380px] shrink-0 flex-col overflow-y-auto border-l border-ink-700 bg-ink-900">
          {sec ? (
            <SectionPanel scan={scan} sec={sec} flagged={!!flags[sec.id]} onFlag={() => setFlags((f) => ({ ...f, [sec.id]: !f[sec.id] }))} onClose={() => setSelected(null)} onPhoto={setPhoto} />
          ) : (
            <Overview scan={scan} hovered={hovered} flags={flags} onHover={setHovered} onSelect={setSelected} />
          )}
        </aside>
      </div>

      {photo && <PhotoModal photo={photo} scan={scan} onClose={() => setPhoto(null)} onStep={(d) => { const i = scan.photos.indexOf(photo); const n = scan.photos[i + d]; if (n) setPhoto(n) }} />}
    </div>
  )
}

function Overview({ scan, hovered, flags, onHover, onSelect }: { scan: Scan; hovered: string | null; flags: Record<string, boolean>; onHover: (id: string | null) => void; onSelect: (id: string) => void }) {
  const aligned = scan.photos.filter((p) => p.aligned).length
  return (
    <div className="p-4">
      <div className="label">Sections along the row</div>
      <ul className="mt-2 space-y-1.5">
        {scan.sections.map((s) => (
          <li key={s.id}>
            <button onMouseEnter={() => onHover(s.id)} onMouseLeave={() => onHover(null)} onFocus={() => onHover(s.id)} onBlur={() => onHover(null)} onClick={() => onSelect(s.id)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${hovered === s.id ? 'border-ink-500 bg-ink-800' : 'border-ink-700 bg-ink-850 hover:border-ink-600'}`}>
              <Thumb scan={scan} name={s.photos[Math.floor(s.photos.length / 2)]} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-[13px] font-medium">{s.label}{flags[s.id] && <span className="chip chip-sim">FLAGGED</span>}</div>
                <div className="text-[11.5px] text-mist-400">{s.photos.length} photos · {s.reconstructed ? 'shape estimated' : 'photos only, no 3D shape'}</div>
                <div className="text-[11.5px] text-mist-400">Condition: not assessed</div>
              </div>
            </button>
          </li>
        ))}
      </ul>

      <div className="mt-5 label">What you are looking at</div>
      <div className="mt-2 space-y-2 text-[12.5px] leading-relaxed text-mist-300">
        <p>A short stretch of a real corn row near harvest, filmed by a camera about 28 cm off the ground looking sideways. The 3D shape comes only from these photos: {aligned} of {scan.photos.length} could be placed in 3D, and pairs of them were compared to estimate where crop is.</p>
        <p>Section 5 was photographed but the photos could not be placed in 3D (a leaf right in front of the lens broke the sequence). It shows as an outline placed just past Section 4 (its exact position is assumed), with its photos still available.</p>
        <p>No crop-condition check has been built or tested yet, so every section says "not assessed" rather than showing a made-up score.</p>
      </div>

      <details className="mt-5 text-[11.5px] leading-snug text-mist-400">
        <summary className="cursor-pointer label">Method and source</summary>
        <p className="mt-2">Method: {scan.method.method}. {scan.method.pairs_tried} photo pairs; a block is kept only where at least {scan.method.min_pairs_per_voxel} pairs agree. CPU only, {scan.method.runtime_s} s. No GPS, motion sensor or measured distances, so sizes are relative.</p>
        <p className="mt-2">Photos: <a className="underline hover:text-mist-200" href={scan.source.url} target="_blank" rel="noreferrer">{scan.source.dataset}</a>, {scan.source.authors}, {scan.source.license}. Run {scan.source.run}, {scan.source.camera}. {scan.source.changes} This is public research footage, not a GroundZero device.</p>
      </details>
    </div>
  )
}

function SectionPanel({ scan, sec, flagged, onFlag, onClose, onPhoto }: { scan: Scan; sec: Section; flagged: boolean; onFlag: () => void; onClose: () => void; onPhoto: (p: Photo) => void }) {
  const photos = sec.photos.map((n) => scan.photos.find((p) => p.name === n)!)
  const secs = (new Date(sec.end).getTime() - new Date(sec.start).getTime()) / 1000
  return (
    <div className="slide-in p-4">
      <div className="flex items-center gap-2">
        <button className="btn px-2 py-1" onClick={onClose} aria-label="Back to all sections">
          <svg width="13" height="13" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12.5 4l-6 6 6 6" /></svg>
        </button>
        <h2 className="text-[17px] font-semibold">{sec.label}</h2>
        {flagged && <span className="chip chip-sim">FLAGGED FOR INSPECTION</span>}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-[12.5px]">
        <Item k="Photographed" v={`${fmtTime(sec.start)} – ${fmtTime(sec.end)}`} sub={`${fmtDate(sec.start)} · ${secs.toFixed(1)} s`} />
        <Item k="Photos" v={`${photos.length}`} sub={`${photos.filter((p) => p.aligned).length} placed in 3D`} />
        <Item k="3D shape" v={sec.reconstructed ? `${sec.voxels.toLocaleString()} blocks` : 'Not estimated'} sub={sec.reconstructed ? 'coarse, relative scale' : 'photos could not be aligned'} />
        <Item k="Crop condition" v="Not assessed" sub="no tested method yet" />
      </dl>

      <div className="mt-4 rounded-lg border border-ink-700 bg-ink-850 p-3 text-[12px] leading-snug text-mist-300">
        <div className="label mb-1">Suggested next step</div>
        Look through the photos below. If something looks wrong, flag this section so someone checks it in person.
        <button className={`btn mt-2.5 w-full ${flagged ? '' : 'btn-primary'}`} onClick={onFlag}>{flagged ? 'Remove flag' : 'Flag for in-person check'}</button>
        <p className="mt-1.5 text-[10.5px] text-mist-400">Flags are kept in this browser tab only for the demo. Nothing is sent to a machine or a person.</p>
      </div>

      <div className="mt-4 label">Original photos</div>
      <div className="mt-2 grid grid-cols-3 gap-1.5">
        {photos.map((p) => (
          <button key={p.name} onClick={() => onPhoto(p)} className="group relative overflow-hidden rounded-md border border-ink-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-leaf-500" aria-label={`Open photo, frame ${p.frame}`}>
            <img src={`${BASE}scan/${p.src}`} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover transition-transform group-hover:scale-105" />
            <span className="num absolute bottom-0.5 left-1 rounded bg-black/60 px-1 text-[9.5px] text-mist-200">{p.frame}</span>
            {!p.aligned && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full border border-mist-300" title="Not placed in 3D" />}
          </button>
        ))}
      </div>
    </div>
  )
}

function Item({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div>
      <dt className="label">{k}</dt>
      <dd className="mt-0.5 text-mist-100">{v}</dd>
      {sub && <dd className="text-[11px] text-mist-400">{sub}</dd>}
    </div>
  )
}

function Thumb({ scan, name }: { scan: Scan; name: string }) {
  const p = scan.photos.find((x) => x.name === name)
  if (!p) return null
  return <img src={`${BASE}scan/${p.src}`} alt="" className="h-12 w-16 shrink-0 rounded-md object-cover" />
}

function PhotoModal({ photo, scan, onClose, onStep }: { photo: Photo; scan: Scan; onClose: () => void; onStep: (d: number) => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'ArrowRight') onStep(1); if (e.key === 'ArrowLeft') onStep(-1) }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onStep])
  const sec = scan.sections.find((s) => s.photos.includes(photo.name))
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-6" onClick={onClose} role="dialog" aria-modal aria-label={`Photo frame ${photo.frame}`}>
      <div className="panel max-w-[900px] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <img src={`${BASE}scan/${photo.src}`} alt={`Corn row, frame ${photo.frame}`} className="block max-h-[70vh] w-full object-contain bg-black" />
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 p-3 text-[12px] text-mist-300">
          <span className="font-medium text-mist-100">{sec?.label} · frame <span className="num">{photo.frame}</span></span>
          <span>{fmtDate(photo.time)} {fmtTime(photo.time)}</span>
          <span>{photo.aligned ? 'Placed in 3D' : 'Not placed in 3D'}</span>
          <span className="num text-mist-400" title={photo.sha256}>sha256 {photo.sha256.slice(0, 12)}…</span>
          <span className="flex-1" />
          <button className="btn px-2 py-1" onClick={() => onStep(-1)} aria-label="Previous photo">‹</button>
          <button className="btn px-2 py-1" onClick={() => onStep(1)} aria-label="Next photo">›</button>
          <button className="btn px-2.5 py-1" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

// ---------- 3D ----------

const SUPPORT_RAMP = [new THREE.Color('#5d7a8a'), new THREE.Color('#2f8f5b'), new THREE.Color('#9be8bb')]
function supportColor(n: number, out: THREE.Color) {
  const t = Math.min(1, Math.max(0, (n - 3) / 17))
  const [a, b] = t < 0.5 ? [SUPPORT_RAMP[0], SUPPORT_RAMP[1]] : [SUPPORT_RAMP[1], SUPPORT_RAMP[2]]
  return out.copy(a).lerp(b, t < 0.5 ? t * 2 : (t - 0.5) * 2)
}

function Scene({ scan, focus, selected, mode, onHover, onSelect }: { scan: Scan; focus: string | null; selected: string | null; mode: ColorMode; onHover: (id: string | null) => void; onSelect: (id: string) => void }) {
  const { voxels, voxel_size: vs, ground_y: gy, sections } = scan
  const bounds = useMemo(() => {
    const b = new THREE.Box3()
    for (const v of voxels) b.expandByPoint(new THREE.Vector3(v[0], v[1], v[2]))
    return b
  }, [voxels])
  const zMax = bounds.max.z
  const xMid = (sections[0].x0 + sections[sections.length - 1].x1) / 2
  const span = sections[sections.length - 1].x1 - sections[0].x0

  return (
    <>
      <color attach="background" args={['#070b0e']} />
      <fog attach="fog" args={['#070b0e', span * 4, span * 9]} />
      <hemisphereLight args={['#dfe9e2', '#2a2118', 0.9]} />
      <directionalLight position={[-20, 60, -30]} intensity={1.4} />
      <OrbitControls target={[xMid, gy + 6, zMax * 0.45]} enableDamping maxPolarAngle={Math.PI * 0.49} minDistance={8} maxDistance={span * 6} makeDefault />
      <CameraStart pos={[xMid + span * 0.45, gy + span * 1.7, -span * 3.1]} target={[xMid, gy + 6, zMax * 0.45]} />

      {/* ground (estimated level, not measured) */}
      <mesh rotation-x={-Math.PI / 2} position={[xMid, gy - vs / 2, zMax / 2]}>
        <planeGeometry args={[span * 3, zMax * 1.6]} />
        <meshStandardMaterial color="#1a1510" roughness={1} />
      </mesh>

      {/* drei 10.7 + React 19: the first <Html> in a scene can mount empty, so mount a blank one first */}
      <Html position={[xMid, gy, 0]}><span /></Html>
      {sections.map((s) => (
        <SectionBand key={s.id} s={s} gy={gy} zMax={zMax} active={focus === s.id} selected={selected === s.id} onHover={onHover} onSelect={onSelect} />
      ))}

      <Voxels voxels={voxels} vs={vs} focus={focus} mode={mode} />
      <CameraPath photos={scan.photos} />
    </>
  )
}

function CameraStart({ pos, target }: { pos: [number, number, number]; target: [number, number, number] }) {
  const camera = useThree((st) => st.camera)
  useLayoutEffect(() => { camera.position.set(...pos); camera.lookAt(...target) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

function SectionBand({ s, gy, zMax, active, selected, onHover, onSelect }: { s: Section; gy: number; zMax: number; active: boolean; selected: boolean; onHover: (id: string | null) => void; onSelect: (id: string) => void }) {
  const w = s.x1 - s.x0
  const cx = (s.x0 + s.x1) / 2
  const depth = zMax * 1.05
  const color = !s.reconstructed ? '#7f95a1' : selected ? '#63d394' : active ? '#9be8bb' : '#2f8f5b'
  const over = (e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onHover(s.id); document.body.style.cursor = 'pointer' }
  const out = () => { onHover(null); document.body.style.cursor = '' }
  const edges = useMemo(() => {
    const g = new THREE.BufferGeometry()
    const y = gy + 0.02, h = 18
    const pts = s.reconstructed
      ? [[s.x0, y, 0], [s.x1, y, 0], [s.x1, y, 0], [s.x1, y, depth], [s.x1, y, depth], [s.x0, y, depth], [s.x0, y, depth], [s.x0, y, 0]]
      : [[s.x0, y, 0], [s.x1, y, 0], [s.x1, y, 0], [s.x1, y, depth], [s.x1, y, depth], [s.x0, y, depth], [s.x0, y, depth], [s.x0, y, 0],
         [s.x0, y + h, 0], [s.x1, y + h, 0], [s.x1, y + h, 0], [s.x1, y + h, depth], [s.x1, y + h, depth], [s.x0, y + h, depth], [s.x0, y + h, depth], [s.x0, y + h, 0],
         [s.x0, y, 0], [s.x0, y + h, 0], [s.x1, y, 0], [s.x1, y + h, 0], [s.x1, y, depth], [s.x1, y + h, depth], [s.x0, y, depth], [s.x0, y + h, depth]]
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts.flat(), 3))
    return g
  }, [s, gy, depth])
  return (
    <group>
      <mesh rotation-x={-Math.PI / 2} position={[cx, gy + 0.01, depth / 2]} onPointerOver={over} onPointerOut={out} onClick={(e) => { e.stopPropagation(); onSelect(s.id) }}>
        <planeGeometry args={[w * 0.98, depth]} />
        <meshBasicMaterial color={color} transparent opacity={selected ? 0.32 : active ? 0.24 : 0.1} depthWrite={false} />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={color} transparent opacity={s.reconstructed ? 0.6 : 0.45} />
      </lineSegments>
      <Html position={[cx, gy + 0.5, -2.5]} center zIndexRange={[10, 0]}>
        <button onClick={() => onSelect(s.id)} onMouseEnter={() => onHover(s.id)} onMouseLeave={() => onHover(null)}
          className={`whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11.5px] font-semibold backdrop-blur-sm ${selected ? 'border-leaf-400 bg-leaf-600 text-[#04140b]' : active ? 'border-leaf-400 bg-ink-800/90 text-mist-100' : 'border-ink-500 bg-ink-900/80 text-mist-200'}`}>
          {s.label.replace('Section ', '')}{!s.reconstructed && ' · photos only'}
        </button>
      </Html>
    </group>
  )
}

function Voxels({ voxels, vs, focus, mode }: { voxels: Voxel[]; vs: number; focus: string | null; mode: ColorMode }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const geom = useMemo(() => new THREE.BoxGeometry(vs * 0.94, vs * 0.94, vs * 0.94), [vs])
  useLayoutEffect(() => {
    const m = new THREE.Matrix4()
    voxels.forEach((v, i) => { m.makeTranslation(v[0], v[1], v[2]); ref.current.setMatrixAt(i, m) })
    ref.current.instanceMatrix.needsUpdate = true
    ref.current.computeBoundingSphere()
  }, [voxels])
  useLayoutEffect(() => {
    const c = new THREE.Color()
    const dim = new THREE.Color('#0b1116')
    voxels.forEach((v, i) => {
      if (mode === 'support') supportColor(v[3], c)
      else c.setRGB(v[4] / 255, v[5] / 255, v[6] / 255, THREE.SRGBColorSpace).multiplyScalar(1.25)
      if (focus && v[7] !== focus) c.lerp(dim, 0.72)
      ref.current.setColorAt(i, c)
    })
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true
  }, [voxels, mode, focus])
  return (
    <instancedMesh ref={ref} args={[geom, undefined, voxels.length]} raycast={() => null}>
      <meshStandardMaterial roughness={0.95} metalness={0} />
    </instancedMesh>
  )
}

function CameraPath({ photos }: { photos: Photo[] }) {
  const pts = photos.filter((p) => p.position).map((p) => new THREE.Vector3(...(p.position as [number, number, number])))
  const geom = useMemo(() => new THREE.BufferGeometry().setFromPoints(pts), [photos]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <group>
      <line>
        <primitive object={geom} attach="geometry" />
        <lineBasicMaterial color="#f0a93b" />
      </line>
      {pts.map((p, i) => (
        <mesh key={i} position={p}><sphereGeometry args={[0.18, 8, 8]} /><meshBasicMaterial color="#f0a93b" /></mesh>
      ))}
      <Html position={[pts[0].x, pts[0].y - 1.4, pts[0].z]} center zIndexRange={[10, 0]}>
        <span className="whitespace-nowrap rounded bg-ink-900/80 px-1.5 py-0.5 text-[10.5px] text-amber-warn">camera start (about 28 cm above ground)</span>
      </Html>
      <Html position={[pts[pts.length - 1].x, pts[pts.length - 1].y - 1.4, pts[pts.length - 1].z]} center zIndexRange={[10, 0]}>
        <span className="whitespace-nowrap rounded bg-ink-900/80 px-1.5 py-0.5 text-[10.5px] text-amber-warn">last placed photo</span>
      </Html>
    </group>
  )
}
