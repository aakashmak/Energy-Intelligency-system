export default function Sparkline({ data = [], width = 72, height = 28, color = '#6366F1', strokeWidth = 1.5 }) {
  if (data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const xs = data.map((_, i) => (i / (data.length - 1)) * width)
  const ys = data.map(v => height - 2 - ((v - min) / range) * (height - 4))

  let d = `M${xs[0].toFixed(1)},${ys[0].toFixed(1)}`
  for (let i = 1; i < xs.length; i++) {
    const cx = (xs[i - 1] + xs[i]) / 2
    d += ` C${cx.toFixed(1)},${ys[i - 1].toFixed(1)} ${cx.toFixed(1)},${ys[i].toFixed(1)} ${xs[i].toFixed(1)},${ys[i].toFixed(1)}`
  }
  const fillPath = `${d} L${xs[xs.length - 1].toFixed(1)},${height} L${xs[0].toFixed(1)},${height} Z`
  const id = `sg${color.replace(/[^a-z0-9]/gi, '')}`

  return (
    <svg width={width} height={height} style={{ overflow: 'visible', display: 'block', flexShrink: 0 }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth}
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
