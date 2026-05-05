export default function RadialGauge({ value = 0, max = 100, size = 52, strokeWidth = 4, color = '#6366F1', bg = 'rgba(255,255,255,0.06)', children }) {
  const r = (size - strokeWidth * 2) / 2
  const cx = size / 2
  const cy = size / 2
  const circ = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(1, value / max))
  const dash = pct * circ
  const gap  = circ - dash
  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', display: 'block' }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={bg} strokeWidth={strokeWidth} />
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={`${dash.toFixed(2)} ${gap.toFixed(2)}`}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color}80)` }}
        />
      </svg>
      {children && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {children}
        </div>
      )}
    </div>
  )
}
