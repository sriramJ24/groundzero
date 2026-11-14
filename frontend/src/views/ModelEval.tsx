import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useStore } from '../store'

const TT = { contentStyle: { background: '#0f171d', border: '1px solid #263742', fontSize: 12 } }
const AX = { tick: { fill: '#7f95a1', fontSize: 11 }, stroke: '#263742' }
const f = (v: unknown, d = 4) => (typeof v === 'number' && isFinite(v) ? String(Number(v.toPrecision(d))) : 'not reported')
const arr = (v: any): any[] => (Array.isArray(v) ? v : [])

function Pending({ name, status }: { name: string; status?: string }) {
  return <p className="text-[12.5px] text-mist-400">{status ? `${name}: ${status}` : `${name}: not available yet.`}</p>
}
const statusBad = (e: any) => e?.status && !['ok', 'OK', 'success'].includes(String(e.status))
function Limits({ items }: { items: any[] }) {
  if (!items.length) return null
  return (
    <div className="mt-3">
      <div className="label mb-1">Limitations</div>
      <ul className="list-disc ml-5 text-[12px] text-mist-300 space-y-1">{items.map((l, i) => <li key={i}>{typeof l === 'string' ? l : JSON.stringify(l)}</li>)}</ul>
    </div>
  )
}
function Feats({ items }: { items: any[] }) {
  if (!items.length) return null
  return (
    <div className="mt-3">
      <div className="label mb-1">Top features (permutation importance)</div>
      <div className="flex flex-wrap gap-1.5">
        {items.slice(0, 10).map((x, i) => <span key={i} className="chip">{x.feature ?? x.name ?? JSON.stringify(x)}{typeof (x.importance_mae_increase ?? x.importance) === 'number' ? ` ${f(x.importance_mae_increase ?? x.importance, 3)}` : ''}</span>)}
      </div>
    </div>
  )
}

export default function ModelEval() {
  const fc = useStore((s) => s.evals.forecast)
  const oc = useStore((s) => s.evals.outcome)
  const di = useStore((s) => s.evals.droughtImage)
  const ndvi = useStore((s) => s.ndvi)

  const variants = arr(fc?.variants)
  const bars = (() => {
    const out: any[] = []
    variants.forEach((v) => arr(v.horizons).forEach((h) => out.push({ k: `+${h.hours} h ${v.uses_future_weather ? 'w/ future wx' : 'no future wx'}`, model: h.mae, persistence: h.persistence_mae })))
    return out
  })()
  const growth = (() => {
    const g = oc?.growth_curves
    return arr(g?.days).map((d: any, i: number) => ({ day: d, control: g.control_mean?.[i], stress: g.stress_mean?.[i] }))
  })()
  const byPeriod = (() => {
    const a = di?.accuracy_by_period
    if (Array.isArray(a)) return a.map((x: any) => ({ period: x.period ?? x.name ?? x.label, accuracy: x.accuracy ?? x.value }))
    if (a && typeof a === 'object') return Object.entries(a).map(([period, accuracy]) => ({ period, accuracy: typeof accuracy === 'number' ? accuracy : (accuracy as any)?.accuracy }))
    return []
  })()
  const series = arr(ndvi?.series).map((s) => ({ date: s.date, mean: s.mean }))

  return (
    <div className="h-full overflow-y-auto p-5 space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-semibold">What has actually been measured</h1>
          <span className="chip chip-pub">PUBLIC DATASETS</span>
        </div>
        <p className="text-[13px] text-mist-300">Every metric on this page is read from an evaluation file. None of it is a measurement on this specific field.</p>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1"><div className="label">A. Soil moisture forecast (0 to 7 cm)</div><span className="chip chip-pub">ERA5-LAND MODELLED</span></div>
        {!fc ? <Pending name="Forecast evaluation" /> : (
          <>
            <p className="text-[12px] text-mist-400">Target: {fc.target} ({fc.units}). Data: {fc.data_source}. Train {fc.train_period} (n={fc.n_train}), validation {fc.val_period}, test {fc.test_period} (n={fc.n_test}).</p>
            <p className="text-[13px] text-amber-warn my-2">Without knowledge of future weather the model does not beat persistence; with observed future weather as a stand-in for a forecast it does. Real forecast error would land in between.</p>
            {variants.map((v) => (
              <div key={v.name} className="mb-3">
                <div className="text-[13px] font-semibold mb-1">{v.name} <span className="text-mist-400 font-normal">(uses future weather: {String(v.uses_future_weather)})</span></div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead><tr className="text-left text-mist-400"><th className="py-1">Horizon</th><th>MAE</th><th>RMSE</th><th>R2</th><th>Persistence MAE</th><th>Persistence RMSE</th><th>Climatology MAE</th><th>Skill vs persistence</th></tr></thead>
                    <tbody>
                      {arr(v.horizons).map((h) => (
                        <tr key={h.hours} className="border-t border-ink-700 num">
                          <td className="py-1">+{h.hours} h</td><td>{f(h.mae)}</td><td>{f(h.rmse)}</td><td>{f(h.r2)}</td><td>{f(h.persistence_mae)}</td><td>{f(h.persistence_rmse)}</td><td>{f(h.climatology_mae)}</td>
                          <td className={h.skill_vs_persistence_pct >= 0 ? 'text-leaf-400' : 'text-red-alert'}>{f(h.skill_vs_persistence_pct)} %</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            {bars.length > 0 && (
              <div style={{ height: 260 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bars}>
                    <CartesianGrid stroke="#1b2831" vertical={false} />
                    <XAxis dataKey="k" {...AX} interval={0} tick={{ fill: '#7f95a1', fontSize: 10 }} /><YAxis {...AX} />
                    <Tooltip {...TT} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#7f95a1' }} />
                    <Bar dataKey="model" name="Model MAE" radius={[3, 3, 0, 0]}>
                      {bars.map((b, i) => <Cell key={i} fill={b.model < b.persistence ? '#63d394' : '#ef5a4c'} />)}
                    </Bar>
                    <Bar dataKey="persistence" name="Persistence MAE" fill="#7f95a1" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            <p className="text-[11px] text-mist-400">Model bars are green where MAE is below persistence, red where it is not. Lower MAE is better.</p>
            <Feats items={arr(fc.top_features)} />
            <Limits items={arr(fc.limitations)} />
          </>
        )}
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1"><div className="label">B. Crop outcome under stress</div><span className="chip chip-pub">{oc?.dataset?.name ? String(oc.dataset.name).toUpperCase() : 'PUBLIC DATASET'}</span></div>
        {!oc ? <Pending name="Crop outcome evaluation" /> : statusBad(oc) ? <Pending name="Crop outcome evaluation" status={String(oc.status)} /> : (
          <>
            <p className="text-[12px] text-mist-400">Dataset: {oc.dataset?.name} ({f(oc.dataset?.n_plants, 6)} plants, {f(oc.dataset?.n_genotypes, 6)} genotypes). Licence: {oc.dataset?.license ?? 'not stated'}. DOI: <span className="num">{oc.dataset?.doi ?? 'not stated'}</span></p>
            {oc.design && <p className="text-[12px] text-mist-300 mt-1">Design: {typeof oc.design === 'string' ? oc.design : [oc.design.experiments, oc.design.day_axis, oc.design.feature_windows, oc.design.split ?? oc.design.validation].filter((x) => typeof x === 'string').join('. ')}</p>}
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-[12px]">
                <thead><tr className="text-left text-mist-400"><th className="py-1">Target</th><th>Model</th><th>R2</th><th>MAE</th><th>MAE %</th></tr></thead>
                <tbody>
                  {arr(oc.targets).flatMap((t) => [
                    <tr key={t.name} className="border-t border-ink-700 num"><td className="py-1">{t.name}</td><td>model</td><td>{f(t.model?.r2)}</td><td>{f(t.model?.mae)}</td><td>{f(t.model?.mae_pct)}</td></tr>,
                    ...arr(t.baselines).map((b) => <tr key={t.name + b.name} className="num text-mist-400"><td></td><td>baseline: {b.name}</td><td>{f(b.r2)}</td><td>{f(b.mae)}</td><td></td></tr>),
                  ])}
                </tbody>
              </table>
            </div>
            {oc.treatment_effect && <p className="text-[12.5px] mt-2">Treatment effect in the dataset: control mean <span className="num">{f(oc.treatment_effect.control_mean)}</span>, stress mean <span className="num">{f(oc.treatment_effect.stress_mean)}</span>, reduction <span className="num">{f(oc.treatment_effect.pct_reduction)} %</span>.</p>}
            {growth.length > 0 && (
              <div className="mt-3" style={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={growth}>
                    <CartesianGrid stroke="#1b2831" />
                    <XAxis dataKey="day" {...AX} /><YAxis {...AX} />
                    <Tooltip {...TT} /><Legend wrapperStyle={{ fontSize: 11, color: '#7f95a1' }} />
                    <Line type="monotone" dataKey="control" stroke="#63d394" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="stress" stroke="#f0a93b" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            <Feats items={arr(oc.top_features)} />
            {oc.dataset?.citation && <p className="text-[11px] text-mist-400 mt-3">Citation: {oc.dataset.citation}</p>}
            <Limits items={arr(oc.limitations)} />
          </>
        )}
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1"><div className="label">C. Camera drought detection (public image dataset)</div><span className="chip chip-pub">{di?.dataset?.name ? String(di.dataset.name).toUpperCase() : 'PUBLIC DATASET'}</span></div>
        {!di ? <Pending name="Drought image evaluation" /> : statusBad(di) ? <Pending name="Drought image evaluation" status={String(di.status)} /> : (
          <>
            {di.dataset && <p className="text-[12px] text-mist-400">Dataset: {di.dataset.name ?? 'not named'}{di.dataset.license ? `. Licence: ${di.dataset.license}` : ''}{di.dataset.citation ? `. ${di.dataset.citation}` : ''}</p>}
            {di.features && <p className="text-[12px] text-mist-400">Features: {typeof di.features === 'string' ? di.features : JSON.stringify(di.features)}</p>}
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-[12px]">
                <thead><tr className="text-left text-mist-400"><th className="py-1">Model</th><th>Split</th><th>Accuracy</th><th>Balanced accuracy</th><th>AUC</th><th>n train</th><th>n test</th><th>Confusion</th></tr></thead>
                <tbody>
                  {arr(di.models).map((m, i) => (
                    <tr key={i} className="border-t border-ink-700 num"><td className="py-1">{m.name}</td><td>{m.split}</td><td>{f(m.accuracy)}</td><td>{f(m.balanced_accuracy)}</td><td>{f(m.auc)}</td><td>{f(m.n_train, 6)}</td><td>{f(m.n_test, 6)}</td><td>{m.confusion ? JSON.stringify(m.confusion) : 'not reported'}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            {byPeriod.length > 0 && (
              <div className="mt-3" style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={byPeriod}>
                    <CartesianGrid stroke="#1b2831" vertical={false} />
                    <XAxis dataKey="period" {...AX} /><YAxis {...AX} domain={[0, 1]} />
                    <Tooltip {...TT} />
                    <Bar dataKey="accuracy" fill="#4aa8e8" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            <Limits items={arr(di.limitations)} />
          </>
        )}
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-1"><div className="label">D. Satellite NDVI</div><span className="chip chip-pub">SENTINEL-2</span></div>
        {!ndvi ? <Pending name="NDVI data" /> : (
          <>
            <p className="text-[12.5px]">Latest scene <span className="num">{ndvi.latest.scene_id}</span> on <span className="num">{ndvi.latest.date}</span>: min <span className="num">{f(ndvi.latest.min, 3)}</span>, mean <span className="num">{f(ndvi.latest.mean, 3)}</span>, max <span className="num">{f(ndvi.latest.max, 3)}</span>.</p>
            {series.length > 0 && (
              <div className="mt-2" style={{ height: 220 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series}>
                    <CartesianGrid stroke="#1b2831" />
                    <XAxis dataKey="date" {...AX} /><YAxis {...AX} domain={['auto', 'auto']} />
                    <Tooltip {...TT} />
                    <Line type="monotone" dataKey="mean" name="Mean NDVI" stroke="#63d394" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            {ndvi.caveat && <p className="text-[12px] text-amber-warn mt-2">{ndvi.caveat}</p>}
          </>
        )}
      </div>

      <div className="panel p-4 border-amber-warn/40">
        <div className="label mb-1">Not measured</div>
        <ul className="list-disc ml-5 text-[12.5px] text-mist-300 space-y-1">
          <li>On-device model accuracy (the model is not trained yet).</li>
          <li>Pesticide efficacy.</li>
          <li>Forecast skill against in-field probes.</li>
          <li>Anything on this specific field.</li>
        </ul>
      </div>
    </div>
  )
}
