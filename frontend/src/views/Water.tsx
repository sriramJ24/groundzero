import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useStore } from '../store'

const TT = { contentStyle: { background: '#0f171d', border: '1px solid #263742', fontSize: 12 } }
const AX = { tick: { fill: '#7f95a1', fontSize: 11 }, stroke: '#263742' }
const ZONE_M2 = 900
const THRESH = 20
const f = (v: unknown, d = 4) => (typeof v === 'number' && isFinite(v) ? String(Number(v.toPrecision(d))) : 'not available')

function waterColor(v: number, max: number) {
  const t = max > 0 ? Math.min(1, v / max) : 0
  const a = 0.12 + 0.88 * t
  return `rgba(74,168,232,${a.toFixed(2)})`
}

export default function Water() {
  const zones = useStore((s) => s.zones)
  const risks = useStore((s) => s.risks)
  const focusZone = useStore((s) => s.focusZone)
  const soilHistory = useStore((s) => s.evals.soilHistory)
  const soilForecast = useStore((s) => s.evals.soilForecast)

  const m = useMemo(() => {
    const n = zones.length
    const total = zones.reduce((a, z) => a + z.water.applied_mm_7d, 0)
    const m3 = (total * ZONE_M2) / 1000
    const under = zones.filter((z) => z.water.applied_mm_7d < THRESH).length
    const driest = zones.reduce<typeof zones[number] | null>((b, z) => (!b || z.water.applied_mm_7d < b.water.applied_mm_7d ? z : b), null)
    const max = Math.max(1, ...zones.map((z) => z.water.applied_mm_7d))
    const bands: Record<number, { sum: number; n: number }> = {}
    zones.forEach((z) => { const b = (bands[z.row] ??= { sum: 0, n: 0 }); b.sum += z.water.applied_mm_7d; b.n++ })
    const bandData = Object.keys(bands).map(Number).sort((a, b) => a - b).map((r) => ({ band: `Row ${r + 1}`, mm: Number((bands[r].sum / bands[r].n).toFixed(1)) }))
    const top = [...zones].sort((a, b) => (risks[b.id]?.drought ?? 0) - (risks[a.id]?.drought ?? 0) || a.water.applied_mm_7d - b.water.applied_mm_7d).slice(0, 10)
    const uni = n ? total / n : 0
    const dsum = zones.reduce((a, z) => a + (risks[z.id]?.drought ?? 0), 0)
    const tgt = zones.map((z) => (dsum > 0 ? (total * (risks[z.id]?.drought ?? 0)) / dsum : uni))
    const tgtUnder = tgt.filter((v) => v < THRESH).length
    const uniUnder = uni < THRESH ? n : 0
    return { n, total, m3, under, driest, max, bandData, top, uni, uniUnder, tgtUnder, tgtMin: Math.min(...tgt), tgtMax: Math.max(...tgt) }
  }, [zones, risks])

  const hist = useMemo(() => {
    const days: any[] = soilHistory?.days ?? []
    return days.slice(-90).map((d) => ({ date: String(d.date).slice(5), sm: d.soil_moisture_0_7cm_m3m3 }))
  }, [soilHistory])

  const fc = useMemo(() => {
    if (!soilForecast) return { data: [] as any[], preds: [] as any[] }
    const h: any[] = (soilForecast.history ?? []).slice(-48)
    const p: any[] = soilForecast.predictions ?? []
    const data: any[] = h.map((x) => ({ t: String(x.time).slice(5, 13).replace('T', ' '), obs: x.value }))
    p.forEach((x) => data.push({ t: String(x.time).slice(5, 13).replace('T', ' '), pred: x.value }))
    return { data, preds: p }
  }, [soilForecast])

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold">Water</h1>
          <span className="chip chip-sim">SIMULATED</span>
          <span className="chip chip-pub">ERA5-LAND MODELLED</span>
        </div>
        <p className="text-[13px] text-mist-300">Irrigation applied in the last 7 days per zone (simulated logs), with modelled soil moisture for the location.</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          ['Applied, 7 d total', `${f(m.m3, 4)} m3`, `${f(m.total, 4)} mm x zones, 900 m2 per zone`],
          [`Zones under ${THRESH} mm`, `${m.under} / ${m.n}`, 'Applied in last 7 d'],
          ['Driest zone', m.driest ? m.driest.id : 'none', m.driest ? `${f(m.driest.water.applied_mm_7d, 3)} mm in 7 d` : ''],
          ['Mean per zone', `${f(m.uni, 3)} mm`, 'Simple average'],
        ].map(([k, v, s]) => (
          <div key={k} className="panel p-4">
            <div className="label">{k}</div>
            <div className="num text-2xl text-sky-water mt-1">{v}</div>
            <div className="text-[11px] text-mist-400 mt-1">{s}</div>
            <span className="chip chip-sim mt-2">SIMULATED</span>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="panel p-4">
          <div className="flex items-center justify-between mb-2"><div className="label">Applied mm, 7 d (click a zone)</div><span className="chip chip-sim">SIMULATED</span></div>
          <div className="grid gap-[2px]" style={{ gridTemplateColumns: 'repeat(12, 1fr)' }}>
            {[...zones].sort((a, b) => a.row - b.row || a.col - b.col).map((z) => (
              <button key={z.id} title={`${z.id}: ${f(z.water.applied_mm_7d, 3)} mm`} onClick={() => focusZone(z.id, 'Water')}
                className="aspect-square rounded-[3px] border border-ink-900 text-[9px] num text-mist-100/80 hover:outline hover:outline-1 hover:outline-mist-100"
                style={{ background: waterColor(z.water.applied_mm_7d, m.max) }}>{z.id}</button>
            ))}
          </div>
          <div className="text-[11px] text-mist-400 mt-2">Darker blue = more water. Scale 0 to {f(m.max, 3)} mm.</div>
        </div>
        <div className="panel p-4">
          <div className="flex items-center justify-between mb-2"><div className="label">Mean applied mm by row band</div><span className="chip chip-sim">SIMULATED</span></div>
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={m.bandData}>
                <CartesianGrid stroke="#1b2831" vertical={false} />
                <XAxis dataKey="band" {...AX} /><YAxis {...AX} />
                <Tooltip {...TT} />
                <Bar dataKey="mm" fill="#4aa8e8" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Highest drought risk, lowest water (top 10)</div><span className="chip chip-sim">SIMULATED</span></div>
        <table className="w-full text-[12.5px]">
          <thead><tr className="text-left text-mist-400"><th className="py-1">Zone</th><th>Drought risk</th><th>Applied 7 d (mm)</th><th>Applied 30 d (mm)</th><th></th></tr></thead>
          <tbody>
            {m.top.map((z) => (
              <tr key={z.id} className="border-t border-ink-700">
                <td className="py-1.5 num">{z.id}</td>
                <td className="num text-amber-warn">{risks[z.id]?.drought ?? 'n/a'}</td>
                <td className="num">{f(z.water.applied_mm_7d, 3)}</td>
                <td className="num">{f(z.water.applied_mm_30d, 3)}</td>
                <td className="text-right"><button className="btn" onClick={() => focusZone(z.id, 'Water')}>Open zone</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[11px] text-mist-400 mt-2">Drought risk is a rule-based indicative score, not a trained model.</p>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Same water, two strategies</div><span className="chip chip-sim">SIMULATED</span></div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="bg-ink-800 rounded-md p-3">
            <div className="text-[13px] font-semibold">Uniform</div>
            <div className="num text-lg">{f(m.uni, 3)} mm everywhere</div>
            <div className="text-[12px] text-mist-300">Zones under {THRESH} mm: <span className="num text-mist-100">{m.uniUnder} / {m.n}</span></div>
          </div>
          <div className="bg-ink-800 rounded-md p-3">
            <div className="text-[13px] font-semibold">Targeted by drought risk</div>
            <div className="num text-lg">{f(m.tgtMin, 3)} to {f(m.tgtMax, 3)} mm</div>
            <div className="text-[12px] text-mist-300">Zones under {THRESH} mm: <span className="num text-mist-100">{m.tgtUnder} / {m.n}</span></div>
          </div>
        </div>
        <ul className="list-disc ml-5 mt-3 text-[12px] text-mist-300 space-y-0.5">
          <li>Total volume is the field's logged 7-day total ({f(m.total, 4)} mm x zones), held constant.</li>
          <li>Uniform: equal mm in every zone. Targeted: mm proportional to each zone's indicative drought risk score.</li>
          <li>Threshold of {THRESH} mm in 7 d is an arbitrary comparison line, not an agronomic requirement.</li>
          <li>No losses, soil differences, rain or crop response are modelled.</li>
        </ul>
        <p className="text-[12px] text-amber-warn mt-2">Illustrative arithmetic on simulated logs, not a yield or savings estimate.</p>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
          <div className="label">Soil moisture, 0 to 7 cm (modelled reanalysis for the location)</div>
          <div className="flex gap-2"><span className="chip chip-pub">OPEN-METEO ERA5-LAND</span><span className="chip chip-pub">NASA POWER</span></div>
        </div>
        <p className="text-[12px] text-mist-400 mb-2">This is modelled reanalysis at a roughly 9-11 km grid for the location, not a probe in this field.</p>
        {hist.length === 0 ? <p className="text-[12.5px] text-mist-400">Soil history not available yet.</p> : (
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hist}>
                <CartesianGrid stroke="#1b2831" />
                <XAxis dataKey="date" {...AX} interval={9} /><YAxis {...AX} domain={['auto', 'auto']} />
                <Tooltip {...TT} />
                <Line type="monotone" dataKey="sm" name="m3/m3" stroke="#4aa8e8" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {fc.preds.length > 0 && (
          <div className="mt-4">
            <div className="label mb-1">Model forecast from {String(soilForecast?.issued_from ?? '')}</div>
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={fc.data}>
                  <CartesianGrid stroke="#1b2831" />
                  <XAxis dataKey="t" {...AX} interval={11} /><YAxis {...AX} domain={['auto', 'auto']} />
                  <Tooltip {...TT} />
                  <Line type="monotone" dataKey="obs" name="modelled history" stroke="#4aa8e8" dot={false} connectNulls />
                  <Line type="monotone" dataKey="pred" name="forecast" stroke="#f0a93b" strokeWidth={0} dot={{ r: 5, fill: '#f0a93b' }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <table className="w-full text-[12.5px] mt-2">
              <thead><tr className="text-left text-mist-400"><th>Horizon</th><th>Predicted (m3/m3)</th><th>Test MAE (m3/m3)</th></tr></thead>
              <tbody>
                {fc.preds.map((p) => (
                  <tr key={p.hours} className="border-t border-ink-700"><td className="py-1 num">+{p.hours} h</td><td className="num">{f(p.value)}</td><td className="num">&plusmn; {f(p.test_mae)}</td></tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-mist-400 mt-2">{soilForecast?.model_variant} The MAE is from a test on observed-weather stand-ins and is optimistic.</p>
          </div>
        )}
      </div>
    </div>
  )
}
