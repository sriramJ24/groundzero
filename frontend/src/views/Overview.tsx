import { Component, lazy, Suspense, useMemo, type ReactNode } from 'react'
import { useStore } from '../store'
import { LAYERS, layerValue, rampColor, rampCss } from '../data/scoring'
import ZonePanel from '../panels/ZonePanel'

const FieldScene = lazy(() => import('../scene/FieldScene'))

export default function Overview() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <KpiBar />
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1">
          <SceneBoundary>
            <Suspense fallback={<div className="grid h-full place-items-center text-mist-400">Loading field…</div>}>
              <FieldScene />
            </Suspense>
          </SceneBoundary>
          <LayerBar />
          <Legend />
          <ReplayBar />
        </div>
        <aside className="w-[372px] shrink-0 border-l border-ink-700 bg-ink-900"><ZonePanel /></aside>
      </div>
    </div>
  )
}

function KpiBar() {
  const zones = useStore((s) => s.zones)
  const risks = useStore((s) => s.risks)
  const captures = useStore((s) => s.captures)
  const actions = useStore((s) => s.actions)
  const done = useStore((s) => s.doneActions)
  const field = useStore((s) => s.field)!
  const machine = useStore((s) => s.machine)!
  const scannedSteps = useStore((s) => Math.min(machine.path.length, Math.floor(s.replayT / machine.step_s) + 1))
  const set = useStore((s) => s.set)
  const k = useMemo(() => {
    const health = Math.round(zones.reduce((a, z) => a + z.health.score, 0) / zones.length)
    const atRisk = zones.filter((z) => z.health.score < 50 || 0.6 * risks[z.id].drought + 0.4 * risks[z.id].heat >= 65).length
    const waterM3 = zones.reduce((a, z) => a + z.water.applied_mm_7d * 0.9, 0)
    const covered = zones.filter((z) => z.spray.coverage_pct > 0).length
    return { health, atRisk, waterM3, covered }
  }, [zones, risks])
  const acresPerZone = field.area_acres / zones.length
  const urgent = actions.filter((a) => a.priority === 1 && !done[a.id]).length
  const items: { label: string; value: ReactNode; sub: string; tone?: string; onClick?: () => void }[] = [
    { label: 'Field health', value: k.health, sub: '/100 indicative', tone: k.health >= 70 ? 'text-leaf-400' : 'text-amber-warn', onClick: () => set({ layer: 'health' }) },
    { label: 'Scanned this pass', value: (scannedSteps * acresPerZone).toFixed(1), sub: `of ${field.area_acres} ac` },
    { label: 'At-risk zones', value: k.atRisk, sub: `of ${zones.length}`, tone: k.atRisk ? 'text-amber-warn' : '', onClick: () => set({ layer: 'drought' }) },
    { label: 'Water applied, 7 d', value: Math.round(k.waterM3).toLocaleString(), sub: 'm³ logged', tone: 'text-sky-water', onClick: () => set({ layer: 'water' }) },
    { label: 'Application coverage', value: `${Math.round((k.covered / zones.length) * 100)}%`, sub: `${k.covered} zones`, tone: 'text-violet-spray', onClick: () => set({ layer: 'spray' }) },
    { label: 'Images', value: captures.length, sub: `${captures.filter((c) => c.review.status === 'unreviewed').length} unreviewed`, onClick: () => set({ view: 'vision' }) },
    { label: 'Urgent actions', value: urgent, sub: 'priority 1', tone: urgent ? 'text-red-alert' : '', onClick: () => set({ view: 'actions' }) },
  ]
  return (
    <div className="grid shrink-0 grid-cols-7 divide-x divide-ink-700 border-b border-ink-700 bg-ink-900">
      {items.map((i) => (
        <button key={i.label} onClick={i.onClick} disabled={!i.onClick} className="px-4 py-2.5 text-left transition-colors enabled:hover:bg-ink-800">
          <div className="label truncate">{i.label}</div>
          <div className="mt-0.5 flex items-baseline gap-1.5"><span className={`num text-[22px] font-semibold leading-none ${i.tone ?? ''}`}>{i.value}</span><span className="truncate text-[11px] text-mist-400">{i.sub}</span></div>
        </button>
      ))}
    </div>
  )
}

function LayerBar() {
  const layer = useStore((s) => s.layer)
  const extrude = useStore((s) => s.extrude)
  const ndvi = useStore((s) => s.ndvi)
  const set = useStore((s) => s.set)
  const scenario = useStore((s) => s.scenario)
  const weatherHeat = useStore((s) => s.weatherHeat)
  const setScenario = useStore((s) => s.setScenario)
  return (
    <div className="pointer-events-none absolute left-3 right-3 top-3 flex flex-wrap items-start justify-between gap-2">
      <div className="pointer-events-auto flex flex-wrap gap-1 rounded-lg border border-ink-700 bg-ink-900/90 p-1 backdrop-blur">
        {LAYERS.filter((l) => l.id !== 'ndvi' || ndvi).map((l) => (
          <button key={l.id} onClick={() => set({ layer: l.id })} className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium transition-colors ${layer === l.id ? 'bg-ink-700 text-mist-100' : 'text-mist-400 hover:text-mist-100'}`}>
            <span className="h-2 w-2 rounded-sm" style={{ background: l.ramp[3] }} />{l.name}
          </button>
        ))}
      </div>
      <div className="pointer-events-auto flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-900/90 p-1 backdrop-blur">
        {weatherHeat && (
          <>
            <span className="label px-1.5">Weather</span>
            <button onClick={() => setScenario('now')} className={`rounded-md px-2.5 py-1.5 text-[12px] font-medium ${scenario === 'now' ? 'bg-ink-700 text-mist-100' : 'text-mist-400 hover:text-mist-100'}`}>This week</button>
            <button onClick={() => setScenario('heat')} title="Replays the real hottest week of summer 2026 at this location" className={`rounded-md px-2.5 py-1.5 text-[12px] font-medium ${scenario === 'heat' ? 'bg-amber-warn/20 text-amber-warn' : 'text-mist-400 hover:text-mist-100'}`}>Aug 2026 heatwave</button>
            <span className="mx-1 h-5 w-px bg-ink-700" />
          </>
        )}
        <button onClick={() => set({ extrude: !extrude })} className={`rounded-md px-2.5 py-1.5 text-[12px] font-medium ${extrude ? 'bg-ink-700 text-mist-100' : 'text-mist-400'}`}>Height = value</button>
        <button onClick={() => useStore.setState((s) => ({ resetTick: s.resetTick + 1 }))} className="rounded-md px-2.5 py-1.5 text-[12px] font-medium text-mist-400 hover:text-mist-100">Reset view</button>
      </div>
    </div>
  )
}

function Legend() {
  const layer = useStore((s) => s.layer)
  const ndvi = useStore((s) => s.ndvi)
  const weather = useStore((s) => s.weather)
  const scenario = useStore((s) => s.scenario)
  const def = LAYERS.find((l) => l.id === layer)!
  const real = layer === 'ndvi'
  const usesWx = layer === 'drought' || layer === 'forecast'
  return (
    <div className="pointer-events-none absolute bottom-[68px] left-3 w-[300px] rounded-lg border border-ink-700 bg-ink-900/90 p-3 backdrop-blur">
      <div className="flex items-center justify-between"><span className="text-[12.5px] font-semibold">{def.name}</span><span className="num text-[11px] text-mist-400">{def.unit}</span></div>
      <div className="mt-2 h-2 rounded" style={{ background: rampCss(def.ramp) }} />
      <div className="mt-1 flex justify-between text-[10.5px] text-mist-400"><span>{def.lowLabel}</span><span>{def.highLabel}</span></div>
      <div className="mt-2 text-[11px] leading-snug text-mist-400">
        {def.source}
        {real && ndvi && <> Scene {ndvi.latest.date}, mean {ndvi.latest.mean.toFixed(2)}. Not linked to the simulated zone data.</>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {real ? <span className="chip chip-pub">SENTINEL-2 · REAL</span> : <span className="chip chip-sim">SIMULATED ZONE DATA</span>}
        {usesWx && <span className={`chip ${weather.provenance === 'simulated' ? 'chip-sim' : 'chip-pub'}`}>{weather.provenance === 'simulated' ? 'SAMPLE FORECAST' : scenario === 'heat' ? 'REAL ARCHIVE · AUG 1–7 2026 REPLAY' : 'OPEN-METEO FORECAST · THIS WEEK'}</span>}
      </div>
    </div>
  )
}

function ReplayBar() {
  const machine = useStore((s) => s.machine)!
  const t = useStore((s) => s.replayT)
  const playing = useStore((s) => s.playing)
  const liveZone = useStore((s) => s.liveZone)
  const set = useStore((s) => s.set)
  const step = Math.min(machine.path.length - 1, Math.floor(t / machine.step_s))
  return (
    <div className="absolute bottom-3 left-3 right-3 flex items-center gap-3 rounded-lg border border-ink-700 bg-ink-900/90 px-3 py-2 backdrop-blur">
      <button className="btn w-[74px]" onClick={() => set({ playing: !playing, liveZone: null })}>{playing && !liveZone ? 'Pause' : 'Play'}</button>
      <div className="min-w-0 flex-1">
        <input type="range" min={0} max={machine.duration_s - 0.01} step={0.5} value={t} onChange={(e) => set({ replayT: Number(e.target.value), playing: false, liveZone: null })} className="w-full" aria-label="Replay position" />
      </div>
      <div className="w-[230px] shrink-0 text-right text-[11.5px] leading-tight">
        {liveZone
          ? <><span className="font-semibold text-leaf-400">Live update</span> <span className="text-mist-400">· machine at</span> <span className="num">{liveZone}</span></>
          : <><span className="text-mist-400">{machine.type.replace(' (simulated)', '')} at</span> <span className="num font-semibold">{machine.path[step].zone_id}</span> <span className="text-mist-400">· pass {Math.round((t / machine.duration_s) * 100)}%</span></>}
        <div className="text-[10px] text-amber-warn">Replay of a simulated machine path</div>
      </div>
    </div>
  )
}

// If WebGL is unavailable the same data is shown as a flat grid with identical hover/click behaviour.
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: !hasWebGL() }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <FlatField /> : this.props.children }
}
function hasWebGL() { try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')) } catch { return false } }

function FlatField() {
  const zones = useStore((s) => s.zones)
  const risks = useStore((s) => s.risks)
  const layer = useStore((s) => s.layer)
  const ndvi = useStore((s) => s.ndvi)
  const pinned = useStore((s) => s.pinned)
  const def = LAYERS.find((l) => l.id === layer)!
  const maxWater = Math.max(1, ...zones.map((z) => z.water.applied_mm_7d))
  return (
    <div className="grid h-full place-items-center p-16">
      <div className="grid aspect-square h-full max-h-[620px] grid-cols-12 gap-[3px]" onMouseLeave={() => useStore.getState().setHovered(null)}>
        {zones.map((z) => {
          const lv = layerValue(layer, z, risks[z.id], ndvi, maxWater)
          const [r, g, b] = rampColor(def.ramp, lv.v)
          return <button key={z.id} title={z.id} onMouseEnter={() => useStore.getState().setHovered(z.id)} onClick={() => useStore.getState().togglePin(z.id)}
            className={`rounded-[3px] ${pinned === z.id ? 'ring-2 ring-leaf-400' : 'hover:ring-2 hover:ring-white'}`} style={{ background: `rgb(${r * 255},${g * 255},${b * 255})` }} />
        })}
      </div>
      <div className="absolute right-3 top-14 text-[11px] text-mist-400">3D view unavailable on this device; showing the flat map.</div>
    </div>
  )
}
