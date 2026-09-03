import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useTheme } from '../lib/theme'

/**
 * Per-frame / per-window manipulation probability over time.
 *
 * One series, so no legend box is needed — the title names it. The threshold is
 * a dashed reference line, distinguished by line style as well as colour, and
 * points above it are marked so the flagged region survives greyscale printing.
 */
export default function ConfidenceChart({ points, unit, threshold = 0.5 }) {
  const { resolved } = useTheme()
  const dark = resolved === 'dark'

  const series = dark ? '#3987e5' : '#2a78d6'
  const critical = '#d03b3b'
  const grid = dark ? '#232b38' : '#e3e7ee'
  const axis = dark ? '#7d8899' : '#6b7688'
  const surface = dark ? '#141922' : '#ffffff'

  const data = points.map((point) => ({
    t: point.timestamp ?? point.start,
    p: point.fake_probability,
    flagged: point.fake_probability >= threshold,
  }))

  const flaggedCount = data.filter((d) => d.flagged).length

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1.5
                      text-[0.75rem] text-ink-secondary">
        <span className="flex items-center gap-1.5">
          <svg width="18" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="18" y2="4" stroke={series} strokeWidth="2" />
          </svg>
          P(manipulated)
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="18" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="18" y2="4" stroke={critical} strokeWidth="2"
                  strokeDasharray="4 3" />
          </svg>
          Decision threshold ({threshold.toFixed(2)})
        </span>
        {flaggedCount > 0 && (
          <span className="flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden="true">
              <circle cx="5" cy="5" r="4" fill={critical} stroke={surface} strokeWidth="2" />
            </svg>
            {flaggedCount} flagged
          </span>
        )}
      </div>

      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 12, bottom: 18, left: 4 }}>
            <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="t" type="number" domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11, fill: axis }} tickLine={false}
              axisLine={{ stroke: grid }}
              tickFormatter={(v) => `${v}s`}
              label={{ value: 'Time (seconds)', position: 'insideBottom', offset: -8,
                       fontSize: 11, fill: axis }}
            />
            <YAxis
              domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]}
              tick={{ fontSize: 11, fill: axis }} tickLine={false}
              axisLine={false} width={38}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
            />
            <Tooltip
              cursor={{ stroke: axis, strokeWidth: 1, strokeDasharray: '3 3' }}
              contentStyle={{
                background: surface, border: `1px solid ${grid}`, borderRadius: 10,
                fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,.12)', padding: '8px 10px',
              }}
              labelStyle={{ color: axis, fontSize: 11, marginBottom: 2 }}
              labelFormatter={(v) => `${Number(v).toFixed(2)} s`}
              formatter={(v) => [`${(v * 100).toFixed(1)}%`, 'P(manipulated)']}
            />
            <ReferenceLine y={threshold} stroke={critical} strokeDasharray="4 3" strokeWidth={2} />
            <Line
              type="monotone" dataKey="p" stroke={series} strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload, index } = props
                if (!payload.flagged) return <g key={index} />
                return (
                  <circle key={index} cx={cx} cy={cy} r={4.5} fill={critical}
                          stroke={surface} strokeWidth={2} />
                )
              }}
              activeDot={{ r: 5, fill: series, stroke: surface, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer text-[0.75rem] text-ink-muted hover:text-ink-primary">
          View as a table
        </summary>
        <div className="mt-2 max-h-48 overflow-auto rounded-lg"
             style={{ background: 'var(--surface-2)' }}>
          <table className="w-full text-left text-[0.75rem]">
            <thead className="sticky top-0" style={{ background: 'var(--surface-3)' }}>
              <tr>
                <th className="px-3 py-2 font-semibold">{unit}</th>
                <th className="px-3 py-2 font-semibold">Time</th>
                <th className="px-3 py-2 font-semibold">P(manipulated)</th>
                <th className="px-3 py-2 font-semibold">Flagged</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, index) => (
                <tr key={index} className="divide-row">
                  <td className="tnum px-3 py-1.5">{index}</td>
                  <td className="tnum px-3 py-1.5">{row.t.toFixed(2)}s</td>
                  <td className="tnum px-3 py-1.5">{(row.p * 100).toFixed(1)}%</td>
                  <td className="px-3 py-1.5">{row.flagged ? 'yes' : 'no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
