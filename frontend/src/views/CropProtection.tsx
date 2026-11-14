import { useMemo } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useStore } from '../store'

const TT = { contentStyle: { background: '#0f171d', border: '1px solid #263742', fontSize: 12 } }
const AX = { tick: { fill: '#7f95a1', fontSize: 11 }, stroke: '#263742' }
const f = (v: unknown, d = 3) => (typeof v === 'number' && isFinite(v) ? String(Number(v.toPrecision(d))) : 'not available')

export default function CropProtection() {
  const zones = useStore((s) => s.zones)
  const focusZone = useStore((s) => s.focusZone)

  const m = useMemo(() => {
    const treated = zones.filter((z) => z.spray.events.length > 0)
    const untreated = zones.filter((z) => z.spray.events.length === 0)
    const meanCov = treated.length ? treated.reduce((a, z) => a + z.spray.coverage_pct, 0) / treated.length : null
    const passes: Record<string, { date: string; product: string; rate: number[]; zones: string[]; cov: number[] }> = {}
    treated.forEach((z) => z.spray.events.forEach((e) => {
      const date = e.at.slice(0, 10)
      const key = `${date}|${e.product_class}`
      const p = (passes[key] ??= { date, product: e.product_class, rate: [], zones: [], cov: [] })
      p.rate.push(e.rate_l_ha); p.zones.push(z.id); p.cov.push(e.coverage_pct)
    }))
    const plist = Object.values(passes).sort((a, b) => (a.date < b.date ? 1 : -1))
    const latest = plist[0]?.date ?? null
    const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)
    const trend = [5, 4, 3, 2, 1, 0].map((w) => {
      const pick = (zs: typeof zones) => avg(zs.map((z) => z.history.find((h) => h.weeks_ago === w)?.score).filter((x): x is number => typeof x === 'number'))
      return { week: w === 0 ? 'now' : `-${w} w`, treated: pick(treated), untreated: pick(untreated) }
    })
    return { treated, untreated, meanCov, plist, latest, trend }
  }, [zones])

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold">Crop Protection</h1>
          <span className="chip chip-sim">SIMULATED</span>
        </div>
        <p className="text-[13px] text-mist-300">Logged application passes and coverage per zone (simulated machine records).</p>
      </div>

      <div className="panel p-3 border-amber-warn/40 text-[12.5px] text-mist-200">
        No dosage or product recommendations are made in this dashboard. Logged rates are simulated records only; consult a qualified agronomist and the product label.
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="panel p-4"><div className="label">Zones covered</div><div className="num text-2xl text-violet-spray mt-1">{m.treated.length} / {zones.length}</div><span className="chip chip-sim mt-2">SIMULATED</span></div>
        <div className="panel p-4"><div className="label">Mean coverage, treated zones</div><div className="num text-2xl text-violet-spray mt-1">{m.meanCov === null ? 'not available' : `${f(m.meanCov, 3)} %`}</div><span className="chip chip-sim mt-2">SIMULATED</span></div>
        <div className="panel p-4"><div className="label">Most recent pass</div><div className="num text-2xl text-violet-spray mt-1">{m.latest ?? 'none logged'}</div><span className="chip chip-sim mt-2">SIMULATED</span></div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Coverage by zone (click a zone)</div><span className="chip chip-sim">SIMULATED</span></div>
        <div className="grid gap-[2px] max-w-xl" style={{ gridTemplateColumns: 'repeat(12, 1fr)' }}>
          {[...zones].sort((a, b) => a.row - b.row || a.col - b.col).map((z) => {
            const c = z.spray.coverage_pct
            return (
              <button key={z.id} title={`${z.id}: ${z.spray.events.length ? f(c, 3) + ' %' : 'no application logged'}`} onClick={() => focusZone(z.id, 'Spraying')}
                className="aspect-square rounded-[3px] border border-ink-900 text-[9px] num text-mist-100/80 hover:outline hover:outline-1 hover:outline-mist-100"
                style={{ background: z.spray.events.length ? `rgba(164,135,242,${(0.15 + 0.85 * Math.min(1, c / 100)).toFixed(2)})` : '#131d24' }}>{z.id}</button>
            )
          })}
        </div>
        <div className="text-[11px] text-mist-400 mt-2">Dark cells: no application logged. Purple intensity = logged coverage percent.</div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Application log, grouped by pass</div><span className="chip chip-sim">SIMULATED</span></div>
        {m.plist.length === 0 ? <p className="text-[12.5px] text-mist-400">No applications logged.</p> : (
          <table className="w-full text-[12.5px]">
            <thead><tr className="text-left text-mist-400"><th className="py-1">Date</th><th>Zones</th><th>Product class</th><th>Rate L/ha</th><th>Coverage %</th></tr></thead>
            <tbody>
              {m.plist.map((p) => {
                const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length
                const lo = Math.min(...p.rate), hi = Math.max(...p.rate)
                return (
                  <tr key={p.date + p.product} className="border-t border-ink-700 align-top">
                    <td className="py-1.5 num">{p.date}</td>
                    <td className="num"><span className="text-mist-100">{p.zones.length}</span> <span className="text-mist-400 text-[11px]">{p.zones.slice(0, 8).join(' ')}{p.zones.length > 8 ? ' ...' : ''}</span></td>
                    <td>{p.product}</td>
                    <td className="num">{lo === hi ? f(lo) : `${f(lo)} to ${f(hi)}`}</td>
                    <td className="num">{f(mean(p.cov), 3)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2"><div className="label">Post-treatment observational trend</div><span className="chip chip-sim">SIMULATED</span></div>
        <p className="text-[12px] text-mist-400 mb-2">Mean zone health score by week: {m.treated.length} treated zones vs {m.untreated.length} untreated zones.</p>
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={m.trend}>
              <CartesianGrid stroke="#1b2831" />
              <XAxis dataKey="week" {...AX} /><YAxis {...AX} domain={['auto', 'auto']} />
              <Tooltip {...TT} formatter={(v: any) => (typeof v === 'number' ? v.toFixed(1) : v)} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#7f95a1' }} />
              <Line type="monotone" dataKey="treated" stroke="#a487f2" strokeWidth={2} dot={false} connectNulls />
              <Line type="monotone" dataKey="untreated" stroke="#7f95a1" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[12px] text-amber-warn mt-2">Observational trend on simulated data. Applied rate and coverage are not biological efficacy, and this is not a causal estimate.</p>
      </div>
    </div>
  )
}
