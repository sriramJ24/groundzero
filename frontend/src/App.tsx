import { useEffect, useState } from 'react'
import { PRODUCT_NAME, PRODUCT_TAGLINE } from './config'
import { useStore, type ViewId } from './store'
import { fmtAgo } from './panels/bits'
import Overview from './views/Overview'
import Actions from './views/Actions'
import FieldVision from './views/FieldVision'
import Water from './views/Water'
import CropProtection from './views/CropProtection'
import WeatherImpact from './views/WeatherImpact'
import ModelEval from './views/ModelEval'
import DeviceHealth from './views/DeviceHealth'
import CaptureModal from './components/CaptureModal'
import Simulator from './panels/Simulator'

const NAV: { id: ViewId; name: string; icon: string }[] = [
  { id: 'overview', name: 'Digital Twin', icon: 'M3 7l9-4 9 4-9 4-9-4zm0 5l9 4 9-4M3 17l9 4 9-4' },
  { id: 'vision', name: 'Field Vision', icon: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z' },
  { id: 'water', name: 'Water Intelligence', icon: 'M12 3s6 6.5 6 11a6 6 0 01-12 0c0-4.5 6-11 6-11z' },
  { id: 'protection', name: 'Crop Protection', icon: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.500-1-8-4-8-9V6l8-3z' },
  { id: 'weather', name: 'Weather Impact', icon: 'M7 18a4 4 0 010-8 5 5 0 019.6-1.500A4.500 4.500 0 0117 18H7z' },
  { id: 'actions', name: 'Action Center', icon: 'M5 12l4 4L19 6' },
  { id: 'models', name: 'Model Evidence', icon: 'M4 20V10m6 10V4m6 16v-7m4 7H2' },
  { id: 'device', name: 'Device Health', icon: 'M6 3h12v18H6zM9 7h6M9 11h6M11 17h2' },
]

export default function App() {
  const ready = useStore((s) => s.ready)
  const view = useStore((s) => s.view)
  const modal = useStore((s) => s.modalCapture)
  const init = useStore((s) => s.init)
  useEffect(() => { init() }, [init])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { const s = useStore.getState(); if (s.modalCapture) s.set({ modalCapture: null }); else s.set({ pinned: null }) } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  if (!ready) return <div className="grid h-full place-items-center text-mist-400">Loading {PRODUCT_NAME}…</div>
  return (
    <div className="flex h-full min-w-[1180px] bg-ink-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="min-h-0 flex-1">
          {view === 'overview' && <Overview />}
          {view === 'vision' && <FieldVision />}
          {view === 'water' && <Water />}
          {view === 'protection' && <CropProtection />}
          {view === 'weather' && <WeatherImpact />}
          {view === 'actions' && <Actions />}
          {view === 'models' && <ModelEval />}
          {view === 'device' && <DeviceHealth />}
        </main>
      </div>
      {modal && <CaptureModal />}
      <Simulator />
    </div>
  )
}

function Sidebar() {
  const view = useStore((s) => s.view)
  const set = useStore((s) => s.set)
  const urgent = useStore((s) => s.actions.filter((a) => a.priority === 1 && !s.doneActions[a.id]).length)
  const unreviewed = useStore((s) => s.captures.filter((c) => c.review.status === 'unreviewed').length)
  return (
    <nav className="flex w-[208px] shrink-0 flex-col border-r border-ink-700 bg-ink-900">
      <div className="flex items-center gap-2.5 border-b border-ink-700 px-4 py-3.5">
        <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden><rect x="1" y="1" width="24" height="24" rx="6" fill="#0e2319" stroke="#2f8f5b" /><path d="M6 17l4-4 3 3 7-8" fill="none" stroke="#63d394" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div className="leading-tight"><div className="text-[16px] font-bold tracking-[0.02em]">{PRODUCT_NAME}</div><div className="text-[9.5px] uppercase tracking-wider text-mist-400">{PRODUCT_TAGLINE}</div></div>
      </div>
      <div className="flex-1 space-y-0.5 p-2">
        {NAV.map((n) => (
          <button key={n.id} onClick={() => set({ view: n.id })} className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors ${view === n.id ? 'bg-ink-700 font-medium text-mist-100' : 'text-mist-300 hover:bg-ink-800 hover:text-mist-100'}`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className={view === n.id ? 'text-leaf-400' : 'text-mist-400'} aria-hidden><path d={n.icon} /></svg>
            <span className="flex-1">{n.name}</span>
            {n.id === 'actions' && urgent > 0 && <span className="num rounded bg-red-alert/20 px-1.5 text-[10.5px] font-semibold text-red-alert">{urgent}</span>}
            {n.id === 'vision' && unreviewed > 0 && <span className="num rounded bg-ink-600 px-1.5 text-[10.5px] text-mist-300">{unreviewed}</span>}
          </button>
        ))}
      </div>
      <div className="border-t border-ink-700 p-3 text-[10.5px] leading-snug text-mist-400">
        Hackathon prototype. Zone data is simulated unless a chip says otherwise. Scores are indicative and need a ground check.
      </div>
    </nav>
  )
}

function Header() {
  const field = useStore((s) => s.field)!
  const mode = useStore((s) => s.mode)
  const sseOk = useStore((s) => s.sseOk)
  const lastSync = useStore((s) => s.lastSync)
  const set = useStore((s) => s.set)
  const realDevice = useStore((s) => s.captures.find((c) => c.provenance === 'real-device'))
  const hasReal = !!realDevice
  const [, tick] = useState(0)
  useEffect(() => { const i = setInterval(() => tick((n) => n + 1), 5000); return () => clearInterval(i) }, [])
  return (
    <header className="flex shrink-0 items-center gap-4 border-b border-ink-700 bg-ink-900 px-4 py-2">
      <div className="leading-tight">
        <div className="text-[13.5px] font-semibold">{field.name}</div>
        <div className="text-[11px] text-mist-400">{field.farm} · {field.crop} · {field.area_acres} ac · {field.rows}×{field.cols} zones</div>
      </div>
      <div className="flex-1" />
      <Stat k="Last sync" v={fmtAgo(lastSync)} />
      <Stat k="Backend" v={mode === 'live' ? (sseOk ? 'connected, live stream' : 'connected') : 'not running'} dot={mode === 'live' ? '#63d394' : '#7f95a1'} />
      <Stat k="Camera" v={hasReal ? `${realDevice!.device_id} · ${fmtAgo(realDevice!.received_at)}` : 'no device seen yet'} dot={hasReal ? '#63d394' : '#f0a93b'} pulse={hasReal} />
      {hasReal ? <span className="chip chip-real">LIVE DEVICE DATA + DEMO DATA</span> : <span className="chip chip-sim">DEMO DATA</span>}
      <button className="btn btn-primary" onClick={() => set({ simOpen: true })}>Simulate capture</button>
    </header>
  )
}

function Stat({ k, v, dot, pulse }: { k: string; v: string; dot?: string; pulse?: boolean }) {
  return (
    <div className="leading-tight">
      <div className="label">{k}</div>
      <div className="flex items-center gap-1.5 text-[12px] text-mist-200">{dot && <span className={`h-1.5 w-1.5 rounded-full ${pulse ? 'pulse' : ''}`} style={{ background: dot }} />}{v}</div>
    </div>
  )
}
