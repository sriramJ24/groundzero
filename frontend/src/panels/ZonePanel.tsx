import { useStore, type ZoneTab } from '../store'
import { ProvChip, ScoreRing, fmtDate, fmtAgo, LABEL_TEXT } from './bits'
import { summarise } from '../data/scoring'
import type { Capture, Risk, Zone } from '../data/types'

const TABS: ZoneTab[] = ['Health', 'Water', 'Spraying', 'Weather', 'Images', 'History']

export default function ZonePanel() {
  const id = useStore((s) => s.pinned ?? s.hovered)
  const pinned = useStore((s) => s.pinned)
  const zone = useStore((s) => (id ? s.zoneById[id] : null))
  const risk = useStore((s) => (id ? s.risks[id] : null))
  const tab = useStore((s) => s.zoneTab)
  const captures = useStore((s) => s.captures)
  const set = useStore((s) => s.set)

  if (!zone || !risk) return <EmptyPanel />
  const zc = captures.filter((c) => c.zone_id === zone.id).sort((a, b) => (a.received_at < b.received_at ? 1 : -1))
  const latest = zc[0]
  const worst = Math.max(risk.drought, risk.heat)

  return (
    <div key={zone.id} className="slide-in flex h-full flex-col">
      <div className="border-b border-ink-700 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="label">Zone</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold tracking-tight">{zone.id}</span>
              <span className="text-xs text-mist-400">row {zone.row + 1} · col {zone.col + 1} · 30 m × 30 m</span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <ProvChip p={zone.provenance} />
              {zc.some((c) => c.provenance === 'real-device') && <ProvChip p="real-device" />}
              <span className="chip">{pinned === zone.id ? 'PINNED · Esc to release' : 'HOVER · click to pin'}</span>
            </div>
          </div>
          <ScoreRing value={zone.health.score} label="health" />
        </div>
        {(worst >= 60 || zone.health.score < 50) && (
          <div className={`mt-3 rounded-md border px-3 py-2 text-[12.5px] ${zone.health.score < 40 || worst >= 75 ? 'border-red-alert/40 bg-red-alert/10 text-red-alert' : 'border-amber-warn/40 bg-amber-warn/10 text-amber-warn'}`}>
            {zone.health.last_label === 'wilting' ? 'Visible wilting with low logged irrigation.' : zone.health.last_label === 'discoloration' ? 'Leaf discoloration flagged by the camera.' : 'Elevated stress risk in the next 72 h.'}{' '}
            <span className="text-mist-300">Indicative, needs a ground check.</span>
          </div>
        )}
      </div>

      <div className="flex border-b border-ink-700 px-1.5">
        {TABS.map((t) => (
          <button key={t} onClick={() => set({ zoneTab: t })} className={`px-2 py-2 text-[11.5px] font-medium transition-colors ${tab === t ? 'border-b-2 border-leaf-400 text-mist-100' : 'border-b-2 border-transparent text-mist-400 hover:text-mist-200'}`}>
            {t}{t === 'Images' && zc.length ? <span className="num ml-1 text-[10px] text-mist-400">{zc.length}</span> : null}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-[13px]">
        {tab === 'Health' && <HealthTab zone={zone} risk={risk} latest={latest} />}
        {tab === 'Water' && <WaterTab zone={zone} risk={risk} />}
        {tab === 'Spraying' && <SprayTab zone={zone} />}
        {tab === 'Weather' && <WeatherTab risk={risk} />}
        {tab === 'Images' && <ImagesTab captures={zc} />}
        {tab === 'History' && <HistoryTab zone={zone} captures={zc} />}
      </div>
    </div>
  )
}

function EmptyPanel() {
  const actions = useStore((s) => s.actions)
  const focus = useStore((s) => s.focusZone)
  return (
    <div className="flex h-full flex-col p-4">
      <div className="label">Zone detail</div>
      <p className="mt-2 text-[13px] leading-relaxed text-mist-300">Hover any zone on the field to see everything known about it. Click to pin it, drag to rotate, scroll to zoom.</p>
      <div className="label mt-6">Top flagged zones</div>
      <div className="mt-2 space-y-1.5 overflow-y-auto">
        {actions.slice(0, 7).map((a) => (
          <button key={a.id} onClick={() => focus(a.zone_id)} className="flex w-full items-center gap-3 rounded-md border border-ink-700 bg-ink-800/60 px-3 py-2 text-left hover:border-ink-500">
            <span className={`num w-9 text-sm font-semibold ${a.priority === 1 ? 'text-red-alert' : a.priority === 2 ? 'text-amber-warn' : 'text-mist-300'}`}>{a.zone_id}</span>
            <span className="text-[12px] leading-snug text-mist-200">{a.title}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

const Row = ({ k, v, sub }: { k: string; v: React.ReactNode; sub?: string }) => (
  <div className="flex items-baseline justify-between gap-3 border-b border-ink-800 py-1.5 last:border-0">
    <span className="text-mist-400">{k}</span>
    <span className="text-right"><span className="num text-mist-100">{v}</span>{sub && <span className="ml-1 text-[11px] text-mist-400">{sub}</span>}</span>
  </div>
)
const Card = ({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) => (
  <div className="rounded-lg border border-ink-700 bg-ink-800/50 p-3">
    <div className="mb-1.5 flex items-center justify-between"><span className="label">{title}</span>{right}</div>
    {children}
  </div>
)
const NotMeasured = () => <span className="text-mist-400 italic">not measured</span>

function Thumb({ c, big }: { c: Capture; big?: boolean }) {
  const set = useStore((s) => s.set)
  return (
    <button onClick={() => set({ modalCapture: c.id })} className={`group relative overflow-hidden rounded-md border border-ink-600 bg-ink-900 ${big ? 'aspect-[4/3] w-full' : 'aspect-[4/3]'}`}>
      <img src={c.image_url} alt={`Capture ${c.id}`} className="h-full w-full object-cover transition-transform group-hover:scale-[1.03]" onError={(e) => { (e.currentTarget.style.opacity = '0.15') }} />
      <span className="absolute left-1.5 top-1.5 rounded bg-ink-950/80 px-1.5 py-0.5 text-[10px] font-semibold" style={{ color: LABEL_TEXT[c.edge_prediction.label] ?? '#c9d5db' }}>
        {c.edge_prediction.label} <span className="num">{Math.round(c.edge_prediction.confidence * 100)}%</span>
      </span>
      {c.live && <span className="absolute right-1.5 top-1.5 rounded bg-leaf-600 px-1.5 py-0.5 text-[9px] font-bold text-ink-950">NEW</span>}
    </button>
  )
}

function Factors({ risk, filter }: { risk: Risk; filter?: (n: string) => boolean }) {
  const fs = risk.factors.filter((f) => !filter || filter(f.name)).sort((a, b) => Math.abs(b.points) - Math.abs(a.points))
  return (
    <div className="space-y-2">
      {fs.map((f) => (
        <div key={f.name}>
          <div className="flex items-center justify-between text-[12px]">
            <span className="text-mist-200">{f.name}</span>
            <span className={`num ${f.points < 0 ? 'text-leaf-400' : 'text-mist-100'}`}>{f.points >= 0 ? '+' : ''}{f.points.toFixed(0)} pts</span>
          </div>
          <div className="mt-1 h-1 rounded bg-ink-700"><div className="h-1 rounded" style={{ width: `${Math.min(100, Math.abs(f.points) * 2.2)}%`, background: f.points < 0 ? '#63d394' : '#f0a93b' }} /></div>
          <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-mist-400"><span>{f.detail}</span><ProvChip p={f.source} tiny /></div>
        </div>
      ))}
    </div>
  )
}

function HealthTab({ zone, risk, latest }: { zone: Zone; risk: Risk; latest?: Capture }) {
  const actions = useStore((s) => s.actions).filter((a) => a.zone_id === zone.id)
  return (
    <>
      {latest ? (
        <Card title="Latest image" right={<span className="text-[11px] text-mist-400">{fmtAgo(latest.received_at)}</span>}>
          <Thumb c={latest} big />
          <div className="mt-2 text-[11.5px] leading-snug text-mist-400">The label describes visible leaf appearance only. It does not identify a cause.</div>
        </Card>
      ) : (
        <Card title="Latest image"><div className="py-4 text-center text-mist-400">No camera pass over this zone yet.</div></Card>
      )}
      <Card title="Indicative scores" right={<span className="chip">RULE-BASED</span>}>
        <Row k="Crop health" v={`${zone.health.score}`} sub="/100" />
        <Row k="Drought risk, 7 d" v={`${risk.drought}`} sub="/100" />
        <Row k="Heat risk, 72 h" v={`${risk.heat}`} sub="/100" />
        <Row k="Images in score" v={zone.health.n_captures} />
        <div className="mt-1.5 text-[11px] text-mist-400">{zone.health.method}. Not a trained or validated model.</div>
      </Card>
      {actions.length > 0 && (
        <Card title="Suggested next steps">
          {actions.map((a) => (
            <div key={a.id} className="mb-2 last:mb-0">
              <div className="font-medium text-mist-100">{a.title}</div>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11.5px] text-mist-400">{a.why.map((w) => <li key={w}>{w}</li>)}</ul>
            </div>
          ))}
        </Card>
      )}
      <Card title="In-field sensors">
        <Row k="Soil moisture" v={<NotMeasured />} />
        <Row k="Canopy temperature" v={<NotMeasured />} />
        <Row k="Light" v={<NotMeasured />} />
        <Row k="GPS position" v={<span className="text-mist-400 italic">none, zone assigned manually</span>} />
      </Card>
    </>
  )
}

function WaterTab({ zone, risk }: { zone: Zone; risk: Risk }) {
  const max = Math.max(...zone.water.events.map((e) => e.mm), 1)
  return (
    <>
      <Card title="Water applied" right={<ProvChip p="simulated" tiny />}>
        <Row k="Last 7 days" v={zone.water.applied_mm_7d.toFixed(1)} sub="mm" />
        <Row k="Last 30 days" v={zone.water.applied_mm_30d.toFixed(1)} sub="mm" />
        <Row k="Volume, 7 d" v={(zone.water.applied_mm_7d * 0.9).toFixed(1)} sub="m³ on 900 m²" />
        <Row k="Last irrigation" v={fmtDate(zone.water.last_irrigation_at)} />
      </Card>
      <Card title="Irrigation log">
        <div className="space-y-1.5">
          {zone.water.events.map((e) => (
            <div key={e.at} className="flex items-center gap-2 text-[12px]">
              <span className="num w-14 text-mist-400">{fmtDate(e.at)}</span>
              <div className="h-2 flex-1 rounded bg-ink-700"><div className="h-2 rounded bg-sky-water" style={{ width: `${(e.mm / max) * 100}%` }} /></div>
              <span className="num w-14 text-right">{e.mm.toFixed(1)} mm</span>
            </div>
          ))}
        </div>
        <div className="mt-2 text-[11px] text-mist-400">Source: {zone.water.events[0]?.source}</div>
      </Card>
      <Card title={`Why drought risk is ${risk.drought}/100`}><Factors risk={risk} filter={(n) => !n.startsWith('Forecast heat') && !n.startsWith('Rain')} /></Card>
      <Card title="Soil"><Row k="Type" v={zone.soil} /><Row k="Soil moisture probe" v={<NotMeasured />} />
        {risk.needs_sensor_validation && <div className="mt-2 rounded border border-amber-warn/30 bg-amber-warn/10 px-2 py-1.5 text-[11.5px] text-amber-warn">Needs sensor validation: this estimate has no in-field moisture reading behind it.</div>}
      </Card>
    </>
  )
}

function SprayTab({ zone }: { zone: Zone }) {
  return (
    <>
      <Card title="Application coverage" right={<ProvChip p="simulated" tiny />}>
        <Row k="Best coverage logged" v={zone.spray.coverage_pct ? `${zone.spray.coverage_pct}%` : 'none'} />
        <Row k="Passes logged" v={zone.spray.events.length} />
      </Card>
      <Card title="Application log">
        {zone.spray.events.length === 0 && <div className="py-2 text-mist-400">No application recorded for this zone.</div>}
        {zone.spray.events.map((e) => (
          <div key={e.at} className="border-b border-ink-800 py-1.5 last:border-0">
            <div className="flex justify-between"><span>{e.product_class}</span><span className="num text-mist-400">{fmtDate(e.at)}</span></div>
            <div className="num text-[11.5px] text-mist-400">logged rate {e.rate_l_ha} L/ha spray volume · coverage {e.coverage_pct}%</div>
          </div>
        ))}
      </Card>
      <Card title="Post-treatment trend (observational)">
        <Spark data={zone.history.map((h) => h.score)} />
        <div className="mt-1.5 text-[11.5px] leading-snug text-mist-400">Health score by week. Coverage and rate are what was applied, not whether it worked. The dashboard makes no product or dosage recommendation.</div>
      </Card>
    </>
  )
}

function WeatherTab({ risk }: { risk: Risk }) {
  const weather = useStore((s) => s.weather)
  const s = summarise(weather)
  return (
    <>
      <Card title="Forecast for the field" right={<ProvChip p={weather.provenance ?? 'public-weather'} tiny />}>
        <Row k="Max temperature, 72 h" v={s.tmax3.toFixed(1)} sub="°C" />
        <Row k="Rain, 72 h" v={s.rain3.toFixed(1)} sub="mm" />
        <Row k="Crop water demand (ET₀), 7 d" v={s.et0_7.toFixed(0)} sub="mm" />
        <Row k="Rain, 7 d" v={s.rain7.toFixed(1)} sub="mm" />
        <div className="mt-1.5 text-[11px] text-mist-400">{weather.source}</div>
      </Card>
      <Card title={`Impact on this zone: ${risk.forecast_impact}/100`} right={<span className="chip">RULE-BASED</span>}>
        <Factors risk={risk} />
        <div className="mt-2 text-[11px] text-mist-400">Forecast impact = 0.65 × drought + 0.35 × heat − rain relief. Weights are stated assumptions, not fitted values.</div>
      </Card>
      {risk.missing_inputs.length > 0 && <Card title="Missing inputs"><div className="text-mist-300">{risk.missing_inputs.join(' · ')}</div></Card>}
    </>
  )
}

function ImagesTab({ captures }: { captures: Capture[] }) {
  if (!captures.length) return <div className="py-8 text-center text-mist-400">No images for this zone yet.<br />Use the simulator or the camera to add one.</div>
  return <div className="grid grid-cols-2 gap-2">{captures.map((c) => <Thumb key={c.id} c={c} />)}</div>
}

function HistoryTab({ zone, captures }: { zone: Zone; captures: Capture[] }) {
  const events = [
    ...captures.map((c) => ({ at: c.received_at, text: `Image: ${c.edge_prediction.label} (${Math.round(c.edge_prediction.confidence * 100)}%)`, color: LABEL_TEXT[c.edge_prediction.label] ?? '#a3b5bf', sub: `${c.device_id} · ${c.review.status}` })),
    ...zone.water.events.map((e) => ({ at: e.at, text: `Irrigation ${e.mm.toFixed(1)} mm`, color: '#4aa8e8', sub: e.source })),
    ...zone.spray.events.map((e) => ({ at: e.at, text: `${e.product_class}, ${e.coverage_pct}% coverage`, color: '#a487f2', sub: 'application log (simulated)' })),
  ].sort((a, b) => (a.at < b.at ? 1 : -1))
  return (
    <>
      <Card title="Health score, last 6 weeks" right={<ProvChip p="simulated" tiny />}><Spark data={zone.history.map((h) => h.score)} /></Card>
      <Card title="Timeline">
        <div className="space-y-2">
          {events.map((e, i) => (
            <div key={i} className="flex gap-2.5">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: e.color }} />
              <div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><span className="truncate">{e.text}</span><span className="num shrink-0 text-[11px] text-mist-400">{fmtDate(e.at)}</span></div><div className="truncate text-[11px] text-mist-400">{e.sub}</div></div>
            </div>
          ))}
        </div>
      </Card>
    </>
  )
}

function Spark({ data }: { data: number[] }) {
  const w = 260, h = 54, min = Math.min(...data, 0), max = Math.max(...data, 100)
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / (max - min)) * (h - 6) - 3}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{ height: 54 }}>
      <polyline points={pts} fill="none" stroke="#63d394" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      {data.map((v, i) => <circle key={i} cx={(i / (data.length - 1)) * w} cy={h - ((v - min) / (max - min)) * (h - 6) - 3} r="2.5" fill="#0f171d" stroke="#63d394" strokeWidth="1.5" />)}
    </svg>
  )
}
